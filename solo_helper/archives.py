"""本机TAB v2、AAF、SARC受限解析；不执行游戏或第三方程序。

格式依据 RyMaxim/cotw-mod-builder/deca，MIT；Jenkins lookup3 原算法允许任意使用。
只提取配置中指定资源，所有长度/名称/解压均有边界检查。
"""
import struct
import zlib
from dataclasses import dataclass
from solo_helper import config


class FormatError(ValueError):
    pass


def rot(value,bits):
    value &= 0xffffffff
    return ((value << bits) | (value >> (32-bits))) & 0xffffffff


def path_hash(path):
    data = path.encode('ascii') if isinstance(path,str) else path
    a = b = c = (0xdeadbeef+len(data)) & 0xffffffff
    cursor = 0
    while len(data)-cursor > 12:
        x,y,z = struct.unpack_from('<3I',data,cursor)
        a,b,c = (a+x)&0xffffffff,(b+y)&0xffffffff,(c+z)&0xffffffff
        a = ((a-c)^rot(c,4))&0xffffffff; c = (c+b)&0xffffffff
        b = ((b-a)^rot(a,6))&0xffffffff; a = (a+c)&0xffffffff
        c = ((c-b)^rot(b,8))&0xffffffff; b = (b+a)&0xffffffff
        a = ((a-c)^rot(c,16))&0xffffffff; c = (c+b)&0xffffffff
        b = ((b-a)^rot(a,19))&0xffffffff; a = (a+c)&0xffffffff
        c = ((c-b)^rot(b,4))&0xffffffff; b = (b+a)&0xffffffff
        cursor += 12
    tail = data[cursor:]
    if not tail:
        return c
    a = (a+int.from_bytes(tail[:4],'little'))&0xffffffff
    b = (b+int.from_bytes(tail[4:8],'little'))&0xffffffff
    c = (c+int.from_bytes(tail[8:12],'little'))&0xffffffff
    c = ((c^b)-rot(b,14))&0xffffffff
    a = ((a^c)-rot(c,11))&0xffffffff
    b = ((b^a)-rot(a,25))&0xffffffff
    c = ((c^b)-rot(b,16))&0xffffffff
    a = ((a^c)-rot(c,4))&0xffffffff
    b = ((b^a)-rot(a,14))&0xffffffff
    c = ((c^b)-rot(b,24))&0xffffffff
    return c


def unpack_aaf(raw):
    if not raw[:4].upper().startswith(b'AAF'):
        return raw,False
    if len(raw) < 48 or raw[8:36] != b'AVALANCHEARCHIVEFORMATISCOOL':
        raise FormatError('AAF头错误')
    version, = struct.unpack_from('<I',raw,4)
    total,section_max,count = struct.unpack_from('<3I',raw,36)
    if version != 1 or not 0 < total <= config.MAX_ASSET_BYTES or not 0 < count <= 16:
        raise FormatError('AAF版本或长度超出范围')
    cursor,parts = 48,[]
    for _ in range(count):
        if cursor+16 > len(raw):
            raise FormatError('AAF节头越界')
        compressed,size,padded,magic = struct.unpack_from('<3I4s',raw,cursor)
        if (magic != b'EWAM' or not 0 < size <= min(section_max,total)
                or padded < compressed+16 or cursor+padded > len(raw)):
            raise FormatError('AAF节边界异常')
        decoder = zlib.decompressobj(-15)
        try:
            part = decoder.decompress(raw[cursor+16:cursor+16+compressed],size+1)
        except zlib.error as exc:
            raise FormatError('AAF压缩内容损坏') from exc
        if len(part) != size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise FormatError('AAF解压长度不匹配')
        parts.append(part)
        cursor += padded
    if sum(map(len,parts)) != total:
        raise FormatError('AAF总长度不匹配')
    return b''.join(parts),True


