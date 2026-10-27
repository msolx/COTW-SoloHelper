"""精确构建的基础碰撞网格交叉检查；不调用游戏代码，不替代水域/障碍检查。"""
from dataclasses import dataclass,asdict
import math
import struct

from memory.process_reader import ReadError,valid_pointer
from solo_helper import config
from solo_helper.player_research import pointer_at
from solo_helper.sdf_mesh_research import read_base_mesh,array_descriptor,triangle_height,read_bounded_buffer


@dataclass(frozen=True)
class BaseMeshEvidence:
    player: tuple
    waypoint: tuple
    terrain_identity: str
    player_mesh_height: float
    target_mesh_height: float
    triangle_counts: tuple

    def validate(self,current,waypoint,terrain):
        """仅对本次坐标/地形快照有效；新航点、移动或切图不能复用旧证据。"""
        ground=waypoint.input_height_candidate
        if ground is None:
            return False
        values=(*current,*self.player,*self.waypoint,self.player_mesh_height,self.target_mesh_height)
        player_tol = getattr(config,'NATIVE_PLAYER_MESH_MAX_ERROR',config.NATIVE_BASE_MESH_MAX_ERROR)
        target_tol = getattr(config,'NATIVE_TARGET_MESH_MAX_ERROR',3.0)
        return (all(math.isfinite(v) for v in values)
                and math.dist(current,self.player)<=0.1
                and (waypoint.marker_position[0],ground,waypoint.marker_position[2])==self.waypoint
                and bool(self.terrain_identity) and terrain.get('resource_identity')==self.terrain_identity
                and abs(current[1]-self.player_mesh_height)<=player_tol
                and abs(ground-self.target_mesh_height)<=target_tol)

    def report(self):
        return dict(kind='base_collision_mesh_crosscheck',**asdict(self),
                    max_height_error_m=config.NATIVE_BASE_MESH_MAX_ERROR,
                    final_collision_surface_verified=False,water_or_obstacle_checked=False)


def _typed_shape(memory,shape,vtable,method,guards):
    actual=pointer_at(memory,shape)
    target=pointer_at(memory,actual+0xb0)
    if actual!=memory.base+vtable or target!=memory.base+method:
        raise ReadError('基础地面碰撞形状与已核对构建不一致')
    guards.extend(((shape,struct.pack('<Q',actual)),(actual+0xb0,struct.pack('<Q',target))))


def _identity_basis(matrix):
    # W项包含打包标志，不当作矩阵系数；本阶段只接收无旋转的实例/物理体。
    return all(math.isfinite(matrix[col*4+row]) and
               abs(matrix[col*4+row]-(1 if col==row else 0))<1e-6
               for col in range(3) for row in range(3))


def _tile_mesh(memory,info,world,bodies,capacity,origin,guards):
    tx,tz=info['tile']
    if not (0<=tx<64 and 0<=tz<64 and info.get('loaded_candidate')
            and info.get('state')==3 and info.get('body_count')==1):
        raise ReadError('基础网格阶段仅支持已加载且单物理体的地形区块')
    entry=memory.base+0x27b9040+(tz*64+tx)*8
    tile=pointer_at(memory,entry)
    raw=memory.read(tile+0x14,8)
    count,index=struct.unpack('<2i',raw)
    state=memory.read(tile+0x68,4)
    if count!=1 or not 0<=index<capacity or state!=struct.pack('<I',3):
        raise ReadError('基础网格地形区块发生变化')
    guards.extend(((entry,struct.pack('<Q',tile)),(tile+0x14,raw),(tile+0x68,state)))
    body=bodies+index*0x90
    transform_raw=memory.read(body,64)
    transform=struct.unpack('<16f',transform_raw)
    flags=memory.read(body+0x40,4)
    if not struct.unpack('<I',flags)[0]&3 or not _identity_basis(transform):
        raise ReadError('基础网格物理体状态或旋转未验证')
    wrapper=pointer_at(memory,body+0x48)
    _typed_shape(memory,wrapper,0x223bff8,0x15df1a0,guards)
    compound=pointer_at(memory,wrapper+0x38)
    _typed_shape(memory,compound,0x1fe7178,0xf299a0,guards)
    descriptor=memory.read(compound+0x60,12)
    data,n=struct.unpack('<Qi',descriptor)
    if not valid_pointer(data) or not 0<n<=1024:
        raise ReadError('基础网格实例数量超出验证范围')
    instances=read_bounded_buffer(memory,data,n*0x80)
    guards.extend(((body,transform_raw),(body+0x40,flags),(body+0x48,struct.pack('<Q',wrapper)),
                   (wrapper+0x38,struct.pack('<Q',compound)),(compound+0x60,descriptor),
                   (data,instances)))
    # 核对全部实例同属这一几何资源且覆盖全部基础三角形，不能仅靠首个样本放行。
    shapes=[]
    model=None
    for i in range(n):
        raw=instances[i*0x80:(i+1)*0x80]
        matrix=struct.unpack_from('<16f',raw)
        scale=struct.unpack_from('<3f',raw,0x40)
        if (not _identity_basis(matrix) or any(abs(v)>1e-6 for v in matrix[12:15])
                or any(not math.isfinite(v) or abs(v-1)>1e-6 for v in scale)
                or raw[0x60]!=0 or not struct.unpack_from('<I',raw,0xc)[0]&0x40):
            raise ReadError('基础网格实例变换/启用状态未验证')
        shape=struct.unpack_from('<Q',raw,0x50)[0]
        if not valid_pointer(shape):
            raise ReadError('基础网格实例指针异常')
        _typed_shape(memory,shape,0x223c280,0x2f4da0,guards)
        binding=memory.read(shape+0x30,12)
        shared,primitive=struct.unpack('<QI',binding)
        current_model=pointer_at(memory,shared)
        if model is not None and current_model!=model:
            raise ReadError('基础网格区块包含多种几何资源，当前不放行')
        model=current_model
        guards.extend(((shape+0x30,binding),(shared,struct.pack('<Q',model))))
        shapes.append((shape,primitive))
    mesh=read_base_mesh(memory,shapes[0][0],guards)
    if n!=mesh['triangle_count']:
        raise ReadError('基础网格实例与三角形数量不一致')
    groups,group_count=array_descriptor(memory,model+0xc8,24,65536,guards)
    group_raw=read_bounded_buffer(memory,groups,group_count*24)
    guards.append((groups,group_raw))
    covered=set()
    for _,primitive in shapes:
        group=primitive>>8
        if group>=group_count:
            raise ReadError('基础网格分组索引越界')
        triangle=(struct.unpack_from('<I',group_raw,group*24)[0]&0x7fffff)+(primitive&255)
        covered.add(triangle)
    if covered!=set(range(n)):
        raise ReadError('基础网格实例未完整覆盖三角形')
    translation=[transform[12+k]+origin[k] for k in range(3)]
    if not all(math.isfinite(v) for v in translation):
        raise ReadError('基础网格平移异常')
    return [[[p[k]+translation[k] for k in range(3)] for p in tri] for tri in mesh['triangles']]


