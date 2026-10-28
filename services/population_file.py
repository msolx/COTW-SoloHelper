"""受限的 SAVE/ADF 只读解析。存档字段不是实时位置，禁止按邻近坐标关联实体。

格式线索来自公开 ADF 研究及 apc-pw/deca 读取结构；本模块独立实现，
没有第三方程序调用、存档写入、进程写入或“修改种群”接口。
"""
from dataclasses import dataclass
import math
import struct
import zlib
import config


class PopulationError(ValueError):
    pass


def stable_read(path):
    """游戏可能正在保存：同一文件连续两次只读并比对，变化则拒绝当前采样。"""
    before = path.stat()
    if not 32 <= before.st_size <= config.POPULATION_MAX_BYTES:
        raise PopulationError('种群文件大小异常')
    with path.open('rb') as stream:
        first = stream.read(config.POPULATION_MAX_BYTES+1)
    with path.open('rb') as stream:
        second = stream.read(config.POPULATION_MAX_BYTES+1)
    after = path.stat()
    if ((before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns)
            or len(first) != before.st_size or first != second):
        raise PopulationError('种群文件在读取时发生变化，请等待保存结束')
    return first,after.st_mtime


def decompress_population(raw):
    if len(raw) < 32 or raw[:4] != b'SAVE' or raw[16:20] != b'COMP':
        raise PopulationError('不支持的种群压缩容器')
    declared = struct.unpack_from('<I',raw,8)[0]
    if not 5 < declared <= config.POPULATION_MAX_BYTES:
        raise PopulationError('解压长度异常')
    try:
        decoder = zlib.decompressobj()
        data = decoder.decompress(raw[32:],declared+1)
    except zlib.error as exc:
        raise PopulationError('种群文件压缩数据损坏') from exc
    if (len(data) != declared or not decoder.eof or decoder.unused_data
            or decoder.unconsumed_tail or data[5:9] != b' FDA'):
        raise PopulationError('种群解压长度或 ADF 标识不匹配')
    return data[5:]


@dataclass(frozen=True)
class Node:
    name: str
    offset: int
    size: int
    value: object


class PopulationADF:
    """只支持本研究所需的基本 ADF 类型；未知类型/越界/递归过深立即拒绝。"""
    PRIMITIVES = {0x580D0A62:'b',0x0CA2821D:'B',0xD13FCF93:'h',0x86D152BD:'H',
                  0x192FE633:'i',0x075E4E4F:'I',0xAF41354F:'q',0xA139E01F:'Q',
                  0x7515A207:'f',0xC609F663:'d'}

    def __init__(self,data):
        self.data = data
        self.nodes = 0
        if len(data) < 64 or data[:4] != b' FDA':
            raise PopulationError('ADF头错误')
        version,instances,instance_offset,types,type_offset,hash_count,hash_offset,names,name_offset,total = self.unpack('<10I',4)
        if (version != 4 or total != len(data) or not 1 <= instances <= 16
                or not 1 <= types <= 2048 or names > 4096 or hash_count or hash_offset):
            raise PopulationError('不支持的ADF版本或表长度')
        lengths = self.take(name_offset,names)
        cursor = name_offset+names
        self.names = []
        for size in lengths:
            raw = self.take(cursor,size+1)
            if raw[-1] != 0:
                raise PopulationError('ADF名称未终止')
            self.names.append(raw[:-1].decode('utf-8'))
            cursor += size+1
        self.types = {}
        cursor = type_offset
        for _ in range(types):
            meta,size,alignment,key,name,flags,element,count = self.unpack('<4IQ3I',cursor)
            cursor += 36
            if size > config.POPULATION_MAX_BYTES or key in self.types:
                raise PopulationError('ADF类型表异常')
            members = []
            if meta != 0:
                entries, = self.unpack('<I',cursor)
                cursor += 4
                if entries > 1024:
                    raise PopulationError('ADF成员过多')
                if meta == 1:
                    for _ in range(entries):
                        n,t,s,offset,default,value = self.unpack('<Q4IQ',cursor)
                        cursor += 32
                        members.append((self.name(n),t,offset & 0xffffff,offset >> 24))
                elif meta == 8:
                    self.take(cursor,entries*12)
                    cursor += entries*12
                elif meta not in (2,3,4,7,9) or entries:
                    raise PopulationError(f'不支持的ADF类型 {meta}')
            self.types[key] = dict(meta=meta,size=size,name=self.name(name),element=element,count=count,members=members)
        self.roots = []
        for index in range(instances):
            _,key,offset,size,name = self.unpack('<4IQ',instance_offset+index*24)
            payload = self.take(offset,size)
            self.roots.append(self.decode(payload,key,0,offset,0))

    def take(self,offset,size):
        if offset < 0 or size < 0 or offset+size > len(self.data):
            raise PopulationError('ADF读取越界')
        return self.data[offset:offset+size]

    def unpack(self,fmt,offset):
        return struct.unpack(fmt,self.take(offset,struct.calcsize(fmt)))

    def name(self,index):
        if not 0 <= index < len(self.names):
            raise PopulationError('ADF名称索引越界')
        return self.names[index]

    def decode(self,payload,key,pos,base,depth,bit=0):
        self.nodes += 1
        if depth > 32 or self.nodes > config.POPULATION_MAX_NODES:
            raise PopulationError('ADF结构超出解析预算')
        primitive = self.PRIMITIVES.get(key)
        spec = self.types.get(key)
        size = struct.calcsize('<'+primitive) if primitive else spec['size'] if spec else 0
        if not size or pos < 0 or pos+size > len(payload):
            raise PopulationError('ADF实例类型未知或越界')
        name = spec['name'] if spec else primitive
        if primitive:
            value = struct.unpack_from('<'+primitive,payload,pos)[0]
        elif spec['meta'] == 1:
            value = {n:self.decode(payload,t,pos+o,base,depth+1,b)
                     for n,t,o,b in spec['members']}
        elif spec['meta'] in (3,4):
            if spec['meta'] == 3:
                offset,flags,count = struct.unpack_from('<3I',payload,pos)
            else:
                offset,count = pos,spec['count']
            element = spec['element']
            stride = struct.calcsize('<'+self.PRIMITIVES[element]) if element in self.PRIMITIVES else self.types.get(element,{}).get('size',0)
            if (count > config.POPULATION_MAX_NODES or not stride or offset < 0
                    or offset+count*stride > len(payload)):
                raise PopulationError('ADF数组越界或类型异常')
            value = [self.decode(payload,element,offset+i*stride,base,depth+1) for i in range(count)]
        elif spec['meta'] in (7,8,9) and size in (1,2,4,8):
            value = int.from_bytes(payload[pos:pos+size],'little')
            if spec['meta'] == 7:
                if bit >= size*8:
                    raise PopulationError('ADF位域越界')
                value = (value >> bit) & 1
        else:
            raise PopulationError(f'尚不支持的ADF实例类型：{name}')
        return Node(name,base+pos,size,value)


def animal_nodes(node):
    """仅识别含明确字段的记录；Id可能为0，不据此当作永久标识。"""
    if isinstance(node.value,dict):
        fields = node.value
        if {'Gender','Weight','Score','VisualVariationSeed'} <= fields.keys():
            sex = fields['Gender'].value
            if sex not in (1,2) or not all(math.isfinite(fields[k].value) for k in ('Weight','Score')):
                raise PopulationError('动物记录性别或数值异常')
            yield node
        else:
            for child in fields.values():
                yield from animal_nodes(child)
    elif isinstance(node.value,list):
        for child in node.value:
            yield from animal_nodes(child)
