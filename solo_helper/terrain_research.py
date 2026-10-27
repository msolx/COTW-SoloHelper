"""当前EXE地形查询的只读研究；粗高程和已加载区块不能替代碰撞/水域检测。"""
import math
import struct
import hashlib

from memory.process_reader import ReadError, valid_pointer
from solo_helper import config
from solo_helper.player_research import pointer_at


def coarse_grid_sample(memory, terrain, x, z):
    # 2CA270: (XZ-(-16384))*1/64，512×512 float表，边缘下一点按511掩码环绕。
    gx, gz = (x + 16384.0) / 64.0, (z + 16384.0) / 64.0
    if not all(math.isfinite(v) and 0 <= v < 512 for v in (gx,gz)):
        raise ReadError('目标超出当前已研究的粗高程表覆盖范围')
    ix, iz = math.floor(gx), math.floor(gz)
    fx, fz = gx-ix, gz-iz
    values = []
    for cx,cz in ((ix,iz),((ix+1)&511,iz),(ix,(iz+1)&511),((ix+1)&511,(iz+1)&511)):
        height, = struct.unpack('<f',memory.read(terrain+4+(cz*512+cx)*4,4))
        if not math.isfinite(height) or not 0 < height < 10000:
            raise ReadError('粗高程采样异常')
        values.append(height)
    a,b,c,d = values
    return (a+(b-a)*fx)*(1-fz)+(c+(d-c)*fx)*fz


def tile_index(x,z,transform):
    ox,oz,scale = transform
    if not all(math.isfinite(v) for v in (x,z,ox,oz,scale)) or not 1e-6 <= scale <= 1024:
        raise ReadError('地形区块坐标变换异常')
    # D83670使用向下取整后算术右移9位，不能将负数直接截断到零。
    tx,tz = math.floor((x-ox)*scale) >> 9, math.floor((z-oz)*scale) >> 9
    if not 0 <= tx < 64 or not 0 <= tz < 64:
        raise ReadError('目标地形区块越界')
    return tx,tz


def read_terrain_context(memory,current,target):
    if memory.sha256 != config.EXPECTED_SHA256:
        raise ReadError('地形研究仅允许当前已核对EXE哈希')
    # 97D940地图高度查询：优先2CA3F0碰撞查询，失败使用2CA270粗表+12。
    terrain = pointer_at(memory,memory.base+0x27c23e0)
    if memory.read(terrain,1) == b'\0':
        raise ReadError('地形粗高程表尚未就绪')
    # 2CB020 -> D83730 -> D83670：区块转换数据来自资源+BA20。
    registry = pointer_at(memory,memory.base+0x27c23d8)
    resource = pointer_at(memory,registry+0xce0)
    transform_raw = memory.read(resource+0xba20,12)
    transform = struct.unpack('<3f',transform_raw)
    result = {}
    guards = []
    for name,position in (('current',current),('target',target)):
        x,_,z = position
        tx,tz = tile_index(x,z,transform)
        entry = memory.base+0x27b9040+(tz*64+tx)*8
        tile_raw = memory.read(entry,8)
        tile, = struct.unpack('<Q',tile_raw)
        state,body_count = None,0
        if tile:
            if not valid_pointer(tile):
                raise ReadError('地形区块指针异常')
            state, = struct.unpack('<I',memory.read(tile+0x68,4))
            body_count, = struct.unpack('<i',memory.read(tile+0x14,4))
            if not 0 <= body_count <= 1024:
                raise ReadError('地形区块物理体数量异常')
            guards.append((tile+0x68,struct.pack('<I',state)))
            guards.append((tile+0x14,struct.pack('<i',body_count)))
        guards.append((entry,tile_raw))
        result[name] = dict(tile=[tx,tz],state=state,body_count=body_count,
                            loaded_candidate=state==3 and body_count>0,
                            coarse_height=coarse_grid_sample(memory,terrain,x,z))
    if (pointer_at(memory,memory.base+0x27c23e0) != terrain
            or pointer_at(memory,memory.base+0x27c23d8) != registry
            or pointer_at(memory,registry+0xce0) != resource
            or memory.read(resource+0xba20,12) != transform_raw
            or any(memory.read(address,len(raw)) != raw for address,raw in guards)):
        raise ReadError('地形资源在采样期间变化，丢弃结果')
    result.update(water_or_obstacle_checked=False,
                  resource_identity=hashlib.sha256(struct.pack('<3Q',terrain,registry,resource)+transform_raw+
                                                   b''.join(raw for _,raw in guards)).hexdigest(),
                  disclaimer='区块状态及64米粗高程只供研究，不代表目标安全落地')
    return result


def same_terrain_context(before,after):
    """资源/区块必须不变；允许人物厘米内抖动造成的极小插值差。"""
    if not before.get('resource_identity') or before.get('resource_identity') != after.get('resource_identity'):
        return False
    for name in ('current','target'):
        a,b = before[name],after[name]
        if any(a.get(key) != b.get(key) for key in ('tile','state','body_count','loaded_candidate')):
            return False
        if abs(a['coarse_height']-b['coarse_height']) > 0.02:
            return False
    return True
