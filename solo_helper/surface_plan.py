"""下一阶段的高度适配计划：利用只读证据筛查，仍需人工确认陆地无障碍。"""
import math
import struct
from memory.process_reader import ReadError
from solo_helper import config


class GroundHeightMismatch(ReadError):
    """保留失败数值供界面与本地报告使用，不把粗表偏差误称为人物异常。"""
    def __init__(self, ground, coarse, current_height, current_coarse):
        self.diagnostics = dict(
            reason='target_coarse_height_mismatch',
            waypoint_ground_height_m=ground, target_coarse_height_m=coarse,
            target_difference_m=ground-coarse,
            tolerance_m=config.SURFACE_TRIAL_COARSE_TOLERANCE,
            player_height_m=current_height, player_coarse_height_m=current_coarse,
            player_difference_m=current_height-current_coarse,
            coarse_grid_spacing_m=64, fine_ground_verified=False)
        super().__init__(
            f'航点地面高度尚未核实：候选{ground:.2f}米，粗地形{coarse:.2f}米，'
            f'差{ground-coarse:+.2f}米，超过{config.SURFACE_TRIAL_COARSE_TOLERANCE:g}米交叉检查范围。'
            '这是目标高度不一致，不代表人物坐标错误；粗表可能误差较大，'
            '当前无法自动区分粗表误差与无效落点，未执行传送。')


def surface_distance_limit(value=None):
    """只允许已列出的实验阶段；不能通过任意大数关闭距离限制。"""
    value = config.SURFACE_TRIAL_MAX_DISTANCE if value is None else value
    if type(value) not in (int,float) or not math.isfinite(value) or value not in config.SURFACE_RESEARCH_DISTANCE_STAGES:
        raise ReadError('未开放的高度适配距离阶段')
    return float(value)


def surface_height_limit(value=None,*,surface_max_distance=None):
    """高度扩展必须显式选择白名单阶段，默认不提升原有门槛。"""
    maximum = surface_distance_limit(surface_max_distance)
    value = config.SURFACE_RESEARCH_GROUND_CHANGE[maximum] if value is None else value
    if type(value) not in (int,float) or not math.isfinite(value) or value not in config.SURFACE_RESEARCH_HEIGHT_STAGES:
        raise ReadError('未开放的高度适配高差阶段')
    return float(value)


def surface_transfer_bytes(current,waypoint,expected,terrain,*,surface_max_distance=None,surface_max_ground_change=None,mesh_evidence=None):
    maximum = surface_distance_limit(surface_max_distance)
    ground_limit = surface_height_limit(surface_max_ground_change,surface_max_distance=maximum)
    return _ground_transfer_bytes(current,waypoint,expected,terrain,maximum,ground_limit,mesh_evidence)


def native_transfer_bytes(current,waypoint,expected,terrain,*,mesh_evidence=None):
    """原生加载路线独立限值；用户取消其距离上限，不连带开放旧物理体直接移动。"""
    maximum=config.NATIVE_REDIRECT_MAX_DISTANCE
    if maximum is not None and (type(maximum) not in (int,float) or not math.isfinite(maximum) or maximum<1):
        raise ReadError('原生航点距离配置异常')
    ground_limit=config.NATIVE_REDIRECT_MAX_HEIGHT
    if type(ground_limit) not in (int,float) or not math.isfinite(ground_limit) or ground_limit<=0:
        raise ReadError('原生航点高差配置异常')
    return _ground_transfer_bytes(current,waypoint,expected,terrain,maximum,ground_limit,mesh_evidence)


def _ground_transfer_bytes(current,waypoint,expected,terrain,maximum,ground_limit,mesh_evidence):
    if waypoint is None or waypoint.input_height_candidate is None:
        raise ReadError('航点高度未知或被游戏下限限制，无法适配落地高度')
    if len(expected) != 12:
        raise ReadError('高度适配仅允许本体XYZ')
    x,y,z = current
    wx,_,wz = waypoint.marker_position
    ground = waypoint.input_height_candidate
    old = struct.unpack('<3f',expected)
    if not all(math.isfinite(v) for v in (*current,wx,wz,ground,*old)):
        raise ReadError('高度适配坐标异常')
    distance = math.hypot(wx-x,wz-z)
    change = ground-y
    if distance<1 or (maximum is not None and distance>maximum):
        requirement='至少1米' if maximum is None else f'1～{maximum:g}米'
        raise ReadError(f'高度适配阶段水平距离{distance:.2f}米，要求{requirement}')
    if abs(change) > ground_limit:
        raise ReadError(f'候选地面高差{change:+.3f}米，超过本阶段±{ground_limit:g}米')
    if maximum is not None and abs(change)/distance > config.SURFACE_TRIAL_MAX_SLOPE_RATIO:
        raise ReadError('两点高度变化比例过大，当前阶段不测试陡坡')
    for name,height in (('current',y),('target',ground)):
        info = terrain.get(name,{})
        if not info.get('loaded_candidate') or info.get('state') != 3 or info.get('body_count',0) <= 0:
            raise ReadError('人物或目标地形区块未通过加载状态检查')
        coarse = info.get('coarse_height',float('nan'))
        if not math.isfinite(coarse):
            raise ReadError('缺少可信的粗高程交叉检查')
        if name == 'target' and abs(height-coarse-config.SURFACE_TRIAL_FALLBACK_OFFSET) <= config.SURFACE_TRIAL_FALLBACK_TOLERANCE:
            raise ReadError('航点高度疑似粗表+12米的回退结果，不将其当成实际地面')
        # 起点高度来自已核对的物理体，而粗表仅64米分辨率；实际到访对照已发现7米误差。
        # 起点粗表偏差作为诊断，不据此否定真实人物位置；目标高度仍保持原有保守门禁。
        if name == 'target' and abs(height-coarse) > config.SURFACE_TRIAL_COARSE_TOLERANCE:
            from solo_helper.ground_mesh import BaseMeshEvidence
            if not isinstance(mesh_evidence,BaseMeshEvidence) or not mesh_evidence.validate(current,waypoint,terrain):
                raise GroundHeightMismatch(ground,coarse,y,terrain['current']['coarse_height'])
    target_ground = ground
    if mesh_evidence is not None and hasattr(mesh_evidence, 'target_mesh_height'):
        target_ground = max(ground, mesh_evidence.target_mesh_height)
    target_y = target_ground + config.SURFACE_TRIAL_CLEARANCE
    return struct.pack('<3f',old[0]+wx-x,old[1]+target_y-y,old[2]+wz-z)
