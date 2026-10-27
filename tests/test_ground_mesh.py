"""基础碰撞网格端到端模拟；验证精确场景绑定和拒绝路径，不连接游戏。"""
from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from memory.process_reader import ReadError,ProcessAccessError
from solo_helper import config
from solo_helper.ground_mesh import read_mesh_evidence
from solo_helper.sdf_mesh_research import Y_SCALE
from solo_helper.native_request_trial import plan_target,plan_with_mesh
from solo_helper.surface_plan import GroundHeightMismatch
from solo_helper.waypoint_reader import UserWaypoint


class GroundMeshTests(unittest.TestCase):
    def fixture(self):
        class Memory:
            base=0x140000000
            sha256=config.EXPECTED_SHA256
            def __init__(self):
                self.data={}
                self.calls={}
            def put(self,address,fmt,*values):
                for i,value in enumerate(struct.pack(fmt,*values)):
                    self.data[address+i]=value
            def read(self,address,size):
                self.calls[address]=self.calls.get(address,0)+1
                return bytes(self.data[address+i] for i in range(size))
        m=Memory()
        manager,world,bodies,tile,wrapper,compound,instances,shape,shared,model=range(0x100000,0xb00000,0x100000)
        for address,value in ((m.base+0x27a8320,manager),(manager+0x30,world),(world+0x20,bodies),
                              (m.base+0x27b9040,tile),(bodies+0x90+0x48,wrapper),
                              (wrapper+0x38,compound),(shape+0x30,shared),(shared,model)):
            m.put(address,'<Q',value)
        m.put(world+0x2c,'<I',10)
        m.put(manager+0x1a064,'<3f',0,0,0)
        m.put(tile+0x14,'<2i',1,1)
        m.put(tile+0x68,'<I',3)
        identity=(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,0)
        m.put(bodies+0x90,'<16f',*identity)
        m.put(bodies+0x90+0x40,'<I',1)
        for address,vtable,method in ((wrapper,0x223bff8,0x15df1a0),(compound,0x1fe7178,0xf299a0),
                                      (shape,0x223c280,0x2f4da0)):
            m.put(address,'<Q',m.base+vtable)
            m.put(m.base+vtable+0xb0,'<Q',m.base+method)
        m.put(compound+0x60,'<Qi',instances,1)
        m.put(instances,'<128s',bytes(128))
        m.put(instances,'<16f',*identity)
        m.put(instances+0xc,'<I',0x40)
        m.put(instances+0x40,'<4f',1,1,1,1)
        m.put(instances+0x50,'<Q',shape)
        m.put(shape+0x38,'<I',0)
        m.put(model+0x20,'<I',9)
        m.put(model+0x38,'<B',2)
        for offset,data,count,stride in ((0xc8,0xb00000,1,24),(0x70,0xc00000,3,2),
                                        (0x40,0xd00000,3,8),(0x58,0xe00000,3,12)):
            m.put(model+offset,'<Q2I',data,count*stride,stride)
        m.put(0xb00000,'<24s',bytes(24))
        m.put(0xc00000,'<3H',0,1,2)
        for i,(x,z) in enumerate(((8192,8192),(16384,8192),(8192,16384))):
            m.put(0xd00000+i*8,'<2I',i,0)
            m.put(0xe00000+i*12,'<3H6x',x,20000,z)
        ground=20000*Y_SCALE-128
        current=(16,ground+.1,16)
        waypoint=UserWaypoint((40,ground+2,16),ground,config.USER_WAYPOINT_ID,10)
        terrain={name:dict(tile=[0,0],state=3,body_count=1,loaded_candidate=True,
                          coarse_height=ground+3.63) for name in ('current','target')}
        terrain['resource_identity']='same-scene'
        return m,current,waypoint,terrain

    def test_actual_mesh_read_allows_independent_crosscheck_without_raising_tolerance(self):
        m,current,waypoint,terrain=self.fixture()
        with self.assertRaises(GroundHeightMismatch):
            plan_target(current,waypoint,terrain)
        target,evidence=plan_with_mesh(m,current,waypoint,terrain)
        self.assertAlmostEqual(target[1],waypoint.input_height_candidate+.15,places=3)
        self.assertEqual(evidence['kind'],'base_collision_mesh_crosscheck')
        self.assertEqual(config.SURFACE_TRIAL_COARSE_TOLERANCE,3)
        self.assertFalse(evidence['final_collision_surface_verified'])

    def test_evidence_cannot_follow_new_waypoint_movement_or_new_scene(self):
        m,current,waypoint,terrain=self.fixture()
        evidence=read_mesh_evidence(m,current,waypoint,terrain)
        self.assertTrue(evidence.validate(current,waypoint,terrain))
        self.assertFalse(evidence.validate((17,current[1],16),waypoint,terrain))
        self.assertFalse(evidence.validate(current,replace(waypoint,marker_position=(41,*waypoint.marker_position[1:])),terrain))
        self.assertFalse(evidence.validate(current,replace(waypoint,input_height_candidate=None),terrain))
        self.assertFalse(evidence.validate(current,waypoint,dict(terrain,resource_identity='new-scene')))

    def test_displaced_ground_uncovered_point_and_disabled_geometry_rejected(self):
        m,current,waypoint,terrain=self.fixture()
        with self.assertRaisesRegex(ReadError,'交叉检查不通过'):
            read_mesh_evidence(m,(16,current[1]+3,16),waypoint,terrain)
        with self.assertRaisesRegex(ReadError,'覆盖面'):
            read_mesh_evidence(m,current,replace(waypoint,marker_position=(140,waypoint.marker_position[1],140)),terrain)
        m.put(0x700000+0x60,'<B',1)
        with self.assertRaisesRegex(ReadError,'启用状态'):
            read_mesh_evidence(m,current,waypoint,terrain)

    def test_origin_change_and_wrong_build_stop(self):
        m,current,waypoint,terrain=self.fixture()
        original=m.read
        def changed(address,size):
            if address==0x100000+0x1a064 and m.calls.get(address,0)>0:
                return struct.pack('<3f',1,0,0)
            return original(address,size)
        m.read=changed
        with self.assertRaisesRegex(ReadError,'采样期间变化'):
            read_mesh_evidence(m,current,waypoint,terrain)
        m,current,waypoint,terrain=self.fixture()
        m.sha256='different'
        with self.assertRaisesRegex(ReadError,'构建'):
            read_mesh_evidence(m,current,waypoint,terrain)

    def test_no_mesh_fallback_for_unknown_height_and_no_permission_downgrade(self):
        m,current,waypoint,terrain=self.fixture()
        with patch('solo_helper.ground_mesh.read_mesh_evidence') as reader:
            with self.assertRaisesRegex(ReadError,'高度未知'):
                plan_with_mesh(m,current,replace(waypoint,input_height_candidate=None),terrain)
            reader.assert_not_called()
        with patch('solo_helper.ground_mesh.read_mesh_evidence',side_effect=ProcessAccessError('ReadProcessMemory',5)):
            with self.assertRaises(ProcessAccessError):
                plan_with_mesh(m,current,waypoint,terrain)

    def test_no_mesh_evidence_can_bypass_unloaded_or_fallback_height(self):
        m,current,waypoint,terrain=self.fixture()
        evidence=read_mesh_evidence(m,current,waypoint,terrain)
        unloaded={**terrain,'target':dict(terrain['target'],loaded_candidate=False)}
        with self.assertRaisesRegex(ReadError,'加载'):
            plan_target(current,waypoint,unloaded,evidence)
        fallback={**terrain,'target':dict(terrain['target'],coarse_height=waypoint.input_height_candidate-12)}
        with self.assertRaisesRegex(ReadError,'回退'):
            plan_target(current,waypoint,fallback,evidence)

    def test_disabled_branch_and_untyped_evidence_do_not_relax_old_guard(self):
        m,current,waypoint,terrain=self.fixture()
        with patch.object(config,'NATIVE_BASE_MESH_ENABLED',False),patch('solo_helper.ground_mesh.read_mesh_evidence') as reader:
            with self.assertRaises(GroundHeightMismatch):
                plan_with_mesh(m,current,waypoint,terrain)
            reader.assert_not_called()
        with self.assertRaises(GroundHeightMismatch):
            plan_target(current,waypoint,terrain,{'target_mesh_height':waypoint.input_height_candidate})

    def test_overlapping_different_height_surfaces_rejected(self):
        m,current,waypoint,terrain=self.fixture()
        triangles=[[(0,current[1],0),(128,current[1],0),(0,current[1],128)],
                   [(0,current[1]+10,0),(128,current[1]+10,0),(0,current[1]+10,128)]]
        with patch('solo_helper.ground_mesh._tile_mesh',return_value=triangles):
            with self.assertRaisesRegex(ReadError,'唯一高度'):
                read_mesh_evidence(m,current,waypoint,terrain)
