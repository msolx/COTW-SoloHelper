"""当前构建的最小参数Mod生成器：不写内存、存档、原始ARC或Steam配置。"""
import hashlib
import json
import math
import re
import struct
from solo_helper import config
from solo_helper.adf import GameADF
from solo_helper.archives import Sarc,extract_tab_resource,FormatError


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_build():
    with config.GAME_EXE.open('rb') as stream:
        actual = hashlib.file_digest(stream,'sha256').hexdigest()
    manifest = config.MANIFEST.read_text(encoding='utf-8')
    match = re.search(r'"buildid"\s+"(\d+)"',manifest,re.IGNORECASE)
    if actual != config.EXPECTED_SHA256 or not match or match[1] != config.EXPECTED_BUILD:
        raise FormatError('不支持当前游戏构建：EXE哈希/Steam buildid不匹配，未生成或安装')
    return dict(sha256=actual,steam_build=match[1])


def verify_asset(data,name):
    if digest(data) != config.ORIGINAL_HASHES[name]:
        raise FormatError(name+'与当前已检查原始资源哈希不符，拒绝覆盖其它Mod')


def patch_movement(raw,multiplier):
    if type(multiplier) not in (float,int) or not math.isfinite(multiplier) or not 1 <= multiplier <= config.MAX_CROUCH_MULTIPLIER:
        raise ValueError(f'普通蹲行倍率必须在1～{config.MAX_CROUCH_MULTIPLIER:g}之间')
    verify_asset(raw,'elmer_movement.mtunec')
    adf = GameADF(raw)
    settings = adf.roots[0].value['FpsSettings'].value
    normal = settings['KeyboardStanceCrouchSpeedModifier']
    sprint = settings['KeyboardStanceCrouchSprintModifier']
    if (normal.name,normal.value,sprint.name,sprint.value) != ('f',.5,'f',2.0):
        raise FormatError('当前蹲行字段语义/默认值与已检查资源不一致')
    result = bytearray(raw)
    # SprintModifier是相对基础蹲速的倍率；反向补偿，避免Shift蹲行一起加速。
    struct.pack_into('<f',result,normal.offset,normal.value*multiplier)
    struct.pack_into('<f',result,sprint.offset,sprint.value/multiplier)
    after = GameADF(bytes(result)).roots[0].value['FpsSettings'].value
    if not math.isclose(after['KeyboardStanceCrouchSpeedModifier'].value*
                        after['KeyboardStanceCrouchSprintModifier'].value,1.0,rel_tol=1e-6):
        raise FormatError('Shift蹲行补偿校验失败')
    allowed = set(range(normal.offset,normal.offset+4)) | set(range(sprint.offset,sprint.offset+4))
    if any(a != b and i not in allowed for i,(a,b) in enumerate(zip(raw,result))):
        raise FormatError('移动资源出现非预期改动')
    return bytes(result),dict(normal_offset=normal.offset,sprint_offset=sprint.offset,
        normal_before=normal.value,normal_after=after['KeyboardStanceCrouchSpeedModifier'].value,
        shift_product_before=normal.value*sprint.value,
        shift_product_after=after['KeyboardStanceCrouchSpeedModifier'].value*after['KeyboardStanceCrouchSprintModifier'].value,
        changed_bytes=sum(a != b for a,b in zip(raw,result)))


def get_cell(adf,sheet_name,column,row):
    book = adf.roots[0].value
    matches = [s.value for s in book['Sheet'].value if s.value['Name'].value == sheet_name]
    if len(matches) != 1:
        raise FormatError('参数表名称不唯一')
    sheet = matches[0]
    if not 1 <= column <= sheet['Cols'].value or not 1 <= row <= sheet['Rows'].value:
        raise FormatError('参数表坐标越界')
    index = sheet['CellIndex'].value[(row-1)*sheet['Cols'].value+column-1].value
    cell = book['Cell'].value[index].value
    if cell['Type'].value != 1:
        raise FormatError('目标单元格不是字符串参数')
    value = book['StringData'].value[cell['DataIndex'].value]
    return cell,value