def pack_aaf(data):
    if not 0 < len(data) <= config.MAX_ASSET_BYTES:
        raise FormatError('AAF输出长度异常')
    size = 32*1024*1024
    result = bytearray(b'AAF\0'+struct.pack('<I',1)+b'AVALANCHEARCHIVEFORMATISCOOL')
    result += struct.pack('<3I',len(data),size,(len(data)+size-1)//size)
    for cursor in range(0,len(data),size):
        part = data[cursor:cursor+size]
        encoder = zlib.compressobj(6,zlib.DEFLATED,-15)
        compressed = encoder.compress(part)+encoder.flush()
        padded = (16+len(compressed)+15)//16*16
        result += struct.pack('<3I4s',len(compressed),len(part),padded,b'EWAM')
        result += compressed+b'0'*(padded-16-len(compressed))
    return bytes(result)


def extract_tab_resource(path,*,research_only=False):
    allowed = config.ASSET_PATHS + (config.RESEARCH_ASSET_PATHS if research_only else ())
    if path not in allowed:
        raise FormatError('未授权的资源路径')
    key = path_hash(path)
    candidates = []
    for tab in (config.GAME_DIR/'archives_win64').glob('*.tab'):
        data = tab.read_bytes()
        if data[:8] != b'TAB\0\x02\0\x01\0' or (len(data)-12)%12:
            raise FormatError('不支持的TAB格式：'+tab.name)
        for offset in range(12,len(data),12):
            name,start,size = struct.unpack_from('<3I',data,offset)
            if name == key:
                candidates.append((tab.with_suffix('.arc'),start,size))
    if len(candidates) != 1:
        raise FormatError(f'{path} 匹配{len(candidates)}个资源；拒绝猜测覆盖顺序')
    arc,offset,size = candidates[0]
    if not 0 < size <= config.MAX_ASSET_BYTES or offset+size > arc.stat().st_size:
        raise FormatError('ARC资源边界异常')
    with arc.open('rb') as stream:
        stream.seek(offset)
        data = stream.read(size)
    if len(data) != size:
        raise FormatError('ARC读取不完整')
    return data,dict(archive=arc.name,offset=offset,size=size,path=path)


@dataclass(frozen=True)
class SarcEntry:
    name: str
    offset: int
    size: int


class Sarc:
    def __init__(self,raw):
        self.data,self.compressed = unpack_aaf(raw)
        data = self.data
        if len(data) < 20:
            raise FormatError('SARC过短')
        version,magic,variant,length = struct.unpack_from('<I4s2I',data)
        if version != 4 or magic != b'SARC' or variant not in (2,3) or 16+length > len(data):
            raise FormatError('只支持SARC v2/v3')
        self.entries = {}
        if variant == 2:
            cursor = 16
            while cursor < 16+length:
                name_size, = struct.unpack_from('<I',data,cursor)
                if name_size == 0 and not any(data[cursor:16+length]):
                    break  # 对齐填充，不是空路径条目
                if not 0 < name_size <= 4096 or cursor+12+name_size > 16+length:
                    raise FormatError('SARC v2目录越界')
                name = data[cursor+4:cursor+4+name_size].rstrip(b'\0').decode('ascii')
                offset,size = struct.unpack_from('<2I',data,cursor+4+name_size)
                if name in self.entries or (offset and (offset < 16+length or offset+size > len(data))):
                    raise FormatError('SARC v2资源边界异常')
                self.entries[name] = SarcEntry(name,offset,size)
                cursor += 12+name_size
            return
        size, = struct.unpack_from('<I',data,16)
        if size > length-4:
            raise FormatError('SARC名称表越界')
        names = data[20:20+size]
        cursor = 20+size
        for name in names.split(b'\0'):
            if not name:
                continue
            string_offset,offset,count,key,extension = struct.unpack_from('<5I',data,cursor)
            cursor += 20
            decoded = name.decode('ascii')
            if (cursor > 16+length or key != path_hash(name) or decoded in self.entries
                    or (offset and (offset < 16+length or offset+count > len(data)))):
                raise FormatError('SARC条目或哈希异常')
            self.entries[decoded] = SarcEntry(decoded,offset,count)

    def extract(self,path):
        entry = self.entries[path]
        if not entry.offset:
            raise FormatError('该资源为外部引用，不能从此容器提取')
        return self.data[entry.offset:entry.offset+entry.size]

    def replace_same_size(self,path,payload):
        entry = self.entries[path]
        if not entry.offset or len(payload) != entry.size:
            raise FormatError('只允许同长度替换已嵌入资源')
        result = bytearray(self.data)
        result[entry.offset:entry.offset+entry.size] = payload
        return pack_aaf(bytes(result)) if self.compressed else bytes(result)
