"""SdfPrimitive基础网格只读解码研究；未接入传送门禁，基础面不等于最终碰撞面。"""
import math
import struct

from memory.process_reader import ReadError,valid_pointer,MAX_READ_BYTES
from solo_helper.player_research import pointer_at
from solo_helper import config


# DB1B70的固定构建常量；仅9～13这五项已从只读段核对。
XZ_ENCODING={9:(-128.,1024.,65536.),10:(-256.,1536.,65535.),
             11:(-512.,3072.,65535.),12:(-1024.,6144.,65535.),13:(-2048.,12288.,65535.)}
Y_SCALE=0.06640726327896118


def read_bounded_buffer(memory,address,size):
    """遵守只读层每次8KiB上限，总量不超过512KiB，不提高公共读取权限或限制。"""
    if type(size) is not int or not 0<size<=512*1024 or not valid_pointer(address) or not valid_pointer(address+size-1):
        raise ReadError('基础网格缓冲区读取边界异常')
    return b''.join(memory.read(address+offset,min(MAX_READ_BYTES,size-offset))
                    for offset in range(0,size,MAX_READ_BYTES))


def decode_vertex(raw,level):
    if level not in XZ_ENCODING or len(raw)!=12:
        raise ReadError('未核对的Sdf顶点编码')
    offset,span,divisor=XZ_ENCODING[level]
    x,y,z=struct.unpack_from('<3H',raw)
    # DB1B70先乘后加，Y按独立常量解码；不将法向/其它属性当作坐标。
    return (x*(span/divisor)+offset,y*Y_SCALE-128.,z*(span/divisor)+offset)


