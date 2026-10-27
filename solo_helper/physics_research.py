"""当前精确构建的位置同步研究：仅追踪本地人物对应的一个物理体。"""
import math
import struct

from memory.process_reader import ReadError
from solo_helper import config
from solo_helper.player_research import pointer_at


def read_physics_position(memory, obj):
    # 来源：6A47E0 -> 24F010 -> FF2FC0。这些是离线指令依据，绝不调用它们。
    if not config.is_compatible_build(memory.sha256):
        raise ReadError('物理研究仅允许已核对哈希')
    component = pointer_at(memory, obj + 0x1ac8)
    controller = pointer_at(memory, component + 0xc0)
    world = pointer_at(memory, controller + 0x20)
    body_id_raw = memory.read(controller + 0x10, 4)
    body_id, = struct.unpack('<i', body_id_raw)
    # 24F080使用world+2C的低30位作为索引边界；只读一个元素，不遍历物理场景。
    capacity_raw = memory.read(world + 0x2c, 4)
    capacity = struct.unpack('<I', capacity_raw)[0] & 0x3fffffff
    if not 0 <= body_id < capacity <= config.PHYSICS_MAX_BODY_CAPACITY:
        raise ReadError('人物物理体索引超出验证边界')
    bodies = pointer_at(memory, world + 0x20)
    body = bodies + body_id * 0x90
    flags, = struct.unpack('<I', memory.read(body + 0x40, 4))
    if not flags & 3:
        raise ReadError('人物物理体未分配或已释放')
    manager = pointer_at(memory, memory.base + 0x27a8320)
    global_world = pointer_at(memory, manager + 0x30)
    if global_world != world:
        raise ReadError('人物物理世界与游戏当前世界不一致')
    origin_raw = memory.read(manager + 0x1a064, 12)
    origin = struct.unpack('<3f', origin_raw)
    # 先固定原点再读局部位置，末尾再核对；否则旧局部位置可能与新原点拼接。
    transform = struct.unpack('<16f', memory.read(body, 64))
    local = transform[12:15]
    if not all(math.isfinite(v) and abs(v) < 1e7 for v in (*transform, *origin)):
        raise ReadError('人物物理坐标存在非有限值或异常范围')
    # 不能因多个小块分别可读就接受跨场景混合快照；重新核对所有链和原点。
    if (pointer_at(memory, obj + 0x1ac8) != component
            or pointer_at(memory, component + 0xc0) != controller
            or pointer_at(memory, controller + 0x20) != world
            or memory.read(controller + 0x10, 4) != body_id_raw
            or pointer_at(memory, world + 0x20) != bodies
            or memory.read(world + 0x2c, 4) != capacity_raw
            or pointer_at(memory, memory.base + 0x27a8320) != manager
            or memory.read(manager + 0x1a064, 12) != origin_raw):
        raise ReadError('人物物理场景或浮动原点在采样期间变化')
    motion_id, = struct.unpack('<i', memory.read(body + 0x68, 4))
    # FCFCC0用motion_id×128索引world+E0；先核对动态数组边界再读本人物一条。
    motion_descriptor = memory.read(world + 0xe0, 16)
    motions, motion_count, motion_capacity = struct.unpack('<Q2I', motion_descriptor)
    motion_capacity &= 0x3fffffff
    from memory.process_reader import valid_pointer
    if (not valid_pointer(motions) or not 0 < motion_id < motion_count <= motion_capacity
            or motion_capacity > config.PHYSICS_MAX_BODY_CAPACITY):
        raise ReadError('人物运动状态索引尚未通过边界验证')
    motion_position = struct.unpack('<4f', memory.read(motions + motion_id * 0x80, 16))
    if not all(math.isfinite(v) for v in motion_position):
        raise ReadError('人物运动状态位置异常')
    if (memory.read(body + 0x68, 4) != struct.pack('<i', motion_id)
            or memory.read(world + 0xe0, 16) != motion_descriptor
            or pointer_at(memory, memory.base + 0x27a8320) != manager
            or pointer_at(memory, manager + 0x30) != world
            or memory.read(manager + 0x1a064, 12) != origin_raw):
        raise ReadError('人物运动状态在采样期间变化')
    return dict(body_id=body_id, body_flags=flags, floating_origin=origin,
                local_position=local, world_position=[v + o for v, o in zip(local, origin)],
                motion_id=motion_id, motion_local_position=motion_position)
