"""只读电子哨范围表：全部目标唯一匹配、异常值和未加载补丁的区分。"""
import struct
import unittest
from memory.process_reader import ReadError
from solo_helper.probe_caller_range import summarize_definitions


class CallerRuntimeTests(unittest.TestCase):
    def fixture(self):
        raw=bytearray(255*0x78)
        for slot,key in ((0,123),(3,456)):
            struct.pack_into('<I',raw,slot*0x78,key)
            struct.pack_into('<f',raw,slot*0x78+0x10,400)
        return raw

    def test_expected_runtime_ranges_do_not_claim_animal_response(self):
        result=summarize_definitions(self.fixture(),{123,456})
        self.assertTrue(result['runtime_parameter_verified'])
        self.assertFalse(result['attraction_response_verified'])
        self.assertEqual(result['runtime_range_counts'],{'400.0':2})

    def test_old_200m_value_is_reported_as_not_verified(self):
        raw=self.fixture()
        struct.pack_into('<f',raw,3*0x78+0x10,200)
        result=summarize_definitions(raw,{123,456})
        self.assertFalse(result['runtime_parameter_verified'])
        self.assertEqual(result['runtime_range_counts'],{'400.0':1,'200.0':1})

    def test_duplicate_missing_or_nonfinite_definition_is_not_accepted(self):
        raw=self.fixture()
        struct.pack_into('<I',raw,4*0x78,123)
        struct.pack_into('<f',raw,4*0x78+0x10,400)
        with self.assertRaises(ReadError): summarize_definitions(raw,{123,456})
        with self.assertRaises(ReadError): summarize_definitions(self.fixture(),{123,789})
        raw=self.fixture()
        struct.pack_into('<f',raw,0x10,float('nan'))
        with self.assertRaises(ReadError): summarize_definitions(raw,{123,456})
