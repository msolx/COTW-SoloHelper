"""仅清除当前保护区已有的实际压力图；不隐藏颜色、不修改存档文件或其它保护区。"""
from dataclasses import dataclass
from collections import Counter
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import struct
import time

from memory.process_reader import ProcessReader,ReadError,ProcessAccessError,valid_pointer,MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.player_research import pointer_at
from solo_helper.sdf_mesh_research import read_bounded_buffer
from solo_helper.trial_guard import position_trial_guard


@dataclass(frozen=True)
class PressureSnapshot:
    manager: int
    pressure: int
    active: int
    map_count: int
    data_address: int
    data: bytes
    guards: tuple
    dirty: int

    def summary(self):
        counts=Counter(self.data)
        return dict(reserve_slot=self.active,map_slots=self.map_count,width=256,height=256,
                    nonzero_cells=sum(n for value,n in counts.items() if value),max_value=max(self.data),
                    histogram=dict(sorted(counts.items())),data_sha256=hashlib.sha256(self.data).hexdigest())


def read_pressure(memory):
    if memory.sha256!=config.EXPECTED_SHA256:
        raise ReadError('狩猎压力构建不匹配')
    # 只校验固定构建的原生查询/纹理更新标记指令，不执行它们。
    code_guards=((memory.base+0x920b30,bytes.fromhex('48895150c6417c01c3')),
                 (memory.base+0x8fd400,bytes.fromhex('488b4350488d1440488b4358488b04d00fb60401')))
    if any(memory.read(address,len(raw))!=raw for address,raw in code_guards):
        raise ReadError('压力查询或更新布局已改变')
    manager=pointer_at(memory,memory.base+0x27c5dc8)
    pressure=pointer_at(memory,manager+0xf0)
    reserve_raw=memory.read(manager+0x68,4)  # 976674..97667F传入当前地图编号。
    dimensions=memory.read(pressure+0x40,8)
    if struct.unpack('<2I',dimensions)!=(256,256):
        raise ReadError('当前压力图尺寸未验证')
    active_raw=memory.read(pressure+0x50,8)
    active=struct.unpack('<Q',active_raw)[0]
    descriptor=memory.read(pressure+0x58,24)
    begin,end,capacity=struct.unpack('<3Q',descriptor)
    if (not all(map(valid_pointer,(begin,end,capacity))) or not begin<end<=capacity
            or (end-begin)%24 or (capacity-begin)%24
            or not 1<=(end-begin)//24<=(capacity-begin)//24<=64
            or active>=(end-begin)//24 or active!=struct.unpack('<I',reserve_raw)[0]):
        raise ReadError('活动压力图与当前保护区不一致')
    layer_address=begin+active*24
    layer=memory.read(layer_address,24)
    data,stop,cap=struct.unpack('<3Q',layer)
    if not all(map(valid_pointer,(data,stop,cap))) or not data<stop<=cap or stop-data!=65536 or cap-data>512*1024:
        raise ReadError('当前保护区压力缓冲区边界异常')
    dirty=memory.read(pressure+0x7c,1)[0]
    if dirty not in (0,1):
        raise ReadError('压力纹理更新状态未验证')
    guards=code_guards+((memory.base+0x27c5dc8,struct.pack('<Q',manager)),
              (manager+0xf0,struct.pack('<Q',pressure)),(manager+0x68,reserve_raw),
              (pressure+0x40,dimensions),(pressure+0x50,active_raw),(pressure+0x58,descriptor),
              (layer_address,layer))
    payload=read_bounded_buffer(memory,data,65536)
    if any(memory.read(address,len(raw))!=raw for address,raw in guards):
        raise ReadError('压力图在读取期间切换或重新分配')
    return PressureSnapshot(manager,pressure,active,(end-begin)//24,data,payload,guards,dirty)


def clear_snapshot_once(memory,snapshot,*,on_attempt=None):
    """只写本次活动图中的非零块和原生dirty标记；失败不自动重试或回写旧压力。"""
    fresh=read_pressure(memory)
    if ((fresh.manager,fresh.pressure,fresh.active,fresh.data_address)!=(
            snapshot.manager,snapshot.pressure,snapshot.active,snapshot.data_address)
            or fresh.guards!=snapshot.guards or fresh.data!=snapshot.data):
        raise ReadError('压力数据或保护区已改变，本次未清除')
    if not any(snapshot.data):
        return dict(write_attempted=False,data_bytes_written=0,dirty_marked=False)
    api=memory.api
    api.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
    api.GetProcessTimes.restype=W.BOOL
    api.WriteProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    api.WriteProcessMemory.restype=W.BOOL
    handle=api.OpenProcess(0x438,False,memory.pid)
    if not handle:
        raise ProcessAccessError('open_pressure_clear',C.get_last_error())
    written=0
    try:
        def creation(h):
            values=[W.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(h,*(C.byref(v) for v in values)):
                raise ProcessAccessError('pressure_process_times',C.get_last_error())
            return values[0].dwHighDateTime,values[0].dwLowDateTime
        if not memory.alive() or creation(handle)!=creation(memory.handle):
            raise ReadError('游戏已退出或进程身份改变')
        def write_owned(address,expected,replacement,*,dirty=False):
            if not memory.alive() or any(memory.read(a,len(raw))!=raw for a,raw in snapshot.guards):
                raise ReadError('清除过程中压力图或保护区改变，立即停止')
            actual=memory.read(address,len(expected))
            if (not dirty and actual!=expected) or (dirty and actual not in (b'\0',b'\1')):
                raise ReadError('压力数据在提交前改变，停止本轮清除')
            mbi=MEMORY_BASIC_INFORMATION()
            if api.VirtualQueryEx(handle,address,C.byref(mbi),C.sizeof(mbi))!=C.sizeof(mbi):
                raise ProcessAccessError('query_pressure_region',C.get_last_error())
            if (mbi.State!=0x1000 or mbi.Protect!=4 or
                    not mbi.BaseAddress<=address<address+len(replacement)<=mbi.BaseAddress+mbi.RegionSize):
                raise ReadError('压力数据不在普通已提交读写内存区域')
            # 检查后不修改页保护；不追写、不循环冻结压力。
            if any(memory.read(a,len(raw))!=raw for a,raw in snapshot.guards):
                raise ReadError('压力写入前身份校验失败')
            buffer=C.create_string_buffer(replacement,len(replacement))
            count=C.c_size_t()
            if on_attempt:
                on_attempt(address,len(replacement),dirty)
            if not api.WriteProcessMemory(handle,address,buffer,len(replacement),C.byref(count)) or count.value!=len(replacement):
                raise ProcessAccessError('write_pressure_once_no_retry',C.get_last_error())
            if not dirty and memory.read(address,len(replacement))!=replacement:
                raise ReadError('压力清除复读不一致，未重试')
        for offset in range(0,65536,8192):
            raw=snapshot.data[offset:offset+8192]
            if any(raw):
                write_owned(snapshot.data_address+offset,raw,bytes(len(raw)))
                written+=len(raw)
        # 920B30原生设置7C为1；92B4F0消费它并调用92B890刷新纹理，随后清零。
        write_owned(snapshot.pressure+0x7c,bytes((snapshot.dirty,)),b'\1',dirty=True)
        return dict(write_attempted=True,data_bytes_written=written,dirty_marked=True)
    finally:
        api.CloseHandle(handle)


def run_clear(*,singleplayer_confirmed=False,approved=False):
    if not (singleplayer_confirmed and approved):
        raise ReadError('清除已有压力需要本机单人确认和本次操作授权')
    memory=ProcessReader()
    report=dict(kind='clear_current_reserve_pressure',timestamp=time.time(),write_attempted=False,
                save_files_written=False,other_reserves_modified=False,generation_disabled=False)
    with position_trial_guard():
        try:
            memory.connect()
            from solo_helper.native_request import read_request
            from solo_helper.physics_research import read_physics_position
            from solo_helper.position_trial import local_object
            read_physics_position(memory,local_object(memory))
            if read_request(memory).state!=0:
                raise ReadError('正在快速移动/加载，暂不清除压力')
            before=read_pressure(memory)
            report['before']=before.summary()
            def attempted(address,size,dirty):
                report['write_attempted']=True
                report.setdefault('writes',[]).append(dict(size=size,kind='refresh_flag' if dirty else 'current_map_data'))
            report['operation']=clear_snapshot_once(memory,before,on_attempt=attempted)
            after=read_pressure(memory)
            report['after']=after.summary()
            report['status']='cleared_current_reserve_pressure' if (after.active==before.active and not any(after.data)) else 'clear_not_confirmed'
        except Exception as exc:
            report.update(status='stopped',error=str(exc))
            if isinstance(exc,ProcessAccessError):
                report['access_error']=dict(stage=exc.stage,winerror=exc.winerror)
        finally:
            memory.close()
            report['handle_closed']=memory.handle is None
            (config.ROOT/f'pressure_clear_{int(report["timestamp"])}.json').write_text(
                json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def preview_current_pressure():
    memory=ProcessReader()
    report=dict(kind='pressure_preview',timestamp=time.time(),write_attempted=False)
    try:
        memory.connect()
        report.update(status='pressure_readonly',pressure=read_pressure(memory).summary())
    except Exception as exc:
        report.update(status='stopped',error=str(exc))
        if isinstance(exc,ProcessAccessError):
            report['access_error']=dict(stage=exc.stage,winerror=exc.winerror)
    finally:
        memory.close()
        report['handle_closed']=memory.handle is None
    return report
