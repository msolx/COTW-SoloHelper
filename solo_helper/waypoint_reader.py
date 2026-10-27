"""按当前构建用户航点固定ID读取，禁止用附近其它标记充当航点。"""
from dataclasses import dataclass
import math
import struct

from memory.process_reader import ReadError, valid_pointer
from solo_helper import config
from solo_helper.player_research import pointer_at


@dataclass(frozen=True)
class UserWaypoint:
    marker_position: tuple[float, float, float]
    # BE5F60将输入Y先限制到至少1024，再加2；低于边界时无法逆推出实际地面。
    input_height_candidate: float | None
    marker_id: int
    kind_flags: int

    @property
    def safe_ground_verified(self):
        # 标记只表达地图/瞄准查询结果，不能证明水域、障碍或目标区碰撞加载完整。
        return False


def marker_count(raw):
    if len(raw) != 24:
        raise ValueError('标记列表描述符长度错误')
    begin, end, capacity = struct.unpack('<3Q', raw)
    if begin == end == capacity == 0:
        return begin, 0
    if (not all(valid_pointer(v) for v in (begin, end, capacity)) or not begin <= end <= capacity
            or (end - begin) % 0x100 or (capacity - begin) % 0x100
            or (capacity - begin) // 0x100 > config.WAYPOINT_MAX_MARKERS):
        raise ValueError('候选地图标记列表边界异常；不遍历')
    return begin, (end - begin) // 0x100


def read_user_waypoint(memory):
    if not config.is_compatible_build(memory.sha256):
        raise ReadError('航点读取不支持当前EXE哈希')
    manager = pointer_at(memory, memory.base + config.WAYPOINT_MANAGER_CANDIDATE)
    descriptor = memory.read(manager + 0x70, 24)
    begin, count = marker_count(descriptor)
    matches = []
    for index in range(count):
        record = begin + index * 0x100
        identity = memory.read(record + 0x30, 8)
        if struct.unpack('<Q', identity)[0] != config.USER_WAYPOINT_ID:
            continue
        position_raw = memory.read(record + 0x20, 12)
        position = struct.unpack('<3f', position_raw)
        flags, = struct.unpack('<I', memory.read(record + 0x60, 4))
        if flags & 0xff != 0x0a or not all(math.isfinite(v) and abs(v) <= 1e6 for v in position):
            raise ReadError('用户航点ID匹配但类型或坐标异常')
        if memory.read(record + 0x30, 8) != identity or memory.read(record + 0x20, 12) != position_raw:
            raise ReadError('用户航点在采样中改变')
        # 2.0/1024.0均来自BE5F60实际常量。1026附近包括clamp后的未知高度。
        input_y = position[1] - 2.0 if position[1] > 1026.01 else None
        matches.append(UserWaypoint(position, input_y, config.USER_WAYPOINT_ID, flags))
    if (memory.read(manager + 0x70, 24) != descriptor
            or pointer_at(memory, memory.base + config.WAYPOINT_MANAGER_CANDIDATE) != manager):
        raise ReadError('读取航点期间地图标记场景改变')
    if len(matches) > 1:
        raise ReadError('用户航点ID重复，不选择任意一条')
    return matches[0] if matches else None
