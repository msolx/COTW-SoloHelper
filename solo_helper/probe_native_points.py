"""按已核对指令读取原生传送点与控制器方法地址；不调用方法，不写游戏内存。"""
import json
import math
import struct
import time

from memory.process_reader import ProcessReader,ReadError,valid_pointer
from solo_helper import config
from solo_helper.player_research import pointer_at
from solo_helper.waypoint_reader import read_user_waypoint


def module_rva(memory,address):
    rva = address-memory.base
    if not 0 <= rva < 0x4000000:
        raise ReadError('原生对象方法不属于当前已研究主模块范围')
    return hex(rva)


def native_request_snapshot(memory):
    """只读原生控制器请求；接口指针是本体+0x10，所有偏移以该接口为准。"""
    if not config.is_compatible_build(memory.sha256):
        raise ReadError('原生请求仅支持精确构建')
    controller = pointer_at(memory,memory.base+0x27c3ae8)
    vtable = pointer_at(memory,controller)
    if (vtable-memory.base not in (0x1c2a208, 0x1c2a218)
            or pointer_at(memory,vtable+0x98)-memory.base != 0x824c00
            or pointer_at(memory,vtable+0xa0)-memory.base != 0x8254b0):
        raise ReadError('原生请求控制器类型或方法变化，停止读取')
    state_raw = memory.read(controller+0xf8,4)
    state, = struct.unpack('<I',state_raw)
    raw = memory.read(controller+0x100,64)
    matrix = struct.unpack('<16f',raw)
    if not 0 <= state <= 9 or not all(math.isfinite(v) and abs(v)<1e7 for v in matrix):
        raise ReadError('原生请求状态或矩阵异常')
    if (pointer_at(memory,memory.base+0x27c3ae8) != controller
            or memory.read(controller+0xf8,4) != state_raw
            or memory.read(controller+0x100,64) != raw):
        raise ReadError('原生请求在采样时变化，丢弃本帧')
    return dict(state=state,target_position=matrix[12:15])


def inspect_points(memory):
    if not config.is_compatible_build(memory.sha256):
        raise ReadError('原生传送点探针仅支持精确构建')
    root = pointer_at(memory,memory.base+0x27c5dc8)  # A84755全局对象
    descriptor = memory.read(root+0x258,16)
    begin,end = struct.unpack('<2Q',descriptor)
    if not (valid_pointer(begin) and valid_pointer(end) and begin <= end
            and (end-begin)%16 == 0 and (end-begin)//16 <= config.NATIVE_TRAVEL_MAX_POINTS):
        raise ReadError('原生传送点列表边界异常')
    waypoint = read_user_waypoint(memory)
    points = []
    guards = []
    for index in range((end-begin)//16):
        entry_address = begin+index*16
        entry = memory.read(entry_address,16)
        point,control = struct.unpack('<2Q',entry)
        if not control:
            continue
        if not valid_pointer(control):
            raise ReadError('原生传送点弱引用控制块异常')
        strong_raw = memory.read(control+8,4)
        strong, = struct.unpack('<i',strong_raw)
        if strong <= 0:
            continue  # 不读已释放对象；不增加引用计数，不伪造对象生命期
        if not valid_pointer(point) or strong > 1_000_000:
            raise ReadError('原生传送点对象或引用计数异常')
        xyz_raw = memory.read(point+0x128,12)
        xyz = struct.unpack('<3f',xyz_raw)
        if not all(math.isfinite(v) and abs(v)<1e6 for v in xyz):
            raise ReadError('原生传送点坐标异常')
        vtable = pointer_at(memory,point)
        getter = pointer_at(memory,vtable+0xa8)
        primary_a = memory.read(point+0x138,1)  # 960CA0：该字节非零且154为零
        primary_b = memory.read(point+0x154,1)
        reference = config.TRAVEL_RESEARCH_REFERENCE_XZ
        dist = math.hypot(xyz[0]-reference[0],xyz[2]-reference[1])
        target_dist = (math.dist(xyz,waypoint.marker_position) if waypoint else None)
        points.append(dict(index=index,position=xyz,reference_horizontal_m=dist,
                           user_waypoint_3d_m=target_dist,vtable_rva=module_rva(memory,vtable),
                           transform_getter_rva=module_rva(memory,getter),
                           primary_query_eligible=primary_a!=b'\0' and primary_b==b'\0'))
        guards.extend(((entry_address,entry),(point+0x128,xyz_raw),(point+0x138,primary_a),(point+0x154,primary_b)))
        if memory.read(control+8,4) != strong_raw:
            raise ReadError('原生传送点引用计数改变，丢弃本轮研究')
    if (pointer_at(memory,memory.base+0x27c5dc8) != root or memory.read(root+0x258,16) != descriptor
            or any(memory.read(address,len(raw)) != raw for address,raw in guards)):
        raise ReadError('传送点列表在采样期间改变')
    controller = pointer_at(memory,memory.base+0x27c3ae8)  # BA46D0全局控制器
    vtable = pointer_at(memory,controller)
    methods = {hex(slot):module_rva(memory,pointer_at(memory,vtable+slot)) for slot in (0x98,0xa0)}
    state_raw = memory.read(controller+0xf8,4)  # 825220本体+108；该接口指针为本体+10
    matrix_raw = memory.read(controller+0x100,64)  # 原生请求复制矩阵；不是人物当前位置
    matrix = struct.unpack('<16f',matrix_raw)
    if not all(math.isfinite(value) and abs(value)<1e7 for value in matrix):
        raise ReadError('原生请求矩阵异常')
    if (pointer_at(memory,memory.base+0x27c3ae8) != controller
            or pointer_at(memory,controller) != vtable
            or memory.read(controller+0xf8,4) != state_raw or memory.read(controller+0x100,64) != matrix_raw):
        raise ReadError('原生请求在只读采样期间变化')
    nearest_reference = sorted(points,key=lambda p:p['reference_horizontal_m'])[:3]
    nearest_waypoint = sorted(points,key=lambda p:p['user_waypoint_3d_m'])[:3] if waypoint else []
    return dict(total_entries=(end-begin)//16,active_points=len(points),registered_points=points,
                nearest_real_tent_candidates=nearest_reference,nearest_user_waypoint_candidates=nearest_waypoint,
                controller_vtable_rva=module_rva(memory,vtable),controller_methods=methods,
                native_request_state=struct.unpack('<I',state_raw)[0],
                last_native_request_position=matrix[12:15],
                waypoint=waypoint.marker_position if waypoint else None,
                disclaimer='距离及方法地址为只读研究，尚未验证可写落点字段或创建协议')


def run():
    memory = ProcessReader()
    report = dict(timestamp=time.time(),write_attempted=False,status='not_started')
    try:
        memory.connect()
        report.update(status='research_only',result=inspect_points(memory))
    except Exception as exc:
        report.update(status='stopped',error=str(exc))
    finally:
        memory.close()
        report['handle_closed'] = memory.handle is None
        (config.ROOT/f'native_points_{int(report["timestamp"])}.json').write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return report


if __name__ == '__main__':
    run()
