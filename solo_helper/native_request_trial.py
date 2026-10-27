"""原生请求重定向：真实帐篷或临时用户航点入口；只改早期请求，不调用游戏函数。"""
import json
import math
import struct
import time

from memory.process_reader import ProcessReader,ReadError,ProcessAccessError
from solo_helper import config
from solo_helper.native_request import read_request,write_target_once,RequestChanging
from solo_helper.physics_research import read_physics_position
from solo_helper.player_research import pointer_at
from solo_helper.position_trial import local_object
from solo_helper.probe_native_points import inspect_points
from solo_helper.surface_plan import native_transfer_bytes,GroundHeightMismatch
from solo_helper.terrain_research import read_terrain_context,same_terrain_context
from solo_helper.trial_guard import position_trial_guard
from solo_helper.waypoint_reader import read_user_waypoint,marker_count
from solo_helper.virtual_tent_marker import TemporaryTentMarker


def find_trigger_tent(memory):
    """只查用户已给出的真实帐篷；不能从最近标记任意选一个作为触发源。"""
    manager = pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE)
    descriptor = memory.read(manager+0x70,24)
    begin,count = marker_count(descriptor)
    if count > config.TRAVEL_RESEARCH_MAX_MARKERS:
        raise ReadError('地图标记数超过原生实验上限')
    candidates = []
    for index in range(count):
        record = begin+index*0x100
        flags = memory.read(record+0x60,4)
        if flags[0] != 40:
            continue
        position_raw = memory.read(record+0x20,12)
        xyz = struct.unpack('<3f',position_raw)
        identity = memory.read(record+0x30,8)
        reference = config.TRAVEL_RESEARCH_REFERENCE_XZ
        if not all(math.isfinite(v) and abs(v)<1e6 for v in xyz):
            raise ReadError('真实帐篷标记坐标异常')
        if math.hypot(xyz[0]-reference[0],xyz[2]-reference[1]) <= config.TRAVEL_RESEARCH_REFERENCE_RADIUS:
            if (memory.read(record+0x60,4) != flags or memory.read(record+0x20,12) != position_raw
                    or memory.read(record+0x30,8) != identity):
                raise ReadError('帐篷记录在核对期间改变')
            candidates.append(dict(id=struct.unpack('<Q',identity)[0],position=xyz))
    if (len(candidates) != 1 or pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE) != manager
            or memory.read(manager+0x70,24) != descriptor):
        raise ReadError('指定位置未找到唯一且稳定的真实帐篷，不进行原生实验')
    return candidates[0]


def plan_target(current,waypoint,terrain,mesh_evidence=None):
    # 独立的受控原生阶段；复用加载不等于跳过目标地面、坡度或区块检查。
    raw = native_transfer_bytes(current,waypoint,struct.pack('<3f',*current),terrain,
                                 mesh_evidence=mesh_evidence)
    return struct.unpack('<3f',raw)


def plan_with_mesh(memory,current,waypoint,terrain):
    """只在粗表失配时读取完整基础碰撞网格；其它拒绝条件不走此分支。"""
    try:
        return plan_target(current,waypoint,terrain),None
    except GroundHeightMismatch as mismatch:
        if not config.NATIVE_BASE_MESH_ENABLED:
            raise
        from solo_helper.ground_mesh import read_mesh_evidence
        try:
            evidence=read_mesh_evidence(memory,current,waypoint,terrain)
        except ProcessAccessError:
            raise  # 权限失败不能降级成普通地形误差或触发其它读取方式。
        except ReadError as exc:
            mismatch.diagnostics['mesh_recheck_error']=str(exc)
            mismatch.args=(str(mismatch)+'；基础网格复核：'+str(exc),)
            raise mismatch from exc
        return plan_target(current,waypoint,terrain,evidence),evidence.report()


def resolve_virtual_source(points,marker):
    eligible = [p for p in points if p['primary_query_eligible']]
    candidates = eligible or points  # 完全复现A84710：筛选结果为空才使用不筛选查询
    if not candidates:
        raise ReadError('没有已注册原生传送点，不能临时复用原生请求')
    chosen = min(candidates,key=lambda p:math.dist(p['position'],marker))
    if (config.VIRTUAL_TENT_MAX_FALLBACK_DISTANCE is not None and
            math.hypot(chosen['position'][0]-marker[0],chosen['position'][2]-marker[2])>config.VIRTUAL_TENT_MAX_FALLBACK_DISTANCE):
        raise ReadError('最近原生后备点过远，不开放本轮临时图标实验')
    return chosen['position']


