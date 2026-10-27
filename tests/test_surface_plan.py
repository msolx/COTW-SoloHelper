"""高度适配阶段的拒绝条件、坐标换算与落地判定；不连接游戏。"""
import struct
import unittest
from copy import deepcopy

from memory.process_reader import ReadError
from solo_helper import config
from solo_helper.surface_plan import surface_transfer_bytes
from solo_helper.terrain_research import coarse_grid_sample,tile_index,same_terrain_context
from solo_helper.waypoint_reader import UserWaypoint
from solo_helper.position_trial import nudge_bytes,validate_change,apply_changes_once,observation_result,run_trial


class SurfaceTests(unittest.TestCase):
    def test_independent_20m_stage_translates_both_uphill_and_downhill(self):
        for height in (12,-12):
            current,waypoint,expected,terrain = self.fixture(180,height)
            with self.assertRaisesRegex(ReadError,'高差'):
                surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)
            new = surface_transfer_bytes(current,waypoint,expected,terrain,
                                         surface_max_distance=200,surface_max_ground_change=20)
            self.assertAlmostEqual(struct.unpack('<3f',new)[1]-struct.unpack('<3f',expected)[1],height+0.15,places=3)
            validate_change(expected,new,surface_trial=True,surface_max_distance=200,surface_max_ground_change=20)
            with self.assertRaises(ReadError):
                validate_change(expected,new,surface_trial=True,surface_max_distance=200)
        args = self.fixture(180,20.01)
        with self.assertRaisesRegex(ReadError,'高差'):
            surface_transfer_bytes(*args,surface_max_distance=200,surface_max_ground_change=20)
        args = self.fixture(30,12)
        with self.assertRaisesRegex(ReadError,'陡坡'):
            surface_transfer_bytes(*args,surface_max_distance=200,surface_max_ground_change=20)

    def test_invalid_height_stage_refused_before_process_access(self):
        from unittest.mock import patch
        from solo_helper.position_trial import inspect_trial
        with patch('solo_helper.position_trial.ProcessReader') as reader:
            for height in (True,'20',0,-20,10,100,float('nan'),float('inf')):
                with self.assertRaises(ReadError):
                    inspect_trial(surface_trial=True,surface_max_distance=200,surface_max_ground_change=height)
                with self.assertRaises(ReadError):
                    run_trial(single_player_confirmed=True,flat_ground_confirmed=True,approved=True,
                              target='body_and_motion',nearby_waypoint=True,surface_trial=True,
                              surface_max_distance=200,surface_max_ground_change=height)
            with self.assertRaises(ReadError):
                inspect_trial(surface_max_ground_change=20)
            reader.assert_not_called()

    def test_explicit_50m_stage_keeps_default_and_writer_limits(self):
        # 研究参数须同时贯穿计划和写入前校验；默认路径仍拒绝25米外。
        current,waypoint,expected,terrain = self.fixture(49.5,1.0)
        with self.assertRaises(ReadError):
            surface_transfer_bytes(current,waypoint,expected,terrain)
        new = surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=50)
        validate_change(expected,new,surface_trial=True,surface_max_distance=50)
        with self.assertRaises(ReadError):
            validate_change(expected,new,surface_trial=True)
        for distance in (50.01,100):
            current,waypoint,expected,terrain = self.fixture(distance,1.0)
            with self.assertRaises(ReadError):
                surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=50)
        self.assertEqual(config.SURFACE_TRIAL_MAX_DISTANCE,25)

    def test_explicit_stage_rejects_unsupported_values_and_unloaded_terrain(self):
        from solo_helper.surface_plan import surface_distance_limit
        for value in (True,'50',0,26,75,150,400,float('inf'),float('nan')):
            with self.assertRaises(ReadError):
                surface_distance_limit(value)
        current,waypoint,expected,terrain = self.fixture(45,1.0)
        terrain['target']['loaded_candidate'] = False
        with self.assertRaisesRegex(ReadError,'加载状态'):
            surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=50)
        # 超限必须在尝试访问API前失败；None模拟不可用的进程接口。
        with self.assertRaises(ReadError):
            apply_changes_once(None,[(0x100000,expected,struct.pack('<3f',60,1031,2)),
                                     (0x200000,expected,struct.pack('<3f',60,1031,2))],
                               surface_trial=True,surface_max_distance=50)

    def test_100m_stage_does_not_expand_default_or_50m_mode(self):
        current,waypoint,expected,terrain = self.fixture(99.5,1.0)
        for stage in (None,50):
            with self.assertRaises(ReadError):
                surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=stage)
        new = surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=100)
        validate_change(expected,new,surface_trial=True,surface_max_distance=100)
        with self.assertRaises(ReadError):
            validate_change(expected,new,surface_trial=True,surface_max_distance=50)
        for distance,height in ((100.01,1.0),(90,2.01)):
            current,waypoint,expected,terrain = self.fixture(distance,height)
            with self.assertRaises(ReadError):
                surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=100)

    def test_stage_selection_rejected_before_opening_process_in_wrong_mode(self):
        from unittest.mock import patch
        from solo_helper.position_trial import inspect_trial
        with patch('solo_helper.position_trial.ProcessReader') as reader:
            for stage in (50,100,200):
                with self.assertRaises(ReadError):
                    inspect_trial(surface_max_distance=stage)
                with self.assertRaises(ReadError):
                    run_trial(single_player_confirmed=True,flat_ground_confirmed=True,
                              approved=True,target='body_and_motion',nearby_waypoint=True,
                              surface_max_distance=stage)
            reader.assert_not_called()

    def test_200m_stage_keeps_shorter_limits_and_terrain_guards(self):
        current,waypoint,expected,terrain = self.fixture(199.5,1)
        for stage in (None,50,100):
            with self.assertRaises(ReadError):
                surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=stage)
        new = surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)
        validate_change(expected,new,surface_trial=True,surface_max_distance=200)
        with self.assertRaises(ReadError):
            validate_change(expected,new,surface_trial=True,surface_max_distance=100)
        for distance,height in ((200.01,1),(180,5.01)):
            args = self.fixture(distance,height)
            with self.assertRaises(ReadError):
                surface_transfer_bytes(*args,surface_max_distance=200)
        terrain['target']['loaded_candidate'] = False
        with self.assertRaisesRegex(ReadError,'加载状态'):
            surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)

    def test_200m_height_extension_preserves_shorter_stage_guards(self):
        current,waypoint,expected,terrain = self.fixture(195.96,4.685)
        new = surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)
        validate_change(expected,new,surface_trial=True,surface_max_distance=200)
        with self.assertRaises(ReadError):
            validate_change(expected,new,surface_trial=True,surface_max_distance=100)
        current,waypoint,expected,terrain = self.fixture(90,4.685)
        with self.assertRaisesRegex(ReadError,'高差'):
            surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=100)
        # 即使200米模式允许5米高度差，距离太短形成陡坡仍须拒绝。
        current,waypoint,expected,terrain = self.fixture(10,4.685)
        with self.assertRaisesRegex(ReadError,'陡坡'):
            surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)

    def fixture(self,distance=9.53,height=0.368):
        current = (0,1030,0)
        waypoint = UserWaypoint((distance,1032+height,0),1030+height,config.USER_WAYPOINT_ID,10)
        expected = struct.pack('<3f',1,1030,2)
        terrain = {name:dict(state=3,body_count=1,loaded_candidate=True,coarse_height=value)
                   for name,value in (('current',1030),('target',1030+height))}
        return current,waypoint,expected,terrain

    def test_adapts_original_rejected_height_with_ground_clearance(self):
        current,waypoint,expected,terrain = self.fixture()
        with self.assertRaisesRegex(ReadError,'高差超限'):
            nudge_bytes(current,waypoint,expected,nearby_waypoint=True)
        new = surface_transfer_bytes(current,waypoint,expected,terrain)
        x,y,z = struct.unpack('<3f',new)
        self.assertAlmostEqual(x,10.53,places=4)
        self.assertAlmostEqual(y,1030.518,places=3)
        self.assertEqual(z,2)
        validate_change(expected,new,surface_trial=True)
        with self.assertRaises(ReadError):
            validate_change(expected,new,nearby_waypoint=True)

    def test_extends_distance_with_loaded_terrain_checks(self):
        for distance,accepted in ((20,True),(26,False)):
            current,waypoint,expected,terrain = self.fixture(distance,1.0)
            if accepted:
                validate_change(expected,surface_transfer_bytes(current,waypoint,expected,terrain),surface_trial=True)
            else:
                with self.assertRaises(ReadError):
                    surface_transfer_bytes(current,waypoint,expected,terrain)
        current,waypoint,expected,terrain = self.fixture(20,1.0)
        terrain['target']['loaded_candidate'] = False
        with self.assertRaisesRegex(ReadError,'加载状态'):
            surface_transfer_bytes(current,waypoint,expected,terrain)

    def test_rejects_fallback_height_coarse_mismatch_and_steep_target(self):
        current,waypoint,expected,terrain = self.fixture()
        fallback = deepcopy(terrain)
        fallback['target']['coarse_height'] -= 12
        with self.assertRaisesRegex(ReadError,'回退'):
            surface_transfer_bytes(current,waypoint,expected,fallback)
        mismatch = deepcopy(terrain)
        mismatch['target']['coarse_height'] += 4
        with self.assertRaisesRegex(ReadError,'航点地面高度尚未核实'):
            surface_transfer_bytes(current,waypoint,expected,mismatch)
        current,waypoint,expected,terrain = self.fixture(5,1.5)
        with self.assertRaisesRegex(ReadError,'陡坡'):
            surface_transfer_bytes(current,waypoint,expected,terrain)

    def test_visited_source_coarse_error_does_not_disable_target_guard(self):
        # 现场步行到达证据：航点与脚底高度相符，但64米粗表可偏差7.37米。
        current,waypoint,expected,terrain = self.fixture(141,0.77)
        terrain['current']['coarse_height'] += 7.37
        new = surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)
        validate_change(expected,new,surface_trial=True,surface_max_distance=200)
        terrain['target']['coarse_height'] += 7.37
        with self.assertRaisesRegex(ReadError,'航点地面高度尚未核实'):
            surface_transfer_bytes(current,waypoint,expected,terrain,surface_max_distance=200)

    def test_surface_write_requires_coupled_plan_and_explicit_mode(self):
        old = struct.pack('<3f',1,1030,2)
        new = struct.pack('<3f',17,1031.15,2)
        with self.assertRaises(ReadError):
            apply_changes_once(None,[(0x100000,old,new)],surface_trial=True)
        with self.assertRaises(ReadError):
            run_trial(single_player_confirmed=True,flat_ground_confirmed=True,approved=True,
                      target='body_and_motion',surface_trial=True)
        with self.assertRaises(ReadError):
            validate_change(old,struct.pack('<3f',17,1034,2),surface_trial=True)

    def test_landing_height_and_stability_required(self):
        def report(y):
            return dict(before=dict(world_position=[0,1030,0],floating_origin=[0,0,0]),
                        requested_local_position=[16,1031.15,0],surface_trial=True,
                        requested_ground_height=1031,
                        samples=[dict(physics=[16,y,0],character=[16,y,0]) for _ in range(50)])
        self.assertEqual(observation_result(report(1031.01))['status'],'position_reached_observation_required')
        self.assertEqual(observation_result(report(1031.5))['status'],'landing_not_confirmed')
        moving = report(1031.01)
        moving['samples'][-5]['character'] = [16,1031.2,0]
        self.assertEqual(observation_result(moving)['status'],'landing_not_confirmed')

    def test_world_position_observation_survives_origin_rebase(self):
        # 模拟跨区块后游戏移动浮动原点，局部质心随之改变，世界落点不变。
        report = dict(before=dict(world_position=[9900,1030,10300],floating_origin=[9900,0,10300]),
                      requested_local_position=[0,1030.15,-90],surface_trial=True,
                      requested_ground_height=1030,
                      terrain=dict(current=dict(tile=[51,52]),target=dict(tile=[51,51])),samples=[])
        for index in range(50):
            origin = [9900,0,10300] if index < 20 else [9900,0,10210]
            report['samples'].append(dict(physics=[9900,1030.01,10210],character=[9900,1030.01,10210],
                                          floating_origin=origin,motion=[0,1031.01,10210-origin[2]]))
        result = observation_result(report)
        self.assertEqual(result['status'],'position_reached_observation_required')
        self.assertEqual(result['floating_origin_change_count'],1)
        self.assertTrue(result['cross_terrain_tile'])
        self.assertAlmostEqual(result['observed_horizontal_movement_m'],90)
        # 旧报告无原点序列时不能宣称未发生重定位。
        for frame in report['samples']:
            del frame['floating_origin']
        self.assertIsNone(observation_result(report)['floating_origin_change_count'])

    def test_coarse_interpolation_and_tile_flooring(self):
        class Memory:
            def read(self,address,size):
                self.assert_size = size
                index = (address-0x100000-4)//4
                row,col = divmod(index,512)
                value = 1030+2*(col-256)+4*(row-256)
                return struct.pack('<f',value)
        memory = Memory()
        self.assertAlmostEqual(coarse_grid_sample(memory,0x100000,32,16),1032)
        self.assertEqual(memory.assert_size,4)
        self.assertEqual(tile_index(9919,10279,(-16384,-16384,1)),(51,52))
        with self.assertRaises(ReadError):
            tile_index(-16384.1,0,(-16384,-16384,1))

    def test_terrain_resource_change_rejected_but_small_jitter_allowed(self):
        *_,before = self.fixture()
        before['resource_identity'] = 'same-resource'
        after = deepcopy(before)
        after['current']['coarse_height'] += 0.001
        self.assertTrue(same_terrain_context(before,after))
        after['resource_identity'] = 'new-resource'
        self.assertFalse(same_terrain_context(before,after))
