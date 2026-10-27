"""临时类型租用的所有权、恢复和原生后备点解析；不访问真实游戏。"""
import struct
import ctypes as C
from ctypes import wintypes as W
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

from memory.process_reader import ReadError,ProcessAccessError,MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.native_request_trial import resolve_virtual_source
from solo_helper.virtual_tent_marker import MarkerBinding,MarkerUnavailable,TemporaryTentMarker,write_owned_field_once
from solo_helper.waypoint_reader import UserWaypoint


class VirtualTentMarkerTests(unittest.TestCase):
    def setUp(self):
        self.manager,self.original_record = 0x200000,0x300000
        self.old_id = 0xabcdef
        self.memory = SimpleNamespace(base=0x140000000,kind=10,high=b'\x02\x01\x01',
                                      record=self.original_record,position=struct.pack('<3f',100,1032,200),
                                      selection=self.old_id,alive=lambda:True,old_exists=True)
        self.memory.read = self.read
        self.writes = []
        self.waypoint = UserWaypoint((100,1032,200),1030,config.USER_WAYPOINT_ID,0x0101020a)
        for name,value in (('find_marker',self.find),('read_request',self.request),('write_owned_field_once',self.write)):
            p = patch('solo_helper.virtual_tent_marker.'+name,side_effect=value)
            p.start()
            self.addCleanup(p.stop)

    def read(self,address,size):
        if address==self.memory.base+config.WAYPOINT_MANAGER_CANDIDATE:
            return struct.pack('<Q',self.manager)
        if address==self.manager+0x90:
            return struct.pack('<Q',self.memory.selection)
        if address==self.memory.record+0x60 and size==1:
            return bytes([self.memory.kind])
        raise AssertionError((address,size))

    def find(self,memory,identity,kinds=None):
        if identity==config.USER_WAYPOINT_ID:
            kind,record,position = memory.kind,memory.record,memory.position
        elif identity==self.old_id and memory.old_exists:
            kind,record,position = 29,0x400000,struct.pack('<3f',110,1032,210)
        else:
            raise MarkerUnavailable('模拟记录不存在')
        if kinds and kind not in kinds:
            raise MarkerUnavailable('模拟类型改变')
        return MarkerBinding(self.manager,record,position,bytes([kind])+memory.high)

    def request(self,memory):
        return SimpleNamespace(state=0,map_manager=self.manager,selection_id=memory.selection)

    def write(self,memory,address,expected,replacement,guard):
        guard()
        self.assertEqual(memory.read(address,len(expected)),expected)
        self.writes.append((address,replacement))
        if address==memory.record+0x60:
            self.assertEqual(len(replacement),1)
            memory.kind = replacement[0]
        else:
            self.assertEqual(address,self.manager+0x90)
            memory.selection = struct.unpack('<Q',replacement)[0]

    def test_acquire_and_early_restore_preserve_game_selection_bits(self):
        lease = TemporaryTentMarker(self.memory,self.waypoint)
        lease.acquire(approved=True)
        self.assertEqual(self.memory.kind,40)
        self.assertEqual(lease.validate(),self.waypoint)
        self.memory.high = b'\x03\x01\x01'  # 游戏正常更新高字节选中态
        self.memory.selection = config.USER_WAYPOINT_ID
        result = lease.restore()
        self.assertEqual(self.memory.kind,10)
        self.assertEqual(self.memory.high,b'\x03\x01\x01')
        self.assertEqual(self.memory.selection,self.old_id)
        self.assertTrue(result['marker_restored'])
        self.assertTrue(result['selection_restored'])
        count = len(self.writes)
        lease.restore()
        self.assertEqual(len(self.writes),count)

    def test_new_real_selection_not_overwritten_and_reallocated_record_relocated(self):
        lease = TemporaryTentMarker(self.memory,self.waypoint)
        lease.acquire(approved=True)
        self.memory.record = 0x310000
        self.memory.selection = 0x777777
        lease.restore()
        self.assertEqual(self.writes[-1],(0x310060,b'\x0a'))
        self.assertEqual(self.memory.selection,0x777777)
        self.assertFalse(any(address==self.manager+0x90 for address,_ in self.writes))

    def test_changed_position_does_not_use_stale_pointer_and_missing_old_id_clears_owned_reference(self):
        lease = TemporaryTentMarker(self.memory,self.waypoint)
        lease.acquire(approved=True)
        self.memory.position = struct.pack('<3f',120,1032,200)
        self.memory.selection = config.USER_WAYPOINT_ID
        self.memory.old_exists = False
        with self.assertRaises(ReadError):
            lease.validate()
        result = lease.restore()
        self.assertFalse(result['marker_restored'])
        self.assertEqual(self.memory.selection,0)
        self.assertEqual(len([w for w in self.writes if len(w[1])==1]),1)

    def test_denial_not_retried_and_approval_required(self):
        lease = TemporaryTentMarker(self.memory,self.waypoint)
        with self.assertRaises(ReadError):
            lease.acquire()
        self.assertEqual(self.writes,[])
        with patch('solo_helper.virtual_tent_marker.write_owned_field_once',side_effect=ProcessAccessError('test',5)) as write:
            with self.assertRaises(ProcessAccessError):
                lease.acquire(approved=True)
            result = lease.restore()
            self.assertEqual(write.call_count,1)
            self.assertEqual(result['status'],'not_retried_after_api_error')

    def test_native_primary_query_is_not_simply_nearest_map_icon(self):
        points = [dict(position=[1,1030,0],primary_query_eligible=False),
                  dict(position=[100,1030,0],primary_query_eligible=True)]
        self.assertEqual(resolve_virtual_source(points,[0,1030,0]),[100,1030,0])
        points[1]['primary_query_eligible'] = False
        self.assertEqual(resolve_virtual_source(points,[0,1030,0]),[1,1030,0])
        with self.assertRaises(ReadError):
            resolve_virtual_source([], [0,1030,0])

    def test_distant_registered_point_does_not_reintroduce_500m_waypoint_cap(self):
        points=[dict(position=[10000,1030,0],primary_query_eligible=True)]
        self.assertEqual(resolve_virtual_source(points,[0,1030,0]),[10000,1030,0])