def prepare_trial(memory,*,virtual_marker=False):
    initial = read_request(memory)
    if initial.state != 0:
        raise ReadError('已有原生移动请求，先停止，不接管现有请求')
    point_report = inspect_points(memory)
    player = read_physics_position(memory,local_object(memory))
    waypoint = read_user_waypoint(memory)
    if waypoint is None:
        raise ReadError('未设置用户航点')
    if virtual_marker:
        source = dict(id=config.USER_WAYPOINT_ID,position=waypoint.marker_position)
        native_source_position = resolve_virtual_source(point_report['registered_points'],waypoint.marker_position)
    else:
        source = find_trigger_tent(memory)
        points = point_report['nearest_real_tent_candidates']
        if not points or points[0]['reference_horizontal_m'] > 5:
            raise ReadError('未找到对应真实帐篷的已注册原生落点')
        native_source_position = points[0]['position']
    terrain = read_terrain_context(memory,player['world_position'],waypoint.marker_position)
    evidence = None
    try:
        target,evidence = plan_with_mesh(memory,player['world_position'],waypoint,terrain)
        if evidence is not None and not same_terrain_context(
                terrain,read_terrain_context(memory,player['world_position'],waypoint.marker_position)):
            raise ReadError('基础网格复核期间地形资源改变')
    except ProcessAccessError:
        raise
    except ReadError as exc:
        exc.preflight_context=dict(player_position=player['world_position'],
                  waypoint_marker=waypoint.marker_position,ground_height=waypoint.input_height_candidate,
                  horizontal_distance_m=math.hypot(waypoint.marker_position[0]-player['world_position'][0],
                                                   waypoint.marker_position[2]-player['world_position'][2]),
                  terrain=terrain)
        is_height_mesh_issue = (
            isinstance(exc, GroundHeightMismatch) or
            any(k in str(exc) for k in ('基础网格', '粗地形', '交叉检查', '覆盖面', '单物理体', '高度尚未核实'))
        )
        is_fatal_context_error = any(k in str(exc) for k in ('疑似粗表+12米', '地形资源改变', '场景改变', '采样期间变化', '构建未验证', '高度未知'))
        if (getattr(config,'NATIVE_WAYPOINT_FALLBACK_ENABLED',True)
                and is_height_mesh_issue and not is_fatal_context_error):
            if waypoint.input_height_candidate is None:
                raise
            target = (waypoint.marker_position[0],
                      waypoint.input_height_candidate+config.SURFACE_TRIAL_CLEARANCE,
                      waypoint.marker_position[2])
            evidence = dict(kind='waypoint_direct_fallback',
                            reason=str(exc),
                            waypoint_ground=waypoint.input_height_candidate,
                            clearance=config.SURFACE_TRIAL_CLEARANCE)
        elif not config.NATIVE_GROUND_WITNESS_ENABLED:
            raise
        else:
            from solo_helper.visited_ground import witnessed_target
            target,evidence = witnessed_target(player['world_position'],waypoint,terrain,source)
    return dict(initial=initial,source=source,native_source_position=native_source_position,
                player=player,waypoint=waypoint,terrain=terrain,target=target,ground_evidence=evidence)


