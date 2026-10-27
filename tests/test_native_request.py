"""原生请求只读快照：校验类型、阶段边界及跨阶段混合快照拒绝。"""
import struct
import unittest

from memory.process_reader import ReadError
from solo_helper import config
from solo_helper.probe_native_points import native_request_snapshot


class NativeRequestTests(unittest.TestCase):
    def fixture(self):
        class Memory:
            base = 0x140000000
            sha256 = config.EXPECTED_SHA256
            def __init__(self):
                self.data,self.reads = {},[]
            def put(self,address,fmt,*values):
                self.data[address] = struct.pack(fmt,*values)
            def read(self,address,size):
                self.reads.append((address,size))
                raw = self.data[address]
                if len(raw) != size:
                    raise ReadError('模拟内存长度异常')
                return raw
        memory = Memory()
        controller = 0x100000
        vtable = memory.base+0x1c2a208
        memory.put(memory.base+0x27c3ae8,'<Q',controller)
        memory.put(controller,'<Q',vtable)
        memory.put(vtable+0x98,'<Q',memory.base+0x824c00)
        memory.put(vtable+0xa0,'<Q',memory.base+0x8254b0)
        memory.put(controller+0xf8,'<I',2)
        memory.put(controller+0x100,'<16f',1,0,0,0,0,1,0,0,0,0,1,0,100,1030,200,1)
        return memory,controller

    def test_valid_request_snapshot_is_target_not_player_position(self):
        memory,_ = self.fixture()
        self.assertEqual(native_request_snapshot(memory),dict(state=2,target_position=(100,1030,200)))

    def test_wrong_build_or_controller_refused(self):
        memory,controller = self.fixture()
        memory.sha256 = 'unsupported'
        with self.assertRaises(ReadError):
            native_request_snapshot(memory)
        self.assertEqual(memory.reads,[])
        memory,controller = self.fixture()
        memory.put(controller,'<Q',memory.base+0x1c2a200)
        with self.assertRaises(ReadError):
            native_request_snapshot(memory)
        self.assertNotIn((controller+0x100,64),memory.reads)

    def test_phase_change_and_invalid_state_rejected(self):
        memory,controller = self.fixture()
        original = memory.read
        seen = 0
        def read(address,size):
            nonlocal seen
            if address == controller+0xf8:
                seen += 1
                if seen == 2:
                    return struct.pack('<I',3)
            return original(address,size)
        memory.read = read
        with self.assertRaisesRegex(ReadError,'变化'):
            native_request_snapshot(memory)
        memory,controller = self.fixture()
        memory.put(controller+0xf8,'<I',255)
        with self.assertRaises(ReadError):
            native_request_snapshot(memory)
