"""真实拒绝样本的数值回归；模拟读取，绝不连接或写入游戏。"""
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from solo_helper.surface_plan import surface_transfer_bytes,GroundHeightMismatch
from solo_helper.waypoint_reader import UserWaypoint
from solo_helper.native_request_trial import inspect_trial


class GroundDiagnosticsTests(unittest.TestCase):
    def mismatch(self):
        return GroundHeightMismatch(1025.323974609375,1028.951959827776,
                                   1031.5186767578125,1031.0436463355345)

    def test_rejected_target_does_not_blame_valid_player(self):
        current=(9894.161296844482,1031.5186767578125,10227.060768127441)
        waypoint=UserWaypoint((9956.341796875,1027.323974609375,10047.537109375),
                              1025.323974609375,0x123456789,10)
        terrain={name:dict(loaded_candidate=True,state=3,body_count=1,coarse_height=height)
                 for name,height in (('current',1031.0436463355345),('target',1028.951959827776))}
        with self.assertRaises(GroundHeightMismatch) as caught:
            surface_transfer_bytes(current,waypoint,struct.pack('<3f',*current),terrain,
                                   surface_max_distance=200,surface_max_ground_change=20)
        values=caught.exception.diagnostics
        self.assertAlmostEqual(values['player_difference_m'],0.47503,places=4)
        self.assertAlmostEqual(values['target_difference_m'],-3.627985,places=4)
        self.assertEqual(values['tolerance_m'],3)
        self.assertFalse(values['fine_ground_verified'])

    def test_failed_native_preview_closes_and_saves_diagnostics(self):
        memory=Mock()
        memory.close.side_effect=lambda:setattr(memory,'handle',None)
        with tempfile.TemporaryDirectory() as folder,patch('solo_helper.native_request_trial.config.ROOT',Path(folder)),patch(
                'solo_helper.native_request_trial.ProcessReader',return_value=memory),patch(
                'solo_helper.native_request_trial.prepare_trial',side_effect=self.mismatch()):
            result=inspect_trial(virtual_marker=True)
            saved=json.loads((Path(folder)/'native_waypoint_preview.json').read_text(encoding='utf-8'))
        self.assertEqual(saved,result)
        self.assertEqual(result['status'],'stopped')
        self.assertFalse(result['write_attempted'])
        self.assertTrue(result['handle_closed'])
        memory.api.OpenProcess.assert_not_called()
        self.assertEqual(result['height_diagnostics']['reason'],'target_coarse_height_mismatch')
