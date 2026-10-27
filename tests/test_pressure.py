"""当前保护区压力清除：边界、其它地图隔离、失败不重试和写句柄关闭。"""
import ctypes as C
from ctypes import wintypes as W
import struct
import unittest
from dataclasses import replace
from unittest.mock import Mock,patch
from memory.process_reader import ReadError,ProcessAccessError,MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.pressure import read_pressure,clear_snapshot_once,run_clear


class PressureTests(unittest.TestCase):
    def fixture(self):
        class Memory:
            base=0x140000000
            sha256=config.EXPECTED_SHA256
            pid=123
            handle=21
            def __init__(self):
                self.data={}
                self.api=Mock()
                self.reads=[]
                self.alive=Mock(return_value=True)
            def put_bytes(self,address,raw):
                for n,value in enumerate(raw):
                    self.data[address+n]=value
            def put(self,address,fmt,*values):
                self.put_bytes(address,struct.pack(fmt,*values))
            def read(self,address,size):
                if size>8192:
                    raise AssertionError('读取超限')
                self.reads.append((address,size))
                return bytes(self.data[address+i] for i in range(size))
        m=Memory()
        manager,pressure,slots,data=0x100000,0x200000,0x300000,0x500000
        m.put_bytes(m.base+0x920b30,bytes.fromhex('48895150c6417c01c3'))
        m.put_bytes(m.base+0x8fd400,bytes.fromhex('488b4350488d1440488b4358488b04d00fb60401'))
        m.put(m.base+0x27c5dc8,'<Q',manager)
        m.put(manager+0xf0,'<Q',pressure)
        m.put(manager+0x68,'<I',1)
        m.put(pressure+0x40,'<2I',256,256)
        m.put(pressure+0x50,'<Q',1)
        m.put(pressure+0x58,'<3Q',slots,slots+48,slots+48)
        m.put(pressure+0x7c,'<B',0)
        m.put(slots+24,'<3Q',data,data+65536,data+65536)
        m.put_bytes(data,bytes(65536))
        m.put(data+30,'<B',13)
        m.put(data+8193,'<B',3)
        # 其它地图的哨兵既不读取，也不能被清除。
        m.put_bytes(0x400000,b'OTHER_RESERVE')
        m.api.OpenProcess.return_value=22
        def times(handle,creation,*unused):
            C.cast(creation,C.POINTER(W.FILETIME)).contents.dwLowDateTime=42
            return True
        def query(handle,address,output,size):
            mbi=C.cast(output,C.POINTER(MEMORY_BASIC_INFORMATION)).contents
            mbi.BaseAddress=address&~4095
            mbi.RegionSize=1024*1024
            mbi.State,mbi.Protect=0x1000,4
            return size
        def write(handle,address,buffer,size,output):
            m.put_bytes(address,C.string_at(buffer,size))
            C.cast(output,C.POINTER(C.c_size_t)).contents.value=size
            return True
        m.api.GetProcessTimes.side_effect=times
        m.api.VirtualQueryEx.side_effect=query
        m.api.WriteProcessMemory.side_effect=write
        return m

    def test_clear_only_current_nonzero_blocks_and_refresh_flag(self):
        m=self.fixture()
        before=read_pressure(m)
        self.assertEqual(before.summary()['nonzero_cells'],2)
        result=clear_snapshot_once(m,before)
        self.assertEqual(result['data_bytes_written'],16384)
        self.assertTrue(result['dirty_marked'])
        self.assertEqual(read_pressure(m).summary()['nonzero_cells'],0)
        writes=[(c.args[1],c.args[3]) for c in m.api.WriteProcessMemory.call_args_list]
        self.assertEqual(writes,[(0x500000,8192),(0x502000,8192),(0x20007c,1)])
        self.assertFalse(any(0x400000<=address<0x410000 for address,size in m.reads))
        self.assertEqual(bytes(m.data[0x400000+i] for i in range(13)),b'OTHER_RESERVE')
        m.api.CloseHandle.assert_called_once_with(22)

    def test_wrong_build_code_reserve_and_array_bounds_rejected_before_write(self):
        for mutation in ('build','code','reserve','bounds'):
            m=self.fixture()
            if mutation=='build': m.sha256='other'
            elif mutation=='code': m.put(m.base+0x920b30,'<B',0)
            elif mutation=='reserve': m.put(0x100000+0x68,'<I',0)
            else: m.put(0x300000+24,'<3Q',0x500000,0x510001,0x510001)
            with self.assertRaises(ReadError):
                read_pressure(m)
            m.api.OpenProcess.assert_not_called()

    def test_switch_reserve_and_changed_pressure_stop_without_opening_writer(self):
        for reserve in (True,False):
            m=self.fixture()
            snapshot=read_pressure(m)
            if reserve:
                m.put(0x100000+0x68,'<I',0)
            else:
                m.put(0x500000+30,'<B',14)
            with self.assertRaises(ReadError):
                clear_snapshot_once(m,snapshot)
            m.api.OpenProcess.assert_not_called()

    def test_partial_api_failure_never_retries_and_closes_handle(self):
        m=self.fixture()
        snapshot=read_pressure(m)
        def partial(handle,address,buffer,size,output):
            C.cast(output,C.POINTER(C.c_size_t)).contents.value=4
            return True
        m.api.WriteProcessMemory.side_effect=partial
        with self.assertRaises(ProcessAccessError):
            clear_snapshot_once(m,snapshot)
        self.assertEqual(m.api.WriteProcessMemory.call_count,1)
        m.api.CloseHandle.assert_called_once_with(22)

    def test_no_permission_bypass_and_no_writes_when_already_zero(self):
        m=self.fixture()
        snapshot=read_pressure(m)
        m.api.OpenProcess.return_value=0
        with self.assertRaises(ProcessAccessError):
            clear_snapshot_once(m,snapshot)
        m.api.WriteProcessMemory.assert_not_called()
        m=self.fixture()
        m.put_bytes(0x500000,bytes(65536))
        result=clear_snapshot_once(m,read_pressure(m))
        self.assertFalse(result['write_attempted'])
        m.api.OpenProcess.assert_not_called()

    def test_missing_approval_never_connects(self):
        with patch('solo_helper.pressure.ProcessReader') as reader:
            with self.assertRaises(ReadError):
                run_clear(singleplayer_confirmed=True)
            reader.assert_not_called()

    def test_forged_snapshot_address_cannot_write_other_reserve(self):
        for field in ('data_address','pressure'):
            m=self.fixture()
            snapshot=replace(read_pressure(m),**{field:0x400000})
            with self.assertRaises(ReadError):
                clear_snapshot_once(m,snapshot)
            m.api.OpenProcess.assert_not_called()

    def test_map_switch_after_first_write_stops_without_touching_next_block(self):
        m=self.fixture()
        snapshot=read_pressure(m)
        original=m.api.WriteProcessMemory.side_effect
        def switch(*args):
            result=original(*args)
            m.put(0x100000+0x68,'<I',0)
            return result
        m.api.WriteProcessMemory.side_effect=switch
        with self.assertRaises(ReadError):
            clear_snapshot_once(m,snapshot)
        self.assertEqual(m.api.WriteProcessMemory.call_count,1)
        self.assertEqual(m.read(0x500000+8193,1),b'\3')
        m.api.CloseHandle.assert_called_once_with(22)