def patch_capacity(raw,capacity):
    if type(capacity) not in (float,int) or not math.isfinite(capacity) or not 1 <= capacity <= 999 or int(capacity) != capacity:
        raise ValueError('基础负重须为1～999的整数kg')
    capacity = int(capacity)
    verify_asset(raw,'player_skills.bin')
    adf = GameADF(raw)
    _,description = get_cell(adf,'skill_component_descriptions',1,44)
    if description.value != 'set_player_carry_capacity(KG)':
        raise FormatError('基础负重单元格功能标识不符')
    targets = [('skill_component_descriptions',2,44,'(20.0)',f'({capacity})'),
               ('skills_strategic',7,11,'set_player_carry_capacity(23.0)',f'set_player_carry_capacity({capacity})')]
    result = bytearray(raw)
    ranges = []
    for sheet,col,row,expected,replacement in targets:
        cell,node = get_cell(adf,sheet,col,row)
        if node.value != expected:
            raise FormatError('负重参数的默认值与已检查版本不符')
        # 确认字符串值未被其它单元格共享，也未被其它字符串描述符别名引用。
        refs = [c for c in adf.roots[0].value['Cell'].value if c.value['Type'].value == 1 and
                c.value['DataIndex'].value == cell['DataIndex'].value]
        relative, = struct.unpack_from('<I',raw,node.offset)
        aliases = [n for n in adf.roots[0].value['StringData'].value
                   if struct.unpack_from('<I',raw,n.offset)[0] == relative]
        if len(refs) != 1 or len(aliases) != 1:
            raise FormatError('负重字符串被共享，拒绝连带修改其它机制')
        original = expected.encode()+b'\0'
        content = replacement.encode()+b'\0'
        if len(content) > len(original):
            raise FormatError('新参数超出原有字符串空间，拒绝改动ADF布局')
        offset = adf.roots[0].offset+relative
        if raw[offset:offset+len(original)] != original:
            raise FormatError('负重字符串内容不匹配')
        result[offset:offset+len(original)] = content.ljust(len(original),b'\0')
        ranges.append((offset,len(original)))
    # 基础512，已学Pack Mule亦设为512，防止原技能的23kg绝对值将新上限覆盖回去。
    after = GameADF(bytes(result))
    for sheet,col,row,expected,replacement in targets:
        if get_cell(after,sheet,col,row)[1].value != replacement:
            raise FormatError('生成的负重参数复读不匹配')
    allowed = {i for offset,size in ranges for i in range(offset,offset+size)}
    if any(a != b and i not in allowed for i,(a,b) in enumerate(zip(raw,result))):
        raise FormatError('负重资源出现非预期改动')
    return bytes(result),dict(base_capacity=capacity,pack_mule_capacity=capacity,
                             changed_ranges=ranges,changed_bytes=sum(a != b for a,b in zip(raw,result)))


def patch_spotting(raw,seconds=config.SPOTTING_SECONDS):
    """只延长Tag两个等级的时间参数，保持同时可标记数量与技能解锁条件。"""
    if type(seconds) is not int or not 120<=seconds<=999:
        raise ValueError('动物高亮时长必须为120～999的整数秒')
    verify_asset(raw,'player_skills.bin')
    adf=GameADF(raw)
    result=bytearray(raw)
    ranges=[]
    targets=((7,'tag(1.5, 1)',f'tag({seconds}, 1)'),
             (9,'tag(2.0, 3)',f'tag({seconds}, 3)'))
    for column,expected,replacement in targets:
        cell,node=get_cell(adf,'skills_passive',column,9)
        if node.value!=expected:
            raise FormatError('Tag技能时长原值与当前构建不符')
        refs=[c for c in adf.roots[0].value['Cell'].value if c.value['Type'].value==1
              and c.value['DataIndex'].value==cell['DataIndex'].value]
        relative=struct.unpack_from('<I',raw,node.offset)[0]
        aliases=[n for n in adf.roots[0].value['StringData'].value
                 if struct.unpack_from('<I',raw,n.offset)[0]==relative]
        if len(refs)!=1 or len(aliases)!=1:
            raise FormatError('Tag字符串存在共享引用，拒绝连带修改')
        offset=adf.roots[0].offset+relative
        content=replacement.encode()+b'\0'
        original=expected.encode()+b'\0'
        if len(content)!=len(original) or raw[offset:offset+len(original)]!=original:
            raise FormatError('Tag替换长度/内容不匹配，拒绝改变ADF布局')
        result[offset:offset+len(content)]=content
        ranges.append((offset,len(content)))
    after=GameADF(bytes(result))
    if any(get_cell(after,'skills_passive',col,9)[1].value!=replacement
           for col,_,replacement in targets):
        raise FormatError('Tag高亮时长复读失败')
    allowed={i for offset,size in ranges for i in range(offset,offset+size)}
    if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(raw,result))):
        raise FormatError('Tag时间之外出现改动')
    return bytes(result),dict(seconds=seconds,changed_ranges=ranges,requires_tag_skill=True,
                             spottable_counts_unchanged=[1,3],in_game_verified=False)


