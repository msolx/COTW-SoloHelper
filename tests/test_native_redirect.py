"""原生请求实验的门禁、早期窗口和最终采样；不访问真实游戏。"""
import struct
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import unittest
from unittest.mock import patch,Mock

from memory.process_reader import ReadError,MEMORY_BASIC_INFORMATION
from solo_helper import config
from solo_helper.native_request import NativeRequest,redirect_bytes,write_target_once
from solo_helper.native_request_trial import plan_target,result_from_samples,run
from solo_helper.waypoint_reader import UserWaypoint


class NativeRedirectTests(unittest.TestCase):
    def writer_fixture(self):
        memory = Mock()
        memory.pid,memory.handle = 123,21
        memory.alive.return_value = True
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

    def test_writer_changes_only_request_xyz_once_and_closes_handle(self):
        memory = self.writer_fixture()
        request = self.request()
        attempted = Mock()
        with patch('solo_helper.native_request.read_request',return_value=request):
            result = write_target_once(memory,request,(110,1031,210),on_attempt=attempted)
        memory.api.WriteProcessMemory.assert_called_once()
        args = memory.api.WriteProcessMemory.call_args.args
        self.assertEqual((args[1],args[3]),(request.controller+0x130,12))
        self.assertEqual(result['observed'],(110,1031,210))
        attempted.assert_called_once()
        memory.api.CloseHandle.assert_called_once_with(22)

    def test_foreign_or_late_request_stops_without_writing(self):
        original = self.request()
        for fresh in (replace(original,selection_id=0x456),replace(original,state=3),replace(original,remaining=0.1)):
            memory = self.writer_fixture()
            attempted = Mock()
            with patch('solo_helper.native_request.read_request',return_value=fresh),self.assertRaises(ReadError):
                write_target_once(memory,original,(110,1031,210),on_attempt=attempted)
            memory.api.WriteProcessMemory.assert_not_called()
            attempted.assert_not_called()
            memory.api.CloseHandle.assert_called_once_with(22)

    def test_denied_or_partial_write_is_not_retried(self):
        request = self.request()
        memory = self.writer_fixture()
        memory.api.OpenProcess.return_value = None
        with self.assertRaises(ReadError):
            write_target_once(memory,request,(110,1031,210))
        memory.api.WriteProcessMemory.assert_not_called()
        memory = self.writer_fixture()
        def partial(handle,address,buffer,size,output):
            C.cast(output,C.POINTER(C.c_size_t)).contents.value = 4
            return True
        memory.api.WriteProcessMemory.side_effect = partial
        with patch('solo_helper.native_request.read_request',return_value=request),self.assertRaises(ReadError):
            write_target_once(memory,request,(110,1031,210))
        self.assertEqual(memory.api.WriteProcessMemory.call_count,1)
        memory.api.CloseHandle.assert_called_once_with(22)

    def request(self,state=2,remaining=1.0):
        return NativeRequest(0x100000,0x200000,state,remaining,0x123,
                             struct.pack('<16f',1,0,0,0,0,1,0,0,0,0,1,0,100,1030,200,1))

    def test_only_early_phase_produces_12_byte_translation(self):
        request = self.request()
        original = request.matrix
        raw = redirect_bytes(request,(110,1031,210))
        self.assertEqual(struct.unpack('<3f',raw),(110,1031,210))
        self.assertEqual(request.matrix,original)
        for phase in (0,1,3,4,5,6,7,9):
            with self.assertRaises(ReadError):
                write_target_once(None,self.request(phase),(110,1031,210))
        with self.assertRaises(ReadError):
            write_target_once(None,self.request(2,0.49),(110,1031,210))
        for target in ((float('nan'),1030,200),(1,2),(1,2,3,4)):
            with self.assertRaises(ReadError):
                redirect_bytes(request,target)

    def test_native_trial_keeps_loaded_ground_checks_without_fixed_distance_cap(self):
        current = (100,1030,200)
        waypoint = UserWaypoint((115,1032.1,200),1030.1,config.USER_WAYPOINT_ID,10)
        terrain = {name:dict(state=3,body_count=1,loaded_candidate=True,coarse_height=1030)
                   for name in ('current','target')}
        target = plan_target(current,waypoint,terrain)
        self.assertAlmostEqual(target[1],1030.25,places=3)
        terrain['target']['loaded_candidate'] = False
        with self.assertRaises(ReadError):
            plan_target(current,waypoint,terrain)

    def test_native_distance_override_is_independent_of_old_direct_move(self):
        from solo_helper.surface_plan import surface_transfer_bytes
        current=(100,1030,200)
        waypoint=UserWaypoint((500,1032.1,200),1030.1,config.USER_WAYPOINT_ID,10)
        terrain={name:dict(state=3,body_count=1,loaded_candidate=True,coarse_height=1030)
                 for name in ('current','target')}
        with self.assertRaises(ReadError):
            surface_transfer_bytes(current,waypoint,struct.pack('<3f',*current),terrain,surface_max_distance=200)
        self.assertEqual(plan_target(current,waypoint,terrain)[0],500)
        with patch.object(config,'NATIVE_REDIRECT_MAX_DISTANCE',200),self.assertRaises(ReadError):
            plan_target(current,waypoint,terrain)
        for invalid in (True,float('inf'),float('nan'),-1,'unlimited'):
            with patch.object(config,'NATIVE_REDIRECT_MAX_DISTANCE',invalid),self.assertRaises(ReadError):
                plan_target(current,waypoint,terrain)
        terrain['target']['loaded_candidate'] = True
        for distance in (201,400,2000,10000):
            waypoint = UserWaypoint((100+distance,1032.1,200),1030.1,config.USER_WAYPOINT_ID,10)
            self.assertAlmostEqual(plan_target(current,waypoint,terrain)[0],100+distance)
        waypoint = UserWaypoint((100,1032.1,200),1030.1,config.USER_WAYPOINT_ID,10)
        with self.assertRaises(ReadError):
            plan_target(current,waypoint,terrain)

    def test_failed_or_missing_tail_samples_never_claim_arrival(self):
        samples = [dict(position=[115,1030.1,200],native_state=0) for _ in range(20)]
        target = (115,1030.25,200)
        self.assertEqual(result_from_samples(samples,target,1030.1)['status'],'position_reached_observation_required')
        samples[-1] = dict(error='对象暂不可用')
        self.assertEqual(result_from_samples(samples,target,1030.1)['status'],'movement_not_confirmed')
        samples[-1] = dict(position=[115,1030.1,200],native_state=6)
        self.assertEqual(result_from_samples(samples,target,1030.1)['status'],'movement_not_confirmed')
        samples[-1] = dict(position=[115,1030.1,200],native_state=0,native_target=[200,1040,300])
        self.assertEqual(result_from_samples(samples,target,1030.1)['status'],'native_request_replaced_after_arrival')

    def test_walking_after_stable_arrival_is_not_initial_arrival_failure(self):
        target = [115,1030.25,200]
        samples = [dict(position=[115,1030.1,200],native_state=0,native_target=target,elapsed=i*0.05) for i in range(20)]
        samples += [dict(position=[117,1030.1,200],native_state=0,native_target=target,elapsed=1+i*0.05) for i in range(20)]
        result = result_from_samples(samples,target,1030.1)
        self.assertEqual(result['status'],'position_reached_later_position_changed')
        self.assertIsNotNone(result['stable_arrival_observed'])
        self.assertEqual(result['final_horizontal_error_m'],2)

    def test_missing_approval_never_connects_or_opens_writer(self):
        with patch('solo_helper.native_request_trial.ProcessReader') as reader:
            with self.assertRaises(ReadError):
                run()
            reader.assert_not_called()
