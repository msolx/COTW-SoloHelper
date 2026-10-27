"""局部实测地面证据仅覆盖已到访小范围，不放宽未知目标或加载门禁。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory.process_reader import ReadError
from solo_helper import config
from solo_helper.visited_ground import witnessed_target
from solo_helper.waypoint_reader import UserWaypoint


class VisitedGroundTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/'ground.json'
        self.record = dict(kind='manual_native_fast_travel_observation',timestamp=100,write_attempted=False,
                           native_functions_called=False,status='observation_finished',samples=[
                               dict(state='observed',world_position=[143.4,1050.1,0],native_request=dict(state=0))
                               for _ in range(20)])
        raw = json.dumps(self.record).encode()
        self.path.write_bytes(raw)
        for name,value in (('NATIVE_GROUND_WITNESS_REPORT',self.path),
                           ('NATIVE_GROUND_WITNESS_SHA256',hashlib.sha256(raw).hexdigest())):
            p = patch.object(config,name,value)
            p.start()
            self.addCleanup(p.stop)
        p = patch('solo_helper.visited_ground.time.time',return_value=200)
        self.clock = p.start()
        self.addCleanup(p.stop)
        self.source = dict(id=config.NATIVE_GROUND_WITNESS_ANCHOR_ID,position=config.NATIVE_GROUND_WITNESS_ANCHOR_POSITION)
        self.current = (0,1030,0)
        self.waypoint = UserWaypoint((143,1052.2,0),1050.2,config.USER_WAYPOINT_ID,10)
        self.terrain = {name:dict(state=3,loaded_candidate=True,body_count=1,coarse_height=1069.5)
                        for name in ('current','target')}

    def test_reviewed_stationary_samples_can_resolve_local_coarse_error(self):
        target,evidence = witnessed_target(self.current,self.waypoint,self.terrain,self.source)
        self.assertAlmostEqual(target[1],1050.35)
        self.assertEqual(evidence['sample_count'],20)
        self.assertFalse(evidence['automatic_ground_detection'])
        self.assertAlmostEqual(evidence['waypoint_ground_error_m'],0.1)

    def test_unknown_point_height_or_unloaded_target_still_refused(self):
        for waypoint in (UserWaypoint((146,1052.2,0),1050.2,config.USER_WAYPOINT_ID,10),
                         UserWaypoint((143,1053.2,0),1051.2,config.USER_WAYPOINT_ID,10)):
            with self.assertRaises(ReadError):
                witnessed_target(self.current,waypoint,self.terrain,self.source)
        self.terrain['target']['loaded_candidate'] = False
        with self.assertRaises(ReadError):
            witnessed_target(self.current,self.waypoint,self.terrain,self.source)

    def test_changed_anchor_stale_or_modified_evidence_refused(self):
        source = dict(self.source,id=123)
        with self.assertRaises(ReadError):
            witnessed_target(self.current,self.waypoint,self.terrain,source)
        self.clock.return_value = 100+config.NATIVE_GROUND_WITNESS_MAX_AGE+1
        with self.assertRaises(ReadError):
            witnessed_target(self.current,self.waypoint,self.terrain,self.source)
        self.clock.return_value = 200
        self.path.write_bytes(b'changed')
        with self.assertRaises(ReadError):
            witnessed_target(self.current,self.waypoint,self.terrain,self.source)