def read_mesh_evidence(memory,current,waypoint,terrain):
    if not config.is_compatible_build(memory.sha256):
        raise ReadError('基础网格构建未验证')
    manager=pointer_at(memory,memory.base+0x27a8320)
    world=pointer_at(memory,manager+0x30)
    bodies=pointer_at(memory,world+0x20)
    capacity_raw=memory.read(world+0x2c,4)
    capacity=struct.unpack('<I',capacity_raw)[0]&0x3fffffff
    origin_raw=memory.read(manager+0x1a064,12)
    origin=struct.unpack('<3f',origin_raw)
    if not 0<capacity<=config.PHYSICS_MAX_BODY_CAPACITY or not all(map(math.isfinite,origin)):
        raise ReadError('基础网格物理场景异常')
    guards=[(memory.base+0x27a8320,struct.pack('<Q',manager)),(manager+0x30,struct.pack('<Q',world)),
            (world+0x20,struct.pack('<Q',bodies)),(world+0x2c,capacity_raw),(manager+0x1a064,origin_raw)]
    heights=[]
    counts=[]
    cache={}
    for name,point in (('current',current),('target',waypoint.marker_position)):
        info=terrain[name]
        if not info.get('loaded_candidate') or info.get('state')!=3 or info.get('body_count')!=1:
            raise ReadError('基础网格仅接收已加载的单物理体区块')
        key=tuple(info['tile'])
        if key not in cache:
            cache[key]=_tile_mesh(memory,info,world,bodies,capacity,origin,guards)
        triangles=cache[key]
        hits=[h for tri in triangles if (h:=triangle_height(tri,point[0],point[2])) is not None]
        if not hits or len(hits)>8 or max(hits)-min(hits)>0.02:
            raise ReadError('基础网格未找到唯一高度的覆盖面')
        heights.append(sum(hits)/len(hits))
        counts.append(len(triangles))
    if any(read_bounded_buffer(memory,address,len(raw))!=raw for address,raw in guards):
        raise ReadError('基础网格或浮动原点在采样期间变化')
    evidence=BaseMeshEvidence(tuple(current),(waypoint.marker_position[0],waypoint.input_height_candidate,
                                            waypoint.marker_position[2]),terrain.get('resource_identity',''),
                              *heights,tuple(counts))
    if not evidence.validate(current,waypoint,terrain):
        player_tol = getattr(config,'NATIVE_PLAYER_MESH_MAX_ERROR',config.NATIVE_BASE_MESH_MAX_ERROR)
        target_tol = getattr(config,'NATIVE_TARGET_MESH_MAX_ERROR',3.0)
        raise ReadError(f'基础碰撞网格交叉检查不通过：人物差{current[1]-heights[0]:+.3f}米，'
                        f'目标差{waypoint.input_height_candidate-heights[1]:+.3f}米，'
                        f'允许人物±{player_tol:g}米、目标±{target_tol:g}米')
    return evidence