def inspect_trial(*,virtual_marker=False):
    """默认入口只读预检，与执行阶段使用同一套计划，失败不打开写句柄。"""
    memory = ProcessReader()
    result = dict(timestamp=time.time(),write_attempted=False,
                  native_distance_limit_m=config.NATIVE_REDIRECT_MAX_DISTANCE)
    try:
        memory.connect()
        plan = prepare_trial(memory,virtual_marker=virtual_marker)
        result.update(status='ready_for_confirmed_trial',source_marker_id=hex(plan['source']['id']),
                      source_marker_position=plan['source']['position'],virtual_marker_mode=virtual_marker,
                      predicted_native_fallback_position=plan['native_source_position'],
                      player_position=plan['player']['world_position'],
                      waypoint_marker=plan['waypoint'].marker_position,target_position=plan['target'],
                      ground_height=plan['waypoint'].input_height_candidate,
                      native_state=plan['initial'].state,terrain=plan['terrain'],ground_evidence=plan['ground_evidence'])
    except Exception as exc:
        result.update(status='stopped',error=str(exc))
        if hasattr(exc,'preflight_context'):
            result['preflight']=exc.preflight_context
        if isinstance(exc,GroundHeightMismatch):
            result['height_diagnostics'] = exc.diagnostics
        if isinstance(exc,ProcessAccessError):
            result['access_error'] = dict(stage=exc.stage,winerror=exc.winerror)
    finally:
        memory.close()
        result['handle_closed'] = memory.handle is None
    # 预检失败也保留本地数值，避免只能从窗口抄报错；不记录原始内存或上传。
    try:
        path = config.ROOT/'native_waypoint_preview.json'
        pending = path.with_suffix('.tmp')
        pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        pending.replace(path)
    except OSError as exc:
        result['report_save_error'] = str(exc)
    return result


def result_from_samples(samples,target,ground):
    # 先识别连续稳定到达，再分析最终状态；用户正常走动不能抹掉已经观测到的到达。
    arrival = None
    window = []
    for frame in samples:
        valid = ('position' in frame and frame.get('native_state')==0
                 and math.hypot(frame['position'][0]-target[0],frame['position'][2]-target[2])<=0.15
                 and abs(frame['position'][1]-ground)<=0.25
                 and ('native_target' not in frame or math.dist(frame['native_target'],target)<=0.02))
        window = (window+[frame])[-10:] if valid else []
        if len(window)==10 and max(f['position'][1] for f in window)-min(f['position'][1] for f in window)<=0.08:
            arrival = dict(first_stable_elapsed=window[0].get('elapsed'),position=window[-1]['position'])
            break
    tail = samples[-10:]
    if len(tail)<10 or any('position' not in frame for frame in tail):
        return dict(status='movement_not_confirmed',error='最终有效反馈不足，不使用旧位置作当前结果',
                    stable_arrival_observed=arrival)
    horizontal = lambda p:math.hypot(p[0]-target[0],p[2]-target[2])
    error = horizontal(tail[-1]['position'])
    spread = max(frame['position'][1] for frame in tail)-min(frame['position'][1] for frame in tail)
    height_error = abs(tail[-1]['position'][1]-ground)
    reached = all(horizontal(frame['position'])<=0.15 and frame.get('native_state')==0
                  and ('native_target' not in frame or math.dist(frame['native_target'],target)<=0.02) for frame in tail)
    status = ('position_reached_observation_required' if reached and spread<=0.08 and height_error<=0.25
              else 'landing_not_confirmed' if reached else 'movement_not_confirmed')
    if arrival and not reached and all(frame.get('native_state')==0 for frame in tail):
        changed_request = any('native_target' in f and math.dist(f['native_target'],target)>0.02 for f in tail)
        status = 'native_request_replaced_after_arrival' if changed_request else 'position_reached_later_position_changed'
    return dict(status=status,final_horizontal_error_m=error,final_ground_height_error_m=height_error,
                final_vertical_spread_m=spread,final_position=tail[-1]['position'],stable_arrival_observed=arrival)


