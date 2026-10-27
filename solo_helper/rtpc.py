"""有界RTPC v2只读解析；格式参照MIT许可Mod Builder的deca/ff_rtpc.py。

独立实现边界与唯一性检查，不导入/执行第三方模块；只提供已明确类型的值位置。
"""
from dataclasses import dataclass
import math
import struct
from solo_helper.archives import FormatError


@dataclass(frozen=True)
class Property:
    name_hash: int
    kind: int
    offset: int | None
    value: object


@dataclass(frozen=True)
class Node:
    name_hash: int
    properties: tuple[Property,...]
    children: tuple['Node',...]


class Rtpc:
    def __init__(self,raw):
        if len(raw)<20 or raw[:4]!=b'RTPC' or struct.unpack_from('<I',raw,4)[0]!=2:
            raise FormatError('仅支持经过研究的RTPC v2')
        if len(raw)>16*1024*1024:
            raise FormatError('RTPC超过研究大小限制')
        self.raw = raw
        self.visited = set()
        self.property_count = 0
        self.root = self.node(8,0)

    def bounds(self,offset,size):
        if not 0<=offset<=len(self.raw) or not 0<=size<=len(self.raw)-offset:
            raise FormatError('RTPC数据越界')

    def node(self,position,depth):
        self.bounds(position,12)
        if position in self.visited or depth>24 or len(self.visited)>=10000:
            raise FormatError('RTPC循环、重复节点或层级过深')
        self.visited.add(position)
        name,data,pc,cc = struct.unpack_from('<2I2H',self.raw,position)
        self.property_count += pc
        if self.property_count>100000:
            raise FormatError('RTPC属性数量异常')
        self.bounds(data,pc*9)
        child_offset = (data+pc*9+3)&~3
        if cc:
            self.bounds(child_offset,cc*12)
        props = []
        keys = set()
        for i in range(pc):
            offset = data+i*9
            key,value,kind = struct.unpack_from('<2IB',self.raw,offset)
            # 本机RTPC存在保留的全零none槽，不是重复的业务字段；仍计入长度边界。
            if key==value==kind==0:
                continue
            if key in keys:
                raise FormatError(f'RTPC节点{position:#x}/{name:#x}存在同名属性{key:#x}，拒绝含糊解释')
            keys.add(key)
            actual = offset+4
            if kind in (0,1):
                decoded = value
            elif kind==2:
                decoded, = struct.unpack_from('<f',self.raw,actual)
                if not math.isfinite(decoded):
                    raise FormatError('RTPC浮点属性异常')
            elif kind==3:
                self.bounds(value,1)
                end = self.raw.find(b'\0',value,min(value+65536,len(self.raw)))
                if end<0:
                    raise FormatError('RTPC字符串未终止')
                try:
                    decoded = self.raw[value:end].decode('utf-8')
                except UnicodeDecodeError as exc:
                    raise FormatError('RTPC字符串编码异常') from exc
                actual = value
            else:
                # 非本任务目标类型不猜布局、不对外提供可写位置。
                decoded,actual = None,None
            props.append(Property(key,kind,actual,decoded))
        children = tuple(self.node(child_offset+i*12,depth+1) for i in range(cc))
        return Node(name,tuple(props),children)

    def walk(self,node=None):
        node = self.root if node is None else node
        yield node
        for child in node.children:
            yield from self.walk(child)
