"""扩展现有只读ADF解析器以读取游戏参数中的String类型；不修改雷达解析器。"""
import struct
from services.population_file import PopulationADF,PopulationError,Node


class GameADF(PopulationADF):
    STRING = 0x8955583e
    PRIMITIVES = dict(PopulationADF.PRIMITIVES,**{})
    PRIMITIVES[STRING] = 'Q'  # 数组中的字符串描述符占8字节，内容由下方单独解析

    def decode(self,payload,key,pos,base,depth,bit=0):
        if key != self.STRING:
            return super().decode(payload,key,pos,base,depth,bit)
        self.nodes += 1
        if depth > 32 or self.nodes > 200000 or pos < 0 or pos+8 > len(payload):
            raise PopulationError('ADF字符串描述符越界')
        offset,length = struct.unpack_from('<2I',payload,pos)
        if not 0 <= offset < len(payload):
            raise PopulationError('ADF字符串指针越界')
        end = payload.find(b'\0',offset,min(offset+65536,len(payload)))
        if end < 0:
            raise PopulationError('ADF字符串未终止')
        return Node('String',base+pos,8,payload[offset:end].decode('utf-8'))