def run(*,approved=False,single_player_confirmed=False,flat_ground_confirmed=False,expected_waypoint_marker=None,
        virtual_marker=False,progress=None):
    if not (approved and single_player_confirmed and flat_ground_confirmed):
        raise ReadError('原生请求实验需要单人、当次干燥平地确认及独立审批')
    with position_trial_guard():
        memory = ProcessReader()
        lease = None
        report = dict(kind='native_request_redirect_trial',timestamp=time.time(),write_attempted=False,
                      native_functions_called=False,real_tent_modified=False,savefiles_modified=False,
                      terrain_safety_implemented=False,status='not_started',samples=[],phases=[],virtual_marker_mode=virtual_marker)
        def notify(event,**values):
            if progress is not None:
                try:
                    progress(dict(event=event,**values))
                except Exception as exc:
                    # 通知失败不能跳过清理或改变已批准的游戏操作。
                    report.setdefault('notification_errors',[]).append(str(exc))
        try:
            memory.connect()
            plan = prepare_trial(memory,virtual_marker=virtual_marker)
            initial,source,native_source_position,player,waypoint,terrain,target = (
                plan[key] for key in ('initial','source','native_source_position','player','waypoint','terrain','target'))
            if expected_waypoint_marker is not None and tuple(expected_waypoint_marker) != waypoint.marker_position:
                raise ReadError('航点与本次审批指定坐标不同，未启动原生实验')
            report.update(source_marker=dict(id=hex(source['id']),position=source['position']),
                          source_registered_position=native_source_position,player_before=player['world_position'],
                          waypoint_marker=waypoint.marker_position,target_position=target,
                          ground_height=waypoint.input_height_candidate,before_origin=player['floating_origin'],
                          ground_evidence=plan['ground_evidence'])
            if virtual_marker:
                lease = TemporaryTentMarker(memory,waypoint)
                report['marker_conversion'] = lease.acquire(approved=approved)
            print('NATIVE_REDIRECT_ARMED '+json.dumps({k:report[k] for k in ('source_marker','target_position','virtual_marker_mode')},ensure_ascii=True),flush=True)
            notify('armed',target_position=target,virtual_marker_mode=virtual_marker,
                   wait_seconds=config.NATIVE_REDIRECT_ARM_SECONDS)
            started = time.monotonic()
            pending_seen = False
            while time.monotonic()-started < config.NATIVE_REDIRECT_ARM_SECONDS:
                cancel = config.NATIVE_REDIRECT_CANCEL_FILE
                if cancel.exists() and cancel.stat().st_mtime>=report['timestamp']:
                    raise ReadError('已取消尚未提交的请求重定向')
                try:
                    request = read_request(memory)
                except RequestChanging:
                    time.sleep(config.NATIVE_REDIRECT_POLL_SECONDS)
                    continue
                if request.controller != initial.controller or request.map_manager != initial.map_manager:
                    raise ReadError('原生控制器或地图场景已更换，停止实验')
                if not report['phases'] or report['phases'][-1]['state'] != request.state:
                    report['phases'].append(dict(elapsed=time.monotonic()-started,state=request.state,
                                                 remaining=request.remaining,selection_id=hex(request.selection_id)))
                if request.state == 9:
                    pending_seen = True  # 原生菜单后的等待阶段；此时绝不写入
                elif request.state == 2:
                    if request.selection_id != source['id']:
                        raise ReadError('启动的不是指定真实帐篷请求；未改目标')
                    if math.dist(request.position,native_source_position)>0.05:
                        raise ReadError('原生初始落点与已核对帐篷不一致；未改目标')
                    current = read_physics_position(memory,local_object(memory))
                    current_waypoint = lease.validate() if lease else read_user_waypoint(memory)
                    if (current_waypoint != waypoint
                            or math.dist(current['world_position'],player['world_position'])>0.1):
                        raise ReadError('人物或航点变化，停止本轮原生实验')
                    fresh_terrain = read_terrain_context(memory,current['world_position'],waypoint.marker_position)
                    if not same_terrain_context(terrain,fresh_terrain):
                        raise ReadError('目标地形状态改变，未改原生请求')
                    if (plan['ground_evidence'] is not None
                            and plan['ground_evidence'].get('kind')!='base_collision_mesh_crosscheck'):
                        if plan['ground_evidence'].get('kind')=='waypoint_direct_fallback':
                            report['ground_evidence'] = plan['ground_evidence']
                        else:
                            from solo_helper.visited_ground import witnessed_target
                            witnessed_target(current['world_position'],waypoint,fresh_terrain,source)
                    else:
                        fresh_target,fresh_evidence=plan_with_mesh(memory,current['world_position'],waypoint,fresh_terrain)
                        if math.dist(fresh_target,target)>0.001:
                            raise ReadError('基础网格复核后的目标改变，未改原生请求')
                        report['ground_evidence']=fresh_evidence
                    # 网格读取耗时较多；完成后再核对人物/航点，不能依赖读取前的状态。
                    final_player=read_physics_position(memory,local_object(memory))
                    final_waypoint=lease.validate() if lease else read_user_waypoint(memory)
                    if final_waypoint!=waypoint or math.dist(final_player['world_position'],current['world_position'])>0.1:
                        raise ReadError('提交前人物或航点改变，未改原生请求')
                    if not same_terrain_context(fresh_terrain,read_terrain_context(
                            memory,final_player['world_position'],waypoint.marker_position)):
                        raise ReadError('提交前地形资源改变，未改原生请求')
                    def on_attempt():
                        report['write_attempted'] = True
                    report['immediate_readback'] = write_target_once(memory,request,target,on_attempt=on_attempt)
                    report['request_write_succeeded'] = True
                    print('NATIVE_REQUEST_REDIRECT_WRITTEN '+json.dumps(target),flush=True)
                    notify('request_written',target_position=target)
                    if lease:
                        # 请求已复制所需数据；立即撤销临时图标，避免用户再次点击排队第二次。
                        report['marker_restoration'] = lease.restore()
                        notify('marker_restored',restoration=report['marker_restoration'])
                    break
                elif request.state not in (0,9):
                    raise ReadError('已错过原生请求阶段2，不补写，不重试')
                elif pending_seen and request.state == 0:
                    raise ReadError('原生请求已结束，未改写')
                time.sleep(config.NATIVE_REDIRECT_POLL_SECONDS)
            else:
                raise ReadError('等待指定原生快速移动超时，没有改写请求')
            observing = time.monotonic()
            idle_since = None
            target_replacement = None
            while time.monotonic()-observing < config.NATIVE_REDIRECT_OBSERVE_SECONDS:
                try:
                    native = read_request(memory)
                    current = read_physics_position(memory,local_object(memory))
                    elapsed = time.monotonic()-observing
                    report['samples'].append(dict(elapsed=elapsed,native_state=native.state,
                                                  native_target=native.position,selection_id=hex(native.selection_id),
                                                  position=current['world_position'],floating_origin=current['floating_origin']))
                    if not report['phases'] or report['phases'][-1]['state'] != native.state:
                        report['phases'].append(dict(elapsed_after_write=elapsed,state=native.state,
                                                     remaining=native.remaining,target_position=native.position,
                                                     selection_id=hex(native.selection_id)))
                    if target_replacement is None and math.dist(native.position,target)>0.02:
                        target_replacement = dict(elapsed_after_write=elapsed,state=native.state,
                                                  target_position=native.position,selection_id=hex(native.selection_id))
                    if native.state == 0:
                        if idle_since is None:
                            print('NATIVE_REQUEST_IDLE_OBSERVING',flush=True)
                            notify('idle_observing',seconds=config.NATIVE_REDIRECT_IDLE_OBSERVE_SECONDS)
                        idle_since = time.monotonic() if idle_since is None else idle_since
                        if time.monotonic()-idle_since >= config.NATIVE_REDIRECT_IDLE_OBSERVE_SECONDS:
                            break
                    else:
                        idle_since = None
                except ProcessAccessError:
                    raise
                except ReadError as exc:
                    report['samples'].append(dict(elapsed=time.monotonic()-observing,error=str(exc)))
                    idle_since = None
                time.sleep(0.05)
            report.update(result_from_samples(report['samples'],target,waypoint.input_height_candidate))
            report['later_target_replacement'] = target_replacement
        except Exception as exc:
            report.update(status='stopped',error=str(exc))
            if hasattr(exc,'preflight_context'):
                report['preflight']=exc.preflight_context
            if isinstance(exc,GroundHeightMismatch):
                report['height_diagnostics'] = exc.diagnostics
            if isinstance(exc,ProcessAccessError):
                report['access_error'] = dict(stage=exc.stage,winerror=exc.winerror)
        finally:
            if lease:
                try:
                    report['marker_restoration'] = lease.restore()
                except Exception as exc:
                    report['marker_restore_error'] = str(exc)
                    report['marker_restoration'] = lease.restoration
                    if isinstance(exc,ProcessAccessError):
                        report['cleanup_access_error'] = dict(stage=exc.stage,winerror=exc.winerror)
            memory.close()
            report['handle_closed'] = memory.handle is None
            path = config.ROOT/f'native_redirect_{int(report["timestamp"])}.json'
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        summary = {key:value for key,value in report.items() if key != 'samples'}
        summary['sample_count'] = len(report['samples'])
        print(json.dumps(summary,ensure_ascii=True,indent=2),flush=True)
        return report


if __name__ == '__main__':
    print(json.dumps(inspect_trial(),ensure_ascii=True,indent=2))
