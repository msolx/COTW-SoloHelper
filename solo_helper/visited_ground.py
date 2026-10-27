"""本轮固定只读记录的局部地面证据；不能泛化到未到访地面或其它保护区。"""
import hashlib
import json
import math
import time

from memory.process_reader import ReadError
from solo_helper import config


def witnessed_target(current,waypoint,terrain,source):
    if (source['id'] != config.NATIVE_GROUND_WITNESS_ANCHOR_ID
            or math.dist(source['position'],config.NATIVE_GROUND_WITNESS_ANCHOR_POSITION)>0.01):
        raise ReadError('本轮地面证据的真实帐篷锚点不匹配')
    if waypoint is None or waypoint.input_height_candidate is None:
        raise ReadError('缺少可信航点输入高度')
    xyz = (waypoint.marker_position[0],waypoint.input_height_candidate,waypoint.marker_position[2])
    if not all(math.isfinite(v) and abs(v)<1e6 for v in (*current,*xyz)):
        raise ReadError('地面证据坐标异常')
    distance = math.hypot(xyz[0]-current[0],xyz[2]-current[2])
    change = xyz[1]-current[1]
    if (not 1<=distance<=config.NATIVE_GROUND_WITNESS_MAX_DISTANCE
            or abs(change)>config.NATIVE_GROUND_WITNESS_MAX_HEIGHT
            or abs(change)/distance>config.SURFACE_TRIAL_MAX_SLOPE_RATIO):
        raise ReadError('已到访落点仍超出本轮距离、高差或坡度边界')
    for name in ('current','target'):
        tile = terrain.get(name,{})
        if (tile.get('state')!=3 or not tile.get('loaded_candidate') or tile.get('body_count',0)<=0
                or not math.isfinite(tile.get('coarse_height',float('nan')))):
            raise ReadError('已到访落点的当前地形加载检查未通过')
    raw = config.NATIVE_GROUND_WITNESS_REPORT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != config.NATIVE_GROUND_WITNESS_SHA256:
        raise ReadError('地面观察记录哈希不匹配，不采纳修改后的证据')
    record = json.loads(raw)
    age = time.time()-record.get('timestamp',0)
    if (record.get('kind')!='manual_native_fast_travel_observation' or record.get('write_attempted') is not False
            or record.get('status')!='observation_finished' or record.get('native_functions_called') is not False
            or not 0<=age<=config.NATIVE_GROUND_WITNESS_MAX_AGE):
        raise ReadError('地面观察来源或有效期不满足本轮条件')
    near = []
    for frame in record.get('samples',[]):
        if frame.get('state')!='observed' or frame.get('native_request',{}).get('state')!=0:
            continue
        position = frame.get('world_position',())
        if len(position)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in position):
            raise ReadError('地面观察记录坐标损坏')
        if math.hypot(position[0]-xyz[0],position[2]-xyz[2])<=config.NATIVE_GROUND_WITNESS_RADIUS:
            near.append(position)
    if len(near)<10:
        raise ReadError('航点不在已到访地面证据的一米范围内')
    heights = [p[1] for p in near]
    ground = sum(heights)/len(heights)
    if max(heights)-min(heights)>0.08 or abs(ground-xyz[1])>0.25:
        raise ReadError('实测站立高度不稳定或与目标高度不符')
    target = (xyz[0],xyz[1]+config.SURFACE_TRIAL_CLEARANCE,xyz[2])
    evidence = dict(source='reviewed_local_ground_observation',report=config.NATIVE_GROUND_WITNESS_REPORT.name,
                    sample_count=len(near),observed_ground_height=ground,waypoint_ground_error_m=xyz[1]-ground,
                    max_radius_m=config.NATIVE_GROUND_WITNESS_RADIUS,age_seconds=age,
                    coarse_disagreement_m=xyz[1]-terrain['target']['coarse_height'],
                    automatic_ground_detection=False)
    return target,evidence
