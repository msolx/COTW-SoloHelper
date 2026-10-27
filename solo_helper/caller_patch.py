"""FOXPRO范围的离线候选：不安装、不改吸引率显示冒充AI效果。"""
import hashlib
import math
import struct
from solo_helper.archives import FormatError
from solo_helper.rtpc import Rtpc


ORIGINAL_SHA256 = 'abf8de31842a080ed7546a853b4c6a9b2d220be0cc8c694c12310b5cb148aae2'
REMOTE_RANGE = 0x7c01072c  # Mod Builder modify_lures.py: 2080442156
REMOTE_TYPE = 0xec29c1ef
CALL_LABEL = 0xa3487d5b
EXPECTED_REMOTE_CALLS = 86  # 当前EXE对应本地文件中的电子哨物种/叫声条目
RESPONSE_GROUPS = (0x4ae67b86, 0x85dd574b)
RESPONSE_CHANCES = (0xdb4b6ca7, 0x816cbd37, 0x8d20b303)


def chance_properties(tree):
    """仅返回电子哨的两组、各三档概率；不触碰手持哨/气味条目。

    当前构建9123E0将其加载到响应记录+1C..30；8FDE57取值，
    8FDEC2调用[0,1)随机数并比较。它是基础概率，游戏其它条件仍存在。
    """
    found = []
    responses = 0
    for call in remote_calls(tree):
        for response in call.children:
            responses += 1
            groups = {n.name_hash:n for n in response.children}
            if len(groups)!=2 or set(groups)!=set(RESPONSE_GROUPS):
                raise FormatError('电子哨概率分组与当前版本不一致')
            for group in RESPONSE_GROUPS:
                props = {p.name_hash:p for p in groups[group].properties}
                if set(props)!=set(RESPONSE_CHANCES):
                    raise FormatError('电子哨概率档位不完整')
                for key in RESPONSE_CHANCES:
                    prop = props[key]
                    if prop.kind!=2 or prop.offset is None or not 0<=prop.value<=1:
                        raise FormatError('电子哨基础概率不是有效的0～1浮点数')
                    found.append(prop)
    if responses!=165 or len(found)!=990 or len({p.offset for p in found})!=990:
        raise FormatError('电子哨响应数量或概率字段别名异常')
    return found


def compile_remote_profile(raw,distance=400.0):
    """400米+100%基础概率测试版；仍要求退出游戏后由安装器安装。"""
    ranged,details = compile_remote_range(raw,distance)
    properties = chance_properties(Rtpc(raw))
    result = bytearray(ranged)
    for prop in properties:
        struct.pack_into('<f',result,prop.offset,1.0)
    # 990个概率与86个范围之外必须逐字节不变。
    offsets = details['range_offsets']+[p.offset for p in properties]
    allowed = {i for offset in offsets for i in range(offset,offset+4)}
    if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(raw,result))):
        raise FormatError('电子哨范围/基础概率之外出现改动')
    if any(p.value!=1.0 for p in chance_properties(Rtpc(bytes(result)))):
        raise FormatError('电子哨基础概率复读失败')
    details.update(attraction_success_changed=True,base_probability=1.0,
                   probability_fields=len(properties),probability_offsets=[p.offset for p in properties],
                   new_sha256=hashlib.sha256(result).hexdigest(),
                   note='电子哨400米、全部基础概率100%；不修改面板数值，不保证绕过警觉、适用物种等其它AI条件；真实加载待核对')
    return bytes(result),details


def remote_calls(rtpc):
    calls = []
    for node in rtpc.root.children:
        props = {p.name_hash:p for p in node.properties}
        label,kind = props.get(CALL_LABEL),props.get(REMOTE_TYPE)
        if label is not None and label.kind==3 and label.value.startswith('ui_remote_caller_call_type_'):
            if kind is None or kind.kind!=1 or kind.value!=5:
                raise FormatError('电子哨叫声标签与实际类型不一致')
            calls.append(node)
    if len(calls)!=EXPECTED_REMOTE_CALLS:
        raise FormatError('电子哨叫声条目数量与当前版本核对记录不符')
    return calls


def compile_remote_range(raw,distance=400.0):
    if type(distance) not in (int,float) or not math.isfinite(distance) or not 200<=distance<=400:
        raise ValueError('本阶段电子哨范围只允许200～400米')
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA256:
        raise FormatError('动物兴趣资源哈希与本次核对版本不同')
    tree = Rtpc(raw)
    result = bytearray(raw)
    offsets = []
    for node in remote_calls(tree):
        ranges = [p for p in node.properties if p.name_hash==REMOTE_RANGE]
        if len(ranges)!=1 or ranges[0].kind!=2 or ranges[0].value!=200.0:
            raise FormatError('电子哨范围字段不唯一或原值不是200米')
        offset = ranges[0].offset
        struct.pack_into('<f',result,offset,distance)
        offsets.append(offset)
    if len(set(offsets))!=len(offsets):
        raise FormatError('电子哨范围字段别名异常')
    allowed = {i for offset in offsets for i in range(offset,offset+4)}
    if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(raw,result))):
        raise FormatError('存在电子哨范围之外的改动')
    after = Rtpc(bytes(result))
    if any(p.value!=distance for n in remote_calls(after) for p in n.properties if p.name_hash==REMOTE_RANGE):
        raise FormatError('电子哨范围复读失败')
    return bytes(result),dict(distance=distance,remote_call_entries=len(offsets),range_offsets=offsets,
                             original_sha256=ORIGINAL_SHA256,new_sha256=hashlib.sha256(result).hexdigest(),
                             runtime_or_game_verified=False,attraction_success_changed=False,
                             ui_stat_changed=False,installed=False,
                             note='只生成400米物理范围候选；未定位真实成功率，不把UI的40改100冒充吸引生效')
