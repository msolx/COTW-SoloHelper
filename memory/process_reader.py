"""只打开指定游戏，权限固定为 QUERY_INFORMATION | VM_READ。无写入或提权路径。"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from config import PROCESS_NAME, MAX_READ_BYTES

class ReadError(RuntimeError):
    pass

class GameNotRunning(ReadError):
    """正常退出/未启动与权限、结构失败区分，允许低频等待游戏重新启动。"""
    pass

class ProcessAccessError(ReadError):
    """保留具体失败 API 和 Windows 错误码，不依赖中文文本判断权限错误。"""
    def __init__(self, stage, winerror):
        self.stage, self.winerror = stage, winerror
        reason = '只读访问被拒绝，停止连接' if winerror == 5 else 'Windows API 调用失败'
        super().__init__(f'{reason}：{stage}；Windows {winerror}')

def valid_pointer(address):
    return isinstance(address, int) and 0x10000 <= address <= 0x7FFFFFFFFFFF

class MODULEENTRY32W(C.Structure):
    _fields_ = [('dwSize', W.DWORD), ('th32ModuleID', W.DWORD), ('th32ProcessID', W.DWORD),
                ('GlblcntUsage', W.DWORD), ('ProccntUsage', W.DWORD),
                ('modBaseAddr', C.POINTER(C.c_byte)), ('modBaseSize', W.DWORD),
                ('hModule', W.HMODULE), ('szModule', W.WCHAR*256), ('szExePath', W.WCHAR*260)]

class PROCESSENTRY32W(C.Structure):
    _fields_ = [('dwSize', W.DWORD), ('cntUsage', W.DWORD), ('th32ProcessID', W.DWORD),
                ('th32DefaultHeapID', C.c_size_t), ('th32ModuleID', W.DWORD),
                ('cntThreads', W.DWORD), ('th32ParentProcessID', W.DWORD),
                ('pcPriClassBase', W.LONG), ('dwFlags', W.DWORD), ('szExeFile', W.WCHAR*260)]

class MEMORY_BASIC_INFORMATION(C.Structure):
    _fields_ = [('BaseAddress', C.c_void_p), ('AllocationBase', C.c_void_p),
                ('AllocationProtect', W.DWORD), ('PartitionId', W.WORD),
                ('RegionSize', C.c_size_t), ('State', W.DWORD),
                ('Protect', W.DWORD), ('Type', W.DWORD)]

class ProcessReader:
    def __init__(self):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise ReadError('需要 Windows 64 位 Python')
        self.api = C.WinDLL('kernel32', use_last_error=True)
        # 显式声明所有指针参数，避免 64 位句柄/地址被 ctypes 默认 int 截断。
        signatures = {
            'CreateToolhelp32Snapshot': ([W.DWORD, W.DWORD], W.HANDLE),
            'Process32FirstW': ([W.HANDLE,C.POINTER(PROCESSENTRY32W)], W.BOOL),
            'Process32NextW': ([W.HANDLE,C.POINTER(PROCESSENTRY32W)], W.BOOL),
            'Module32FirstW': ([W.HANDLE,C.POINTER(MODULEENTRY32W)], W.BOOL),
            'Module32NextW': ([W.HANDLE,C.POINTER(MODULEENTRY32W)], W.BOOL),
            'OpenProcess': ([W.DWORD,W.BOOL,W.DWORD], W.HANDLE),
            'CloseHandle': ([W.HANDLE], W.BOOL),
            'ReadProcessMemory': ([W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL),
            'VirtualQueryEx': ([W.HANDLE,C.c_void_p,C.POINTER(MEMORY_BASIC_INFORMATION),C.c_size_t],C.c_size_t),
            'WaitForSingleObject': ([W.HANDLE,W.DWORD],W.DWORD),
            'GetExitCodeProcess': ([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        }
        for name,(args,result) in signatures.items():
            fn = getattr(self.api,name)
            fn.argtypes, fn.restype = args,result
        self.handle = None
        self.pid = None
        self.base = 0
        self.path = ''
        self.stage = 'initialized'

    def _snapshot(self, flags, pid=0):
        self.stage = 'process_snapshot' if flags == 2 else 'module_snapshot'
        handle = self.api.CreateToolhelp32Snapshot(flags,pid)
        if handle == C.c_void_p(-1).value:
            error = C.get_last_error()
            raise ProcessAccessError(self.stage,error)
        return handle

    def _enumeration_call(self, function, snapshot, entry, stage):
        self.stage = stage
        C.set_last_error(0)
        if function(snapshot,C.byref(entry)):
            return True
        error = C.get_last_error()
        if error == 18:  # ERROR_NO_MORE_FILES：唯一正常的枚举结束条件。
            return False
        raise ProcessAccessError(stage,error)

    def connect(self):
        self.close()
        snap = self._snapshot(2)
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = C.sizeof(entry)
            found = self._enumeration_call(self.api.Process32FirstW,snap,entry,'process_first')
            matches = []
            while found:
                if entry.szExeFile.casefold() == PROCESS_NAME.casefold():
                    matches.append(entry.th32ProcessID)
                found = self._enumeration_call(self.api.Process32NextW,snap,entry,'process_next')
            if not matches:
                raise GameNotRunning('未找到游戏进程，等待重新启动')
            if len(matches) > 1:
                raise ReadError('存在多个游戏进程，请只保留一个')
            self.pid = matches[0]
        finally:
            self.api.CloseHandle(snap)
        try:
            snap = self._snapshot(0x18,self.pid)
            try:
                module = MODULEENTRY32W()
                module.dwSize = C.sizeof(module)
                found = self._enumeration_call(self.api.Module32FirstW,snap,module,'module_first')
                while found:
                    if module.szModule.casefold() == PROCESS_NAME.casefold():
                        self.base = C.cast(module.modBaseAddr,C.c_void_p).value
                        self.path = module.szExePath
                        break
                    found = self._enumeration_call(self.api.Module32NextW,snap,module,'module_next')
            finally:
                self.api.CloseHandle(snap)
            if not self.base:
                raise ReadError('无法获取游戏主模块')
            self.stage = 'open_process_readonly'
            self.handle = self.api.OpenProcess(0x410,False,self.pid)
            if not self.handle:
                raise ProcessAccessError(self.stage,C.get_last_error())
            self.stage = 'hash_executable'
            with open(self.path,'rb') as stream:
                self.sha256 = hashlib.file_digest(stream,'sha256').hexdigest()
            self.stage = 'connected'
        except Exception:
            self.close()
            raise

    def alive(self):
        code = W.DWORD()
        return bool(self.handle and self.api.GetExitCodeProcess(self.handle,C.byref(code)) and code.value == 259)

    def read(self,address,size):
        if not valid_pointer(address) or not 0 < size <= MAX_READ_BYTES or not valid_pointer(address+size-1):
            raise ReadError('无效地址或读取长度')
        if not self.alive():
            self.close()
            raise GameNotRunning('游戏已退出')
        # 可以跨连续可读区域，但每一段都必须 committed 且没有 guard/noaccess。
        cursor, end = address,address+size
        while cursor < end:
            mbi = MEMORY_BASIC_INFORMATION()
            if self.api.VirtualQueryEx(self.handle,cursor,C.byref(mbi),C.sizeof(mbi)) != C.sizeof(mbi):
                raise ProcessAccessError('query_memory_region',C.get_last_error())
            if mbi.State != 0x1000 or mbi.Protect & 0x101 or (mbi.Protect & 0xFF) not in (2,4,8,0x20,0x40,0x80):
                raise ReadError('目标地址不是可读的已提交内存')
            next_address = mbi.BaseAddress + mbi.RegionSize
            if next_address <= cursor:
                raise ReadError('异常内存区域')
            cursor = min(end,next_address)
        buffer = C.create_string_buffer(size)
        count = C.c_size_t()
        if not self.api.ReadProcessMemory(self.handle,address,buffer,size,C.byref(count)) or count.value != size:
            raise ProcessAccessError('read_process_memory',C.get_last_error())
        return buffer.raw

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
        self.handle, self.pid, self.base, self.path = None,None,0,''