def build(multiplier=config.CROUCH_MULTIPLIER,capacity=config.BASE_CAPACITY_KG,
          crouch_enabled=True,capacity_enabled=True,foxpro_enabled=False,
          spotting_enabled=False,spotting_seconds=config.SPOTTING_SECONDS):
    report = dict(version=verify_build(),features={},files=[],in_game_verified=False,
                  singleplayer_mode='人工确认；静态参数Mod不能自动拦截多人菜单',
                  teleport='独立运行时功能，不包含在本静态Mod资源中')
    output = config.OUTPUT/'active'
    output.mkdir(parents=True,exist_ok=True)
    payloads = {}
    if crouch_enabled:
        archive,source = extract_tab_resource(config.LOCAL_PLAYER_PATH)
        sarc = Sarc(archive)
        raw = sarc.extract(config.MOVEMENT_PATH)
        patched,details = patch_movement(raw,multiplier)
        encoded = sarc.replace_same_size(config.MOVEMENT_PATH,patched)
        verified = Sarc(encoded)
        if verified.entries != sarc.entries or verified.extract(config.MOVEMENT_PATH) != patched:
            raise FormatError('重打包后的玩家资源未通过校验')
        # 解压后仅允许移动资源中的两个float变化，不改其它嵌入文件或容器目录。
        entry = sarc.entries[config.MOVEMENT_PATH]
        if (sarc.data[:entry.offset] != verified.data[:entry.offset] or
                sarc.data[entry.offset+entry.size:] != verified.data[entry.offset+entry.size:]):
            raise FormatError('重打包影响了其它资源')
        payloads[config.LOCAL_PLAYER_PATH] = encoded
        report['features']['crouch'] = dict(multiplier=multiplier,source=source,details=details)
    if capacity_enabled or spotting_enabled:
        raw,source = extract_tab_resource(config.SKILLS_PATH)
        patched=raw
        if capacity_enabled:
            patched,details = patch_capacity(raw,capacity)
            report['features']['capacity'] = dict(source=source,details=details)
        if spotting_enabled:
            tagged,details=patch_spotting(raw,spotting_seconds)
            merged=bytearray(patched)
            for index,(before,after) in enumerate(zip(raw,tagged)):
                if before!=after:
                    if merged[index]!=before:
                        raise FormatError('Tag与负重补丁字节冲突')
                    merged[index]=after
            patched=bytes(merged)
            GameADF(patched)  # 两项合并后仍须是合法的同布局ADF。
            report['features']['spotting']=dict(source=source,details=details)
        payloads[config.SKILLS_PATH] = patched
    if foxpro_enabled:
        from solo_helper.caller_patch import compile_remote_profile
        raw,source=extract_tab_resource(config.CALLER_INTEREST_PATH,research_only=True)
        patched,details=compile_remote_profile(raw,config.FOXPRO_RANGE_METERS)
        details={key:value for key,value in details.items() if key!='installed'}
        payloads[config.CALLER_INTEREST_PATH]=patched
        report['features']['foxpro_range']=dict(source=source,details=details,
             note='400米+100%基础吸引概率测试版；真实加载和动物响应仍须分别实测')
    if not payloads:
        raise ValueError('至少选择一项可实现功能')
    for path,data in payloads.items():
        target = output/path
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary = target.with_suffix(target.suffix+'.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)
        report['files'].append(dict(path=path,size=len(data),sha256=digest(data)))
    # 未选功能的旧文件不会被安装：安装器只使用本次清单列出的文件。
    (output/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