def triangle_height(vertices,x,z):
    """水平投影重心坐标，只返回覆盖该XZ的基础三角面高度；竖面/退化面拒绝。"""
    if len(vertices)!=3 or not all(math.isfinite(v) for p in vertices for v in p) or not all(map(math.isfinite,(x,z))):
        raise ReadError('基础三角面坐标异常')
    a,b,c=vertices
    det=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
    if abs(det)<1e-8:
        return None
    u=((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/det
    v=((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/det
    w=1-u-v
    if min(u,v,w)<-1e-7 or max(u,v,w)>1+1e-7:
        return None
    return u*a[1]+v*b[1]+w*c[1]


def array_descriptor(memory,address,stride,limit,guards):
    raw=memory.read(address,16)
    # 此资源缓冲不是hknp的hkArray；末字段应匹配元素步长，长度按字节计。
    # 字节长度必须可整除步长，保守限定元素数，不用末字段当容量扩读。
    data,byte_count,element_size=struct.unpack('<Q2I',raw)
    if (not valid_pointer(data) or element_size!=stride or byte_count%stride
            or not 0<byte_count//stride<=limit):
        raise ReadError(f'Sdf几何数组边界未验证：stride={stride}, bytes={byte_count}, element_size={element_size}, pointer_valid={valid_pointer(data)}')
    guards.append((address,raw))
    return data,byte_count//stride


def inspect_primitive(memory,shape,guards):
    if memory.sha256!=config.EXPECTED_SHA256:
        raise ReadError('Sdf网格研究构建不匹配')
    # 2F4E77..2F4E9E：shape+30为共享对象，首指针为几何资源，+38为primitive ID。
    shared=pointer_at(memory,shape+0x30)
    model=pointer_at(memory,shared)
    identity=memory.read(shape+0x38,4)
    primitive=struct.unpack('<I',identity)[0]
    level_raw=memory.read(model+0x20,4)
    level=struct.unpack('<I',level_raw)[0]
    width_raw=memory.read(model+0x38,1)
    width=width_raw[0]
    if level not in XZ_ENCODING or width not in (2,4):
        raise ReadError(f'Sdf几何编码未验证：level={level}，index_width={width}')
    guards.extend(((shape+0x30,struct.pack('<Q',shared)),(shared,struct.pack('<Q',model)),
                   (shape+0x38,identity),(model+0x20,level_raw),(model+0x38,width_raw)))
    # DB01AC..DB023C：分组24字节、三角形顶点索引、8字节顶点引用、12字节坐标。
    groups,group_count=array_descriptor(memory,model+0xc8,24,65536,guards)
    indices,index_count=array_descriptor(memory,model+0x70,width,2**20,guards)
    references,reference_count=array_descriptor(memory,model+0x40,8,2**20,guards)
    vertices,vertex_count=array_descriptor(memory,model+0x58,12,2**20,guards)
    group=primitive>>8
    if group>=group_count:
        raise ReadError('Sdf分组索引越界')
    group_raw=memory.read(groups+group*24,4)
    triangle=(struct.unpack('<I',group_raw)[0]&0x7fffff)+(primitive&255)
    if triangle*3+2>=index_count:
        raise ReadError('Sdf三角索引越界')
    index_raw=memory.read(indices+triangle*3*width,3*width)
    ids=struct.unpack('<'+('H' if width==2 else 'I')*3,index_raw)
    if any(i>=reference_count for i in ids):
        raise ReadError('Sdf顶点引用越界')
    decoded=[]
    guards.extend(((groups+group*24,group_raw),(indices+triangle*3*width,index_raw)))
    for i in ids:
        ref_raw=memory.read(references+i*8,8)
        vertex=struct.unpack_from('<I',ref_raw)[0]
        if vertex>=vertex_count:
            raise ReadError('Sdf顶点索引越界')
        raw=memory.read(vertices+vertex*12,12)
        guards.extend(((references+i*8,ref_raw),(vertices+vertex*12,raw)))
        decoded.append(decode_vertex(raw,level))
    return dict(primitive_id=primitive,level=level,index_width=width,
                group_count=group_count,index_count=index_count,reference_count=reference_count,
                vertex_count=vertex_count,base_triangle=decoded,
                final_collision_surface_verified=False)


def read_base_mesh(memory,shape,guards):
    """完整读取一个已识别资源的基础三角网格，限总量512KiB；不作为可传送证明。"""
    first=inspect_primitive(memory,shape,guards)
    shared=pointer_at(memory,shape+0x30)
    model=pointer_at(memory,shared)
    refs,nrefs=array_descriptor(memory,model+0x40,8,65536,guards)
    vertices,nvertices=array_descriptor(memory,model+0x58,12,65536,guards)
    indices,nindices=array_descriptor(memory,model+0x70,first['index_width'],196608,guards)
    if nindices%3 or nrefs*8+nvertices*12+nindices*first['index_width']>512*1024:
        raise ReadError('基础地形网格超过有界读取范围')
    ref_raw=read_bounded_buffer(memory,refs,nrefs*8)
    vert_raw=read_bounded_buffer(memory,vertices,nvertices*12)
    index_raw=read_bounded_buffer(memory,indices,nindices*first['index_width'])
    guards.extend(((refs,ref_raw),(vertices,vert_raw),(indices,index_raw),
                   (shape+0x30,struct.pack('<Q',shared)),(shared,struct.pack('<Q',model))))
    ids=struct.unpack('<'+('H' if first['index_width']==2 else 'I')*nindices,index_raw)
    ref_ids=[struct.unpack_from('<I',ref_raw,i*8)[0] for i in range(nrefs)]
    if any(i>=nrefs for i in ids) or any(i>=nvertices for i in ref_ids):
        raise ReadError('基础地形网格顶点引用越界')
    decoded=[decode_vertex(vert_raw[i*12:i*12+12],first['level']) for i in range(nvertices)]
    triangles=[[decoded[ref_ids[ids[i+j]]] for j in range(3)] for i in range(0,nindices,3)]
    return dict(triangles=triangles,triangle_count=len(triangles),
                final_collision_surface_verified=False)
