"""只读核对FOXPRO范围运行时定义；不搜索任意内存、不写参数、不执行游戏函数。"""
import hashlib
import json
import math
import struct
import time

from memory.process_reader import ProcessReader,ReadError
from solo_helper import config
from solo_helper.player_research import pointer_at
from solo_helper.sdf_mesh_research import read_bounded_buffer
from solo_helper.caller_patch import remote_calls,ORIGINAL_SHA256
from solo_helper.rtpc import Rtpc


def summarize_definitions(table,expected):
    if len(table)!=255*0x78:
        raise ReadError('叫声定义表长度异常')
    found={key:[] for key in expected}
    for index in range(255):
        identity=struct.unpack_from('<I',table,index*0x78)[0]
        if identity in found:
            value=struct.unpack_from('<f',table,index*0x78+0x10)[0]
            if not math.isfinite(value) or not 0<value<10000:
                raise ReadError('电子哨定义范围数值异常')
            found[identity].append(value)
    if not expected or any(len(values)!=1 for values in found.values()):
        raise ReadError('未唯一找到全部已核对电子哨定义')
    counts={}
    for values in found.values():
        key=str(values[0])
        counts[key]=counts.get(key,0)+1
    matched=all(values[0]==config.FOXPRO_RANGE_METERS for values in found.values())
    return dict(remote_entries=len(expected),runtime_range_counts=counts,
                configured_range_m=config.FOXPRO_RANGE_METERS,runtime_parameter_verified=matched,
                attraction_response_verified=False,attraction_success_changed=False)


def inspect_caller_ranges(memory,raw):
    if memory.sha256!=config.EXPECTED_SHA256 or hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA256:
        raise ReadError('电子哨范围核对版本不符')
    calls=remote_calls(Rtpc(raw))
    expected={node.name_hash for node in calls}
    # 95FDC7构造8E5FC0后存世界服务+D0；构造器固定255项、每项78，数组从60开始。
    manager=pointer_at(memory,memory.base+0x27c5dc8)
    definitions=pointer_at(memory,manager+0xd0)
    vtable=pointer_at(memory,definitions)
    if vtable!=memory.base+0x1def7b0 or memory.read(definitions+0x77f8,1)!=b'\1':
        raise ReadError('电子哨定义对象类型或加载状态未核对')
    # 904624/904656把RTPC range存入记录+10，即定义对象+60数组起点再加10。
    table=read_bounded_buffer(memory,definitions+0x60,255*0x78)
    result=summarize_definitions(table,expected)
    counts={}
    response_count=0
    sampled=[]
    for node in calls:
        slots=[i for i in range(255) if struct.unpack_from('<I',table,i*0x78)[0]==node.name_hash]
        slot=slots[0]  # summarize_definitions已确认每个目标唯一
        record=slot*0x78
        if table[record+0x51]!=5:
            raise ReadError('电子哨运行时类型不是5')
        start,end,capacity=struct.unpack_from('<3Q',table,record+0x58)
        size=len(node.children)*0x34
        if not start or end-start!=size or not end<=capacity<=start+256*0x34:
            raise ReadError('电子哨物种响应向量边界异常')
        payload=read_bounded_buffer(memory,start,size)
        sampled.append((start,payload))
        species=[next(p.value for p in child.properties if p.name_hash==0x19b8918c)
                 for child in node.children]
        for index,identity in enumerate(species):
            if payload[index*0x34]!=identity:
                raise ReadError('电子哨响应物种顺序与原始资源不同')
            # 9123E0加载六档基础概率，8FD700实际消费这些字段。
            values=struct.unpack_from('<6f',payload,index*0x34+0x1c)
            if any(not math.isfinite(value) or not 0<=value<=1 for value in values):
                raise ReadError('电子哨运行时基础概率超出0～1')
            response_count+=1
            for value in values:
                key=str(value)
                counts[key]=counts.get(key,0)+1
    if response_count!=165:
        raise ReadError('电子哨响应记录数量异常')
    if any(read_bounded_buffer(memory,address,len(payload))!=payload for address,payload in sampled):
        raise ReadError('电子哨基础概率在采样期间变化')
    result.update(runtime_probability_counts=counts,response_entries=response_count,
                  base_probability_100_verified=counts=={'1.0':990},
                  attraction_success_changed=counts=={'1.0':990})
    if (pointer_at(memory,memory.base+0x27c5dc8)!=manager
            or pointer_at(memory,manager+0xd0)!=definitions
            or pointer_at(memory,definitions)!=vtable or memory.read(definitions+0x77f8,1)!=b'\1'
            or read_bounded_buffer(memory,definitions+0x60,255*0x78)!=table):
        raise ReadError('电子哨定义在采样期间改变')
    return result


def run():
    memory=ProcessReader()
    report=dict(timestamp=time.time(),write_attempted=False)
    try:
        memory.connect()
        raw=(config.WORK/'research_assets/animal_interest.bin').read_bytes()
        result=inspect_caller_ranges(memory,raw)
        report.update(status='runtime_parameter_verified' if result['runtime_parameter_verified'] else 'runtime_values_differ',**result)
    except Exception as exc:
        report.update(status='stopped',error=str(exc))
    finally:
        memory.close()
        report['handle_closed']=memory.handle is None
    (config.ROOT/'caller_runtime_range_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return report


if __name__=='__main__':
    run()
