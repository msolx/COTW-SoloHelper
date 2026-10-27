"""基础地形网格的解码/边界测试；不能代替最终碰撞面现场验证。"""
import math
import struct
import unittest
from memory.process_reader import ReadError
from solo_helper import config
from solo_helper.sdf_mesh_research import decode_vertex,triangle_height,inspect_primitive,read_base_mesh,read_bounded_buffer


class SdfMeshTests(unittest.TestCase):
    def test_buffer_preserves_8k_read_limit_and_total_bound(self):
        calls=[]
        class Memory:
            def read(self,address,size):
                calls.append((address,size))
                if size>8192:
                    raise AssertionError('超过公共读取上限')
                return bytes(size)
        result=read_bounded_buffer(Memory(),0x100000,8192+17)
        self.assertEqual(len(result),8209)
        self.assertEqual(calls,[(0x100000,8192),(0x102000,17)])
        with self.assertRaises(ReadError):
            read_bounded_buffer(Memory(),0x100000,512*1024+1)

    def test_vertex_axes_and_independent_height_encoding(self):
        raw=struct.pack('<3H6x',8192,20000,16384)
        x,y,z=decode_vertex(raw,9)
        self.assertEqual(x,0)
        self.assertEqual(z,128)
        self.assertAlmostEqual(y,1200.1452655792236)
        with self.assertRaises(ReadError):
            decode_vertex(raw,14)

    def test_sloped_triangle_boundary_outside_and_vertical_face(self):
        triangle=((0,10,0),(10,20,0),(0,30,10))
        self.assertAlmostEqual(triangle_height(triangle,2,3),18)
        self.assertEqual(triangle_height(triangle,10,0),20)
        self.assertIsNone(triangle_height(triangle,8,8))
        self.assertIsNone(triangle_height(((0,0,0),(0,10,0),(0,10,10)),0,1))
        with self.assertRaises(ReadError):
            triangle_height(triangle,math.nan,3)

    def fixture(self):
        class Memory:
            sha256=config.EXPECTED_SHA256
            def __init__(self):
                self.data={}
            def put(self,address,fmt,*args):
                self.data[address]=struct.pack(fmt,*args)
            def read(self,address,size):
                raw=self.data[address]
                if len(raw)<size:
                    raise AssertionError((hex(address),size,len(raw)))
                return raw[:size]
        m=Memory()
        shape,shared,model=0x100000,0x200000,0x300000
        m.put(shape+0x30,'<Q',shared)
        m.put(shared,'<Q',model)
        m.put(shape+0x38,'<I',0)
        m.put(model+0x20,'<I',9)
        m.put(model+0x38,'<B',2)
        for offset,data,count,stride in ((0xc8,0x400000,1,24),(0x70,0x500000,3,2),
                                         (0x40,0x600000,3,8),(0x58,0x700000,3,12)):
            m.put(model+offset,'<Q2I',data,count*stride,stride)
        m.put(0x400000,'<I',0)
        m.put(0x500000,'<3H',0,1,2)
        for i,point in enumerate(((8192,20000,8192),(16384,20000,8192),(8192,20000,16384))):
            m.put(0x600000+i*8,'<2I',i,0)
            m.put(0x700000+i*12,'<3H6x',*point)
        m.data[0x600000]=b''.join(m.data[0x600000+i*8] for i in range(3))
        m.data[0x700000]=b''.join(m.data[0x700000+i*12] for i in range(3))
        return m,shape

    def test_bulk_base_mesh_matches_single_primitive_and_stays_unverified(self):
        m,shape=self.fixture()
        mesh=read_base_mesh(m,shape,[])
        self.assertEqual(mesh['triangle_count'],1)
        self.assertEqual(mesh['triangles'][0],inspect_primitive(m,shape,[])['base_triangle'])
        self.assertFalse(mesh['final_collision_surface_verified'])

    def test_bounded_mesh_read_retains_guards_and_rejects_bad_reference(self):
        m,shape=self.fixture()
        guards=[]
        report=inspect_primitive(m,shape,guards)
        self.assertEqual(len(report['base_triangle']),3)
        self.assertFalse(report['final_collision_surface_verified'])
        self.assertTrue(all(m.read(a,len(raw))==raw for a,raw in guards))
        m.put(0x500000,'<3H',0,1,3)
        with self.assertRaisesRegex(ReadError,'引用越界'):
            inspect_primitive(m,shape,[])

    def test_bad_array_descriptor_and_group_never_read_unbounded_data(self):
        m,shape=self.fixture()
        m.put(0x300000+0x58,'<Q2I',0x700000,3,2)
        with self.assertRaisesRegex(ReadError,'数组边界'):
            inspect_primitive(m,shape,[])
        m,shape=self.fixture()
        m.put(shape+0x38,'<I',256)
        with self.assertRaisesRegex(ReadError,'分组索引'):
            inspect_primitive(m,shape,[])
