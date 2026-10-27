"""当前构建原生移动请求的数据快照；只有阶段2且保留时间充足时允许单次目标写入。"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import math
import struct

from memory.process_reader import ReadError,ProcessAccessError,MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.player_research import pointer_at


class RequestChanging(ReadError):
    """采样跨过原生请求转换；只读观察可丢弃该帧，写入路径仍直接停止。"""
    pass


@dataclass(frozen=True)
class NativeRequest:
    controller: int
    map_manager: int
    state: int
    remaining: float
    selection_id: int
    matrix: bytes

    @property
    def position(self):
        return struct.unpack_from('<3f',self.matrix,48)


def read_request(memory):
    if memory.sha256 != config.EXPECTED_SHA256:
        raise ReadError('原生请求仅支持精确构建')
    controller = pointer_at(memory,memory.base+0x27c3ae8)
    vtable = pointer_at(memory,controller)
    if (vtable-memory.base != 0x1c2a208 or pointer_at(memory,vtable+0x98)-memory.base != 0x824c00
            or pointer_at(memory,vtable+0xa0)-memory.base != 0x8254b0):
        raise ReadError('原生控制器类型或方法变化')
    state_raw = memory.read(controller+0xf8,4)
    state, = struct.unpack('<I',state_raw)
    remaining, = struct.unpack('<f',memory.read(controller+0x148,4))
    matrix = memory.read(controller+0x100,64)
    values = struct.unpack('<16f',matrix)
    manager = pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE)
    selection_raw = memory.read(manager+0x90,8)  # B609F0中的最后快速移动记录ID
    selection, = struct.unpack('<Q',selection_raw)
    if not 0 <= state <= 9 or not math.isfinite(remaining) or abs(remaining)>1000:
        raise ReadError('原生请求状态或计时异常')
    if not all(math.isfinite(v) and abs(v)<1e7 for v in values):
        raise ReadError('原生请求矩阵异常')
    if (pointer_at(memory,memory.base+0x27c3ae8) != controller
            or memory.read(controller+0xf8,4) != state_raw or memory.read(controller+0x100,64) != matrix
            or pointer_at(memory,memory.base+config.WAYPOINT_MANAGER_CANDIDATE) != manager
            or memory.read(manager+0x90,8) != selection_raw):
        raise RequestChanging('原生请求或选择在采样时变化')
    return NativeRequest(controller,manager,state,remaining,selection,matrix)


def redirect_bytes(request,target):
    """纯计划：不写状态、不改变矩阵朝向，只替换目标XYZ；晚于阶段2绝不补写。"""
    if request.state != 2 or request.remaining < config.NATIVE_REDIRECT_MIN_REMAINING:
        raise ReadError('错过原生请求早期窗口，不改已开始加载的目标')
    if len(target) != 3 or not all(math.isfinite(v) and abs(v)<1e6 for v in target):
        raise ReadError('原生请求目标坐标异常')
    return struct.pack('<3f',*target)


def write_target_once(memory,request,target,*,on_attempt=None):
    """唯一写地址为已验证控制器请求矩阵的XYZ；不调用函数或改人物/帐篷实体。"""
    replacement = redirect_bytes(request,target)
    api = memory.api
    api.GetProcessTimes.argtypes = [W.HANDLE]+[C.POINTER(W.FILETIME)]*4
    api.GetProcessTimes.restype = W.BOOL
    api.WriteProcessMemory.argtypes = [W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    api.WriteProcessMemory.restype = W.BOOL
    handle = api.OpenProcess(0x438,False,memory.pid)
    if not handle:
        raise ProcessAccessError('open_native_request_trial',C.get_last_error())
    try:
        def creation(h):
            values = [W.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(h,*(C.byref(v) for v in values)):
                raise ProcessAccessError('native_trial_process_times',C.get_last_error())
            return values[0].dwHighDateTime,values[0].dwLowDateTime
        if not memory.alive() or creation(handle) != creation(memory.handle):
            raise ReadError('游戏已退出或PID已复用')
        fresh = read_request(memory)
        if (fresh.controller != request.controller or fresh.map_manager != request.map_manager
                or fresh.selection_id != request.selection_id or fresh.matrix != request.matrix):
            raise ReadError('原生请求已改变，取消写入')
        redirect_bytes(fresh,target)
        address = request.controller+0x130
        mbi = MEMORY_BASIC_INFORMATION()
        if api.VirtualQueryEx(handle,address,C.byref(mbi),C.sizeof(mbi)) != C.sizeof(mbi):
            raise ProcessAccessError('query_native_request_region',C.get_last_error())
        if (mbi.State != 0x1000 or mbi.Protect != 4
                or not mbi.BaseAddress <= address < address+12 <= mbi.BaseAddress+mbi.RegionSize):
            raise ReadError('原生请求目标不在普通已提交读写页')
        # 再核对阶段与计时。外部读写无法与游戏线程原子同步，因此仍为受控实验。
        fresh = read_request(memory)
        if (fresh.controller != request.controller or fresh.selection_id != request.selection_id
                or fresh.matrix != request.matrix):
            raise ReadError('提交前原生请求变化，停止')
        redirect_bytes(fresh,target)
        buffer = C.create_string_buffer(replacement,12)
        count = C.c_size_t()
        if on_attempt is not None:
            on_attempt()
        if not api.WriteProcessMemory(handle,address,buffer,12,C.byref(count)) or count.value != 12:
            raise ProcessAccessError('write_native_target_once_no_retry',C.get_last_error())
        return dict(requested=struct.unpack('<3f',replacement),observed=struct.unpack('<3f',memory.read(address,12)))
    finally:
        api.CloseHandle(handle)
