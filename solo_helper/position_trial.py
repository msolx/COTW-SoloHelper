"""一次性位置实验：0.25m微移，或现场确认的10m内平地航点；不自动执行。"""
import ctypes as C
from ctypes import wintypes as W
import json
import math
import struct
import time

from memory.process_reader import ProcessReader, ReadError, ProcessAccessError, MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.physics_research import read_physics_position
from solo_helper.player_research import pointer_at, find_game_object
from solo_helper.waypoint_reader import read_user_waypoint
from solo_helper.trial_guard import exclusive_position_trial


def local_object(memory):
    if memory.sha256 != config.EXPECTED_SHA256:
        raise ReadError('当前构建不支持位置实验')
    registry = pointer_at(memory, memory.base + config.PLAYER_REGISTRY_CANDIDATE)
    manager = pointer_at(memory, registry + 0x60)
    character = pointer_at(memory, manager + 0x170)
    obj = find_game_object(memory, character)
    vtable = pointer_at(memory, obj)
    if pointer_at(memory, vtable + 0xa8) - memory.base != 0x6805b0:
        raise ReadError('人物类型与已核对getter不同')
    return obj


def motion_address(memory, obj, sample):
    component = pointer_at(memory, obj + 0x1ac8)
    controller = pointer_at(memory, component + 0xc0)
    world = pointer_at(memory, controller + 0x20)
    bodies = pointer_at(memory, world + 0x20)
    body_id, = struct.unpack('<i', memory.read(controller + 0x10, 4))
    if body_id != sample['body_id']:
        raise ReadError('人物物理体改变')
    motion_id, = struct.unpack('<i', memory.read(bodies + body_id * 0x90 + 0x68, 4))
    if motion_id != sample['motion_id']:
        raise ReadError('人物运动状态改变')
    motions = pointer_at(memory, world + 0xe0)
    return motions + motion_id * 0x80


def body_position_address(memory, obj, sample):
    component = pointer_at(memory, obj + 0x1ac8)
    controller = pointer_at(memory, component + 0xc0)
    world = pointer_at(memory, controller + 0x20)
    body_id, = struct.unpack('<i', memory.read(controller + 0x10, 4))
    if body_id != sample['body_id']:
        raise ReadError('人物物理体改变')
    bodies = pointer_at(memory, world + 0x20)
    return bodies + body_id * 0x90 + 0x30


def preflight_details(current, waypoint):
    """写入前保存可解释的数值，拒绝时也能知道具体哪个条件失败。"""
    if waypoint is None:
        return {'waypoint_present': False}
    values = (*current, *waypoint.marker_position)
    if not all(math.isfinite(v) for v in values):
        raise ReadError('人物或航点坐标包含非有限值')
    height = waypoint.input_height_candidate
    if height is not None and not math.isfinite(height):
        raise ReadError('航点输入高度异常')
    return dict(waypoint_present=True, player_position=list(current),
                waypoint_marker=list(waypoint.marker_position),
                horizontal_distance_m=math.hypot(waypoint.marker_position[0]-current[0],
                                               waypoint.marker_position[2]-current[2]),
                height_difference_m=None if height is None else height-current[1])


def nudge_bytes(current, waypoint, expected, *, nearby_waypoint=False):
    """生成单次水平位置变化；附近航点实验仅限现场确认的10米内平地。"""
    if waypoint is None or waypoint.input_height_candidate is None:
        raise ReadError('无有效用户航点或高度被限制，不实验')
    if len(expected) != 12:
        raise ReadError('微移仅允许12字节XYZ')
    x, y, z = current
    wx, wy, wz = waypoint.marker_position
    details = preflight_details(current, waypoint)
    distance = details['horizontal_distance_m']
    reasons = []
    if distance < 1.0:
        reasons.append(f'航点太近：水平距离{distance:.2f}米，要求至少1米')
    elif distance > 10.0:
        reasons.append(f'航点太远：水平距离{distance:.2f}米，上限10米')
    height_difference = details['height_difference_m']
    if abs(height_difference) > 0.25:
        reasons.append(f'高差超限：航点输入高度减人物高度为{height_difference:+.3f}米，允许±0.25米')
    if reasons:
        raise ReadError('；'.join(reasons)+'；未写入游戏')
    mx, my, mz = struct.unpack('<3f', expected)
    if not all(math.isfinite(v) for v in (*current, wx, wy, wz, mx, my, mz)):
        raise ReadError('微移参数异常')
    length = distance if nearby_waypoint else 0.25
    replacement = struct.pack('<3f', mx + (wx - x) / distance * length, my,
                              mz + (wz - z) / distance * length)
    return replacement


