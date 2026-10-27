"""用户航点的临时帐篷图标租用；仅改类型字节，完成或取消后恢复，不创建实体。"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import math
import struct

from memory.process_reader import ReadError,ProcessAccessError,MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.player_research import pointer_at
from solo_helper.waypoint_reader import marker_count
from solo_helper.native_request import read_request


class MarkerUnavailable(ReadError):
    pass


@dataclass(frozen=True)
class MarkerBinding:
    manager: int
    record: int
    position_raw: bytes
    flags: bytes

    @property
    def position(self):
        return struct.unpack('<3f',self.position_raw)


def find_marker(memory,identity,kinds=None):
    if not config.is_compatible_build(memory.sha256):
        raise ReadError('临时航点图标仅支持精确构建')
    manager = pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE)
    descriptor = memory.read(manager+0x70,24)
    begin,count = marker_count(descriptor)
    if count>config.TRAVEL_RESEARCH_MAX_MARKERS:
        raise ReadError('地图标记超出临时图标研究上限')
    matches = []
    for index in range(count):
        record = begin+index*0x100
        if struct.unpack('<Q',memory.read(record+0x30,8))[0] != identity:
            continue
        position_raw = memory.read(record+0x20,12)
        flags = memory.read(record+0x60,4)
        position = struct.unpack('<3f',position_raw)
        if not all(math.isfinite(v) and abs(v)<1e6 for v in position):
            raise ReadError('临时图标坐标异常')
        if kinds is not None and flags[0] not in kinds:
            raise MarkerUnavailable('指定图标类型已改变，不接管其它类型')
        if (memory.read(record+0x30,8) != struct.pack('<Q',identity)
                or memory.read(record+0x20,12) != position_raw or memory.read(record+0x60,4) != flags):
            raise ReadError('地图图标在采样期间改变')
        matches.append(MarkerBinding(manager,record,position_raw,flags))
    if (pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE) != manager
            or memory.read(manager+0x70,24) != descriptor):
        raise ReadError('地图标记场景在采样期间改变')
    if len(matches)!=1:
        raise MarkerUnavailable('指定图标不是唯一现存记录')
    return matches[0]


def write_owned_field_once(memory,address,expected,replacement,guard):
    """租用器私有写入：仅支持1字节类型或8字节会话引用；身份及地址由guard重新定位。"""
    if len(expected)!=len(replacement) or len(expected) not in (1,8):
        raise ReadError('临时图标拒绝超出类型/会话引用的字段长度')
    api = memory.api
    api.GetProcessTimes.argtypes = [W.HANDLE]+[C.POINTER(W.FILETIME)]*4
    api.GetProcessTimes.restype = W.BOOL
    api.WriteProcessMemory.argtypes = [W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    api.WriteProcessMemory.restype = W.BOOL
    handle = api.OpenProcess(0x438,False,memory.pid)
    if not handle:
        raise ProcessAccessError('open_virtual_marker_lease',C.get_last_error())
    try:
        def creation(h):
            times = [W.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(h,*(C.byref(v) for v in times)):
                raise ProcessAccessError('virtual_marker_process_times',C.get_last_error())
            return times[0].dwHighDateTime,times[0].dwLowDateTime
        if not memory.alive() or creation(handle)!=creation(memory.handle):
            raise ReadError('游戏已退出或进程实例改变，不写入图标')
        guard()
        mbi = MEMORY_BASIC_INFORMATION()
        if api.VirtualQueryEx(handle,address,C.byref(mbi),C.sizeof(mbi))!=C.sizeof(mbi):
            raise ProcessAccessError('query_virtual_marker_region',C.get_last_error())
        if (mbi.State!=0x1000 or mbi.Protect!=4
                or not mbi.BaseAddress<=address<address+len(expected)<=mbi.BaseAddress+mbi.RegionSize):
            raise ReadError('临时图标字段不是普通已提交读写页')
        guard()
        if memory.read(address,len(expected))!=expected:
            raise ReadError('临时图标字段变化，不覆盖其它操作')
        buf = C.create_string_buffer(replacement,len(replacement))
        written = C.c_size_t()
        if not api.WriteProcessMemory(handle,address,buf,len(replacement),C.byref(written)) or written.value!=len(replacement):
            raise ProcessAccessError('write_virtual_marker_once_no_retry',C.get_last_error())
        if memory.read(address,len(replacement))!=replacement:
            raise ReadError('临时图标回读不匹配，不重复写入')
    finally:
        api.CloseHandle(handle)


class TemporaryTentMarker:
    def __init__(self,memory,waypoint):
        self.memory,self.waypoint = memory,waypoint
        self.original = None
        self.previous_selection = None
        self.changed = False
        self.restoration = None

    def acquire(self,*,approved=False):
        if not approved:
            raise ReadError('临时帐篷图标需要独立执行审批')
        memory = self.memory
        initial = read_request(memory)
        if initial.state!=0:
            raise ReadError('原生请求正在执行，不转换图标')
        original = find_marker(memory,config.USER_WAYPOINT_ID,(10,))
        if original.position!=self.waypoint.marker_position:
            raise ReadError('用户航点与已确认目标不同')
        if initial.map_manager!=original.manager or initial.selection_id==config.USER_WAYPOINT_ID:
            raise ReadError('前一轮图标会话未清理，不能重新租用')
        self.original,self.previous_selection = original,initial.selection_id
        def guard():
            fresh = find_marker(memory,config.USER_WAYPOINT_ID,(10,))
            if (fresh.manager!=original.manager or fresh.record!=original.record
                    or fresh.position_raw!=original.position_raw or read_request(memory).state!=0):
                raise ReadError('图标或请求场景改变，未转换')
        # 在实际调用前标记清理责任，即使发生部分失败也只按当前自有值决定是否恢复。
        self.changed = True
        try:
            write_owned_field_once(memory,original.record+0x60,b'\x0a',b'\x28',guard)
        except ProcessAccessError as exc:
            self.restoration = dict(status='not_retried_after_api_error',marker_restored=False,
                                    selection_restored=False,error=str(exc))
            raise
        self.validate()
        return dict(original_kind=10,temporary_kind=40,entity_created=False)

    def validate(self):
        current = find_marker(self.memory,config.USER_WAYPOINT_ID,(40,))
        if (self.original is None or current.manager!=self.original.manager
                or current.position_raw!=self.original.position_raw):
            raise ReadError('临时航点已移动或场景改变，停止租用')
        # 忽略正常鼠标选中状态的高字节变化，仅验证本工具拥有的类型字节和位置。
        return self.waypoint

    def restore(self):
        try:
            return self._restore_once()
        except Exception as exc:
            if self.restoration is not None:
                self.restoration.update(status='restore_failed_no_retry',error=str(exc))
            raise

    def _restore_once(self):
        if self.restoration is not None:
            return self.restoration  # 不在权限拒绝后反复尝试恢复
        result = dict(marker_restored=False,selection_restored=False)
        self.restoration = result
        if not self.changed or self.original is None:
            result['status'] = 'nothing_changed'
            return result
        memory = self.memory
        if not memory.alive():
            result['status'] = 'process_unavailable_no_stale_write'
            return result
        manager = pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE)
        if manager!=self.original.manager:
            result['status'] = 'context_changed_no_stale_write'
            return result
        try:
            current = find_marker(memory,config.USER_WAYPOINT_ID,(10,40))
        except MarkerUnavailable:
            current = None
        if current and current.position_raw==self.original.position_raw:
            if current.flags[0]==40:
                def guard():
                    fresh = find_marker(memory,config.USER_WAYPOINT_ID,(40,))
                    if fresh.manager!=manager or fresh.record!=current.record or fresh.position_raw!=self.original.position_raw:
                        raise ReadError('恢复图标前身份改变，不写旧指针')
                write_owned_field_once(memory,current.record+0x60,b'\x28',b'\x0a',guard)
            result['marker_restored'] = True
        # 只清理仍然指向本工具用户航点的会话引用；真实新请求的ID绝不覆盖。
        selected = memory.read(manager+0x90,8)
        owned = struct.pack('<Q',config.USER_WAYPOINT_ID)
        if selected==owned:
            previous = self.previous_selection
            if previous:
                try:
                    old = find_marker(memory,previous,(29,40,46,62))
                    if old.manager!=manager:
                        previous = 0
                except MarkerUnavailable:
                    previous = 0  # 原ID已卸载时清除自有引用，不恢复已不存在的对象ID
            def guard_selection():
                if (pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE)!=manager
                        or memory.read(manager+0x90,8)!=owned):
                    raise ReadError('会话引用已被其它操作更换，不覆盖')
            write_owned_field_once(memory,manager+0x90,owned,struct.pack('<Q',previous or 0),guard_selection)
            result['selection_restored'] = True
        result['status'] = 'restored' if result['marker_restored'] else 'marker_missing_or_changed'
        return result