class MarkerFieldWriterTests(unittest.TestCase):
    def fixture(self,expected):
        memory = Mock()
        memory.pid,memory.handle = 123,21
        memory.alive.return_value = True
        memory.read.return_value = expected
        memory.api.OpenProcess.return_value = 22
        def times(handle,creation,*unused):
            C.cast(creation,C.POINTER(W.FILETIME)).contents.dwLowDateTime = 123
            return True
        def query(handle,address,output,size):
            mbi = C.cast(output,C.POINTER(MEMORY_BASIC_INFORMATION)).contents
            mbi.BaseAddress,mbi.RegionSize,mbi.State,mbi.Protect = 0x100000,4096,0x1000,4
            return size
        def write(handle,address,buffer,size,output):
            memory.read.return_value = C.string_at(buffer,size)
            C.cast(output,C.POINTER(C.c_size_t)).contents.value = size
            return True
        memory.api.GetProcessTimes.side_effect = times
        memory.api.VirtualQueryEx.side_effect = query
        memory.api.WriteProcessMemory.side_effect = write
        return memory

    def test_type_and_reference_writes_have_exact_sizes_and_close(self):
        for expected,replacement,address in ((b'\x0a',b'\x28',0x100060),
                                               (struct.pack('<Q',config.USER_WAYPOINT_ID),struct.pack('<Q',123),0x100090)):
            memory = self.fixture(expected)
            guard = Mock()
            write_owned_field_once(memory,address,expected,replacement,guard)
            self.assertEqual(memory.api.WriteProcessMemory.call_count,1)
            self.assertEqual(memory.api.WriteProcessMemory.call_args.args[1],address)
            self.assertEqual(memory.api.WriteProcessMemory.call_args.args[3],len(expected))
            self.assertEqual(guard.call_count,2)
            memory.api.CloseHandle.assert_called_once_with(22)

    def test_changed_field_or_guard_never_writes(self):
        memory = self.fixture(b'\x29')
        with self.assertRaises(ReadError):
            write_owned_field_once(memory,0x100060,b'\x0a',b'\x28',lambda:None)
        memory.api.WriteProcessMemory.assert_not_called()
        memory.api.CloseHandle.assert_called_once_with(22)
        memory = self.fixture(b'\x0a')
        with self.assertRaises(ReadError):
            write_owned_field_once(memory,0x100060,b'\x0a',b'\x28',Mock(side_effect=ReadError('身份改变')))
        memory.api.WriteProcessMemory.assert_not_called()
        memory.api.CloseHandle.assert_called_once_with(22)