def validate_change(expected, replacement, *, nearby_waypoint=False, surface_trial=False,surface_max_distance=None,surface_max_ground_change=None):
    if len(expected) != 12 or len(replacement) != 12 or (not surface_trial and expected[4:8] != replacement[4:8]):
        raise ReadError('拒绝超出单次水平XYZ实验范围的写入')
    old = struct.unpack('<3f', expected)
    new = struct.unpack('<3f', replacement)
    if not all(math.isfinite(v) for v in (*old, *new)):
        raise ReadError('微移坐标非法')
    length = math.hypot(new[0]-old[0],new[2]-old[2])
    from solo_helper.surface_plan import surface_distance_limit,surface_height_limit
    maximum = surface_distance_limit(surface_max_distance)+0.001 if surface_trial else (10.001 if nearby_waypoint else 0.251)
    if surface_trial and abs(new[1]-old[1]) > surface_height_limit(surface_max_ground_change,surface_max_distance=surface_max_distance)+config.SURFACE_TRIAL_CLEARANCE+0.001:
        raise ReadError('高度适配垂直位移超出本阶段范围')
    if not 0.24 <= length <= maximum:
        raise ReadError('写入位移超出本次实验范围')


def apply_once(memory, address, expected, replacement, *, nearby_waypoint=False):
    """独立申请必要写权限，仅写可读写数据页的一次12字节，失败绝不重试。"""
    return apply_changes_once(memory, [(address,expected,replacement)], nearby_waypoint=nearby_waypoint)


def coupled_replacement(body_before, body_after, motion_before):
    """平移刚体与质心相同的XYZ增量，保留两者偏移和所有非XYZ字段。"""
    body = struct.unpack('<3f',body_before)
    target = struct.unpack('<3f',body_after)
    motion = struct.unpack('<3f',motion_before)
    if not all(math.isfinite(v) for v in (*body,*target,*motion)):
        raise ReadError('双状态位置异常')
    if math.hypot(motion[0]-body[0],motion[2]-body[2]) > 0.02 or not 0.2 < motion[1]-body[1] < 2.0:
        raise ReadError('人物物理体与质心尚未同步，不能生成双状态实验')
    return struct.pack('<3f',*(m+t-b for m,t,b in zip(motion,target,body)))


