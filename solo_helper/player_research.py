"""按当前EXE两个脚本getter的只读逻辑定位人物GameObject，不执行游戏函数。"""
import struct
from memory.process_reader import valid_pointer,ReadError


def guid_hash(guid):
    mask = (1 << 64)-1
    words = [(guid >> (16*i)) & 0xffff for i in range(4)]
    value = (words[0]<<48) | (words[1]<<32) | (words[2]<<16) | words[3]
    value = (~value+(value<<21)) & mask
    value ^= value >> 24
    value = value*0x109 & mask
    value ^= value >> 14
    value = value*0x15 & mask
    value ^= value >> 28
    return value*0x80000001 & mask


def pointer_at(memory,address):
    value, = struct.unpack('<Q',memory.read(address,8))
    if not valid_pointer(value):
        raise ReadError('人物结构指针无效，停止研究')
    return value


def find_game_object(memory,character):
    # GetLocalPlayerCharacter: character+8 -> 50F6C0 -> handle+0x86。
    guid_raw = memory.read(character+0x8e,8)
    guid, = struct.unpack('<Q',guid_raw)
    if not guid & ((1 << 48)-1):
        raise ReadError('本地人物对象ID为空')
    key = guid_hash(guid)
    buckets,count = struct.unpack('<2Q',memory.read(memory.base+0x25ac368,16))
    if buckets == 0 or buckets & (buckets-1) or buckets > 1 << 24 or count > 1 << 24:
        raise ReadError('人物对象索引表参数异常')
    table = pointer_at(memory,memory.base+0x25ac388)
    index = key & (buckets-1)
    before_node = pointer_at(memory,table+index*8)
    node, = struct.unpack('<Q',memory.read(before_node,8))
    visited = set()
    for _ in range(64):
        if not node or not valid_pointer(node) or node in visited:
            break
        visited.add(node)
        next_node,node_hash,node_guid,obj = struct.unpack('<4Q',memory.read(node,32))
        if node_hash == key and node_guid == guid:
            if not valid_pointer(obj):
                raise ReadError('人物GameObject指针无效')
            if memory.read(character+0x8e,8) != guid_raw:
                raise ReadError('人物对象在定位期间变化')
            return obj
        if node_hash & (buckets-1) != index:
            break
        node = next_node
    raise ReadError('当前人物对象未在其GUID桶中唯一定位；不搜索其它桶')