def apply_changes_once(memory, changes, *, nearby_waypoint=False, surface_trial=False,surface_max_distance=None,surface_max_ground_change=None):
    """至多两个位置，各写一次。两处写入不具备原子性，仅用于受控实验。"""
    if not 1 <= len(changes) <= 2:
        raise ReadError('只允许人物本体/质心至多两项')
    if surface_trial and len(changes) != 2:
        raise ReadError('高度适配必须同时同步本体与质心')
    for _, expected, replacement in changes:
        validate_change(expected,replacement,nearby_waypoint=nearby_waypoint,surface_trial=surface_trial,surface_max_distance=surface_max_distance,surface_max_ground_change=surface_max_ground_change)
    if len(changes) == 2:
        a, b = changes
        if abs(a[0]-b[0]) < 12 or coupled_replacement(a[1],a[2],b[1]) != b[2]:
            raise ReadError('双状态实验必须为不重叠且一致的平移')
    api = memory.api
    api.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
    api.GetProcessTimes.restype = W.BOOL
    api.WriteProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    api.WriteProcessMemory.restype = W.BOOL
    handle = api.OpenProcess(0x438, False, memory.pid)
    if not handle:
        raise ProcessAccessError('open_process_single_nudge', C.get_last_error())
    try:
        def creation_time(h):
            values = [W.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(h, *(C.byref(v) for v in values)):
                raise ProcessAccessError('get_process_times', C.get_last_error())
            return values[0].dwHighDateTime, values[0].dwLowDateTime
        if not memory.alive() or creation_time(handle) != creation_time(memory.handle):
            raise ReadError('目标游戏已退出或PID复用，拒绝写入')
        # 所有检查在第一处写入前完成，任一位置变化时整组取消。
        for address,expected,_ in changes:
            mbi = MEMORY_BASIC_INFORMATION()
            if api.VirtualQueryEx(handle,address,C.byref(mbi),C.sizeof(mbi)) != C.sizeof(mbi):
                raise ProcessAccessError('query_nudge_region',C.get_last_error())
            if (mbi.State != 0x1000 or mbi.Protect != 4
                    or not mbi.BaseAddress <= address < address+12 <= mbi.BaseAddress+mbi.RegionSize):
                raise ReadError('微移目标不是同一已提交普通读写数据页')
            if memory.read(address,12) != expected:
                raise ReadError('人物正在移动或数据已改变，不写入')
        for address,_,replacement in changes:
            buffer = C.create_string_buffer(replacement,12)
            written = C.c_size_t()
            if not api.WriteProcessMemory(handle,address,buffer,12,C.byref(written)) or written.value != 12:
                raise ProcessAccessError('write_position_group_no_retry',C.get_last_error())
        return [dict(requested=struct.unpack('<3f',replacement),
                     observed=struct.unpack('<3f',memory.read(address,12)))
                for address,_,replacement in changes]
    finally:
        api.CloseHandle(handle)


def inspect_trial(*,surface_trial=False,surface_max_distance=None,surface_max_ground_change=None):
    """GUI只读预览，当前航点每次重新读取，绝不使用上轮缓存传送。"""
    from solo_helper.surface_plan import surface_distance_limit,surface_height_limit
    if (surface_max_distance is not None or surface_max_ground_change is not None) and not surface_trial:
        raise ReadError('扩距只允许明确选择高度适配实验')
    maximum = surface_distance_limit(surface_max_distance) if surface_trial else None
    ground_limit = surface_height_limit(surface_max_ground_change,surface_max_distance=maximum) if surface_trial else None
    memory = ProcessReader()
    try:
        memory.connect()
        obj = local_object(memory)
        sample = read_physics_position(memory, obj)
        waypoint = read_user_waypoint(memory)
        if waypoint is None:
            result = {'状态':'未设置用户航点','可执行近距实验':False,'surface_max_distance':maximum}
            return save_preview_result(result,surface_trial)
        expected = struct.pack('<3f', *sample['local_position'])
        reason = ''
        terrain = None
        try:
            if surface_trial:
                from solo_helper.terrain_research import read_terrain_context
                from solo_helper.surface_plan import surface_transfer_bytes
                terrain = read_terrain_context(memory,sample['world_position'],waypoint.marker_position)
                surface_transfer_bytes(sample['world_position'],waypoint,expected,terrain,surface_max_distance=maximum,surface_max_ground_change=ground_limit)
            else:
                nudge_bytes(sample['world_position'], waypoint, expected, nearby_waypoint=True)
        except ReadError as exc:
            reason = str(exc)
        result = {'状态': reason or '满足所选阶段数值边界，仍须目视确认平缓干燥陆地无障碍',
                '人物坐标': sample['world_position'], '航点标记坐标': waypoint.marker_position,
                '水平距离米': math.hypot(waypoint.marker_position[0] - sample['world_position'][0],
                                       waypoint.marker_position[2] - sample['world_position'][2]),
                '航点输入高度': waypoint.input_height_candidate,
                '航点与人物高差米': None if waypoint.input_height_candidate is None else waypoint.input_height_candidate-sample['world_position'][1],
                '可执行近距实验': not reason, '自动地形水域障碍检测': False,
                '地形交叉检查':terrain,'surface_max_distance':maximum,
                'surface_max_ground_change':ground_limit}
        if terrain:
            result['起点实测高度减粗高程米'] = sample['world_position'][1]-terrain['current']['coarse_height']
            result['目标输入高度减粗高程米'] = (None if waypoint.input_height_candidate is None else
                                              waypoint.input_height_candidate-terrain['target']['coarse_height'])
        return save_preview_result(result,surface_trial)
    finally:
        memory.close()


def save_preview_result(result,surface_trial):
    """只读预览也落盘，避免只能从窗口手抄日志；不包含进程地址。"""
    result = dict(result,timestamp=time.time(),surface_trial=surface_trial,write_attempted=False)
    pending = config.WAYPOINT_PREVIEW_REPORT.with_suffix('.tmp')
    pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pending.replace(config.WAYPOINT_PREVIEW_REPORT)
    return result


def observation_result(report):
    """API写入成功与人物实际到达分别判断，不能把被游戏恢复的值算成功。"""
    before = report['before']
    desired = [v+o for v,o in zip(report['requested_local_position'],before['floating_origin'])]
    samples = report['samples']
    if not samples:
        return dict(status='movement_not_confirmed',error='没有人物反馈采样，不能确认移动')
    def horizontal(a,b):
        return math.hypot(a[0]-b[0],a[2]-b[2])
    last = samples[-1]
    error = horizontal(last['character'],desired)
    moved = horizontal(last['character'],before['world_position'])
    result = dict(final_horizontal_error_m=error,observed_horizontal_movement_m=moved)
    # 世界坐标用于到达判定；单独记录浮动原点重定位，不能把局部坐标变化误判成回弹。
    origins = [before['floating_origin']] + [frame['floating_origin'] for frame in samples
                                            if 'floating_origin' in frame]
    origin_changes = sum(a != b for a,b in zip(origins,origins[1:]))
    complete_origins = all('floating_origin' in frame for frame in samples)
    result.update(floating_origin_change_count=origin_changes if complete_origins else None)
    terrain = report.get('terrain')
    if terrain and terrain.get('current') and terrain.get('target'):
        result['cross_terrain_tile'] = terrain['current']['tile'] != terrain['target']['tile']
    tail = samples[-10:]
    reached = len(tail) == 10 and all(horizontal(frame[key],desired) <= 0.15 for frame in tail for key in ('physics','character'))
    if reached:
        result.update(status='position_reached_observation_required',
                      message='物理体和人物坐标已到达目标，仍需确认画面及正常移动；不是自动地形安全验收')
    else:
        result.update(status='movement_not_confirmed',
                      error=f'写入API成功，但人物未稳定到达：距目标{error:.2f}米，实际水平移动{moved:.2f}米；未重试')
    if reached and report.get('surface_trial'):
        ground = report['requested_ground_height']
        ground_error = abs(last['character'][1]-ground)
        vertical_spread = max(f['character'][1] for f in tail)-min(f['character'][1] for f in tail)
        result.update(final_ground_height_error_m=ground_error,final_vertical_spread_m=vertical_spread)
        if ground_error > 0.25 or vertical_spread > 0.08:
            result.update(status='landing_not_confirmed',
                          message='水平坐标已到达；自动落地检查尚未确认，请核对画面，不等于传送未发生',
                          error=f'稳定位置与航点输入高度相差{ground_error:.3f}米，末段垂直波动{vertical_spread:.3f}米；停止，不自动回写')
    return result


@exclusive_position_trial
def run_trial(*, single_player_confirmed=False, flat_ground_confirmed=False, approved=False, target=None,
              nearby_waypoint=False, surface_trial=False,surface_max_distance=None,surface_max_ground_change=None):
    # 必须由现场单人/平地确认及单独执行审批明确触发；导入此模块没有副作用。
    if not (single_player_confirmed and flat_ground_confirmed and approved):
        raise ReadError('位置微移实验需要现场确认和单独审批；默认不执行')
    # 质心单独写入已在实机被覆盖，禁止重复该失败路径；新实验只允许显式选择物理体位置。
    if target != 'body_and_motion':
        raise ReadError('仅开放双状态同步实验；旧的单字段写入方案已停用')
    if surface_trial and not nearby_waypoint:
        raise ReadError('高度适配需要明确选择整段航点实验')
    from solo_helper.surface_plan import surface_distance_limit,surface_height_limit
    if (surface_max_distance is not None or surface_max_ground_change is not None) and not surface_trial:
        raise ReadError('扩距只允许明确选择高度适配实验')
    maximum = surface_distance_limit(surface_max_distance) if surface_trial else None
    ground_limit = surface_height_limit(surface_max_ground_change,surface_max_distance=maximum) if surface_trial else None
    memory = ProcessReader()
    report = dict(kind='surface_height_trial' if surface_trial else ('nearby_waypoint_trial' if nearby_waypoint else 'quarter_meter_trial'), write_attempted=False, samples=[],
                  timestamp=time.time(), terrain_safety_implemented=False, target=target,surface_trial=surface_trial,
                  surface_max_distance=maximum,
                  surface_max_ground_change=ground_limit)
    try:
        # 批准后留5秒回游戏站稳，随后才采集用于本次实验的最新状态。
        time.sleep(5.0)
        memory.connect()
        obj = local_object(memory)
        sample = read_physics_position(memory, obj)
        waypoint = read_user_waypoint(memory)
        report['preflight'] = preflight_details(sample['world_position'], waypoint)
        address = body_position_address(memory, obj, sample)
        expected = memory.read(address, 12)
        terrain = None
        if surface_trial:
            from solo_helper.terrain_research import read_terrain_context,same_terrain_context
            from solo_helper.surface_plan import surface_transfer_bytes
            if waypoint is None:
                raise ReadError('未设置用户航点')
            terrain = read_terrain_context(memory,sample['world_position'],waypoint.marker_position)
            report.update(terrain=terrain,requested_ground_height=waypoint.input_height_candidate,
                          landing_clearance_m=config.SURFACE_TRIAL_CLEARANCE)
            replacement = surface_transfer_bytes(sample['world_position'],waypoint,expected,terrain,surface_max_distance=maximum,surface_max_ground_change=ground_limit)
        else:
            replacement = nudge_bytes(sample['world_position'], waypoint, expected, nearby_waypoint=nearby_waypoint)
        changes = [(address,expected,replacement)]
        motion_pointer = None
        if target == 'body_and_motion':
            motion_pointer = motion_address(memory,obj,sample)
            motion_expected = memory.read(motion_pointer,12)
            changes.append((motion_pointer,motion_expected,coupled_replacement(expected,replacement,motion_expected)))
        # 提交前重新定位，不能跨重新加载使用缓存对象/物理体/浮动原点。
        check = read_physics_position(memory, obj)
        if (local_object(memory) != obj or body_position_address(memory, obj, check) != address
                or sample['floating_origin'] != check['floating_origin']
                or math.dist(sample['world_position'], check['world_position']) > 0.01
                or (motion_pointer is not None and motion_address(memory,obj,check) != motion_pointer)
                or read_user_waypoint(memory) != waypoint):
            raise ReadError('人物、航点或场景变化，实验取消')
        if surface_trial and not same_terrain_context(terrain,read_terrain_context(memory,check['world_position'],waypoint.marker_position)):
            raise ReadError('高度适配提交前地形状态发生变化，停止')
        old_xyz,new_xyz = struct.unpack('<3f',expected),struct.unpack('<3f',replacement)
        report.update(before=sample, requested_horizontal_delta=math.hypot(new_xyz[0]-old_xyz[0],new_xyz[2]-old_xyz[2]),
                      requested_local_position=struct.unpack('<3f', replacement),
                      waypoint_marker=waypoint.marker_position)
        report['write_attempted'] = True
        report['planned_position_write_count'] = len(changes)
        report['immediate_readback'] = apply_changes_once(memory,changes,nearby_waypoint=nearby_waypoint,surface_trial=surface_trial,surface_max_distance=maximum,surface_max_ground_change=ground_limit)
        report['write_returned_success'] = True
        # 不冻结坐标、不重复写入、不回滚到可能已经不再安全的旧位置。
        # 记录实际物理/渲染反馈，API成功不能冒充人物移动成功。
        for _ in range(50):
            time.sleep(0.1)
            if local_object(memory) != obj:
                raise ReadError('采样时人物对象变化，停止，不再写入')
            after = read_physics_position(memory, obj)
            character = struct.unpack('<3f', memory.read(obj + 0x228c, 12))
            report['samples'].append(dict(physics=after['world_position'], character=character,
                                          motion=after['motion_local_position'],floating_origin=after['floating_origin']))
        report.update(observation_result(report))
    except Exception as exc:
        report.update(status='stopped', error=str(exc))
    finally:
        memory.close()
        report['handle_closed'] = memory.handle is None
        if config.POSITION_TRIAL_REPORT.exists():
            old = json.loads(config.POSITION_TRIAL_REPORT.read_text(encoding='utf-8'))
            archive = config.ROOT / f'position_trial_{int(old["timestamp"])}.json'
            if not archive.exists():
                archive.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding='utf-8')
        config.POSITION_TRIAL_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {key: value for key, value in report.items() if key != 'samples'}
    summary['sample_count'] = len(report['samples'])
    if report['samples']:
        summary.update(first_sample=report['samples'][0], last_sample=report['samples'][-1])
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return report
