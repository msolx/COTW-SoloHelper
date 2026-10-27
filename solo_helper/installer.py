"""只管理本工具专用目录；不覆盖原始文件、存档、Steam设置或其它Mod。"""
import json
from pathlib import PurePosixPath
import subprocess
import uuid
from solo_helper import config
from solo_helper.builder import verify_build,digest

OWNER = 'COTW Solo Helper 0.1'
STATE_FILE = 'solo_helper_manifest.json'
ALLOWED = {config.LOCAL_PLAYER_PATH,config.SKILLS_PATH,config.CALLER_INTEREST_PATH}


def write_atomic(target,data):
    """独占创建随机临时文件，防止重用已有临时链接；失败后只清理自己创建的文件。"""
    temporary = target.with_name(target.name+'.solo_'+uuid.uuid4().hex)
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(data)
        temporary.replace(target)
    finally:
        if created and temporary.exists():
            temporary.unlink()


def prune_empty(root,names):
    directories = {root}
    for name in names:
        directories.update(p for p in safe_target(root,name).parents if p.is_relative_to(root))
    for directory in sorted(directories,key=lambda p:len(p.parts),reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def game_running():
    # 仅枚举目标进程名，不打开游戏的写句柄，也不读取游戏内存。
    import ctypes
    from memory.process_reader import ProcessReader,PROCESSENTRY32W
    memory = ProcessReader()
    handle = memory._snapshot(2)
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        found = memory._enumeration_call(memory.api.Process32FirstW,handle,entry,'process_first')
        while found:
            if entry.szExeFile.casefold() == config.GAME_EXE.name.casefold():
                return True
            found = memory._enumeration_call(memory.api.Process32NextW,handle,entry,'process_next')
        return False
    finally:
        memory.api.CloseHandle(handle)


def require_closed():
    if game_running():
        raise RuntimeError('请先按游戏正常流程完全退出，再安装、卸载或加载Mod；不强制结束游戏')


def install_root():
    expected = config.GAME_DIR.resolve()/config.INSTALL_FOLDER
    root = expected.resolve()
    if root != expected:
        raise RuntimeError('专用Mod目录是重定向/链接，拒绝写入')
    return root


def safe_target(root,name):
    if name not in ALLOWED or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
        raise ValueError('安装清单含未授权路径')
    target = (root/name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('安装目标越出专用目录')
    return target


def validate_manifest(manifest):
    if not manifest.get('version',{}).get('sha256'):
        raise ValueError('Mod不是为当前受支持构建生成')
    files = manifest.get('files',[])
    paths = [f['path'] for f in files]
    if not paths or len(paths) != len(set(paths)) or any(p not in ALLOWED for p in paths):
        raise ValueError('Mod文件清单无效')
    return files


def read_installed(root):
    state = root/STATE_FILE
    if state.is_symlink():
        raise RuntimeError('安装状态文件是链接，拒绝操作')
    if not state.exists():
        if root.exists() and any(root.iterdir()):
            raise RuntimeError('专用目录已有未知内容，拒绝接管或覆盖')
        return None
    report = json.loads(state.read_text(encoding='utf-8'))
    if report.get('owner') != OWNER:
        raise RuntimeError('目录不属于本工具，拒绝操作')
    for item in validate_manifest(report):
        target = safe_target(root,item['path'])
        if not target.is_file() or digest(target.read_bytes()) != item['sha256']:
            raise RuntimeError('已安装文件被其它工具修改或缺失，拒绝覆盖/删除：'+item['path'])
    return report


def install(singleplayer_confirmed=False):
    if not singleplayer_confirmed:
        raise RuntimeError('本工具仅限单人，需先明确确认；不能自动识别游戏后续多人菜单')
    verify_build()
    require_closed()
    source = config.OUTPUT/'active'
    report = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    payloads = {}
    for item in validate_manifest(report):
        data = safe_target(source,item['path']).read_bytes()
        if digest(data) != item['sha256'] or len(data) != item['size']:
            raise RuntimeError('生成文件与清单不符，请重新生成')
        payloads[item['path']] = data
    root = install_root()
    old = read_installed(root)
    old_payloads = {item['path']:safe_target(root,item['path']).read_bytes() for item in old['files']} if old else {}
    root.mkdir(exist_ok=True)
    try:
        for name,data in payloads.items():
            target = safe_target(root,name)
            target.parent.mkdir(parents=True,exist_ok=True)
            write_atomic(target,data)
        for name in old_payloads.keys()-payloads.keys():
            safe_target(root,name).unlink()
        state = dict(report,owner=OWNER)
        write_atomic(root/STATE_FILE,json.dumps(state,ensure_ascii=False,indent=2).encode('utf-8'))
    except Exception:
        # 普通写入失败时恢复本工具上次文件；绝不改动其它Mod或原始ARC。
        for name in payloads:
            target = safe_target(root,name)
            if name not in old_payloads and target.exists():
                target.unlink()
        for name,data in old_payloads.items():
            target = safe_target(root,name)
            target.parent.mkdir(parents=True,exist_ok=True)
            write_atomic(target,data)
        if old is None:
            prune_empty(root,payloads)
        raise
    return state


def uninstall():
    require_closed()
    root = install_root()
    state = read_installed(root)
    if state is None:
        return '没有已安装的本工具Mod'
    for item in state['files']:
        target = safe_target(root,item['path'])
        target.unlink()
    (root/STATE_FILE).unlink()
    prune_empty(root,[item['path'] for item in state['files']])
    return '本工具的Mod已移除；原始游戏与存档未改动'


def launch(singleplayer_confirmed=False):
    if not singleplayer_confirmed:
        raise RuntimeError('请先确认只进入本机单人模式')
    verify_build()
    require_closed()
    state = read_installed(install_root())
    if not state:
        raise RuntimeError('请先生成并安装Mod')
    # 独立VFS目录仅作用于本次启动，不写Steam持久启动选项。
    args = [str(config.GAME_EXE),'--vfs-fs',config.INSTALL_FOLDER,
            '--vfs-archive','archives_win64','--vfs-archive','patch_win64',
            '--vfs-archive','dlc_win64','--vfs-fs','.']
    process = subprocess.Popen(args,cwd=config.GAME_DIR,stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return dict(pid=process.pid,message='已发起正常游戏启动；请只选择单人，效果仍需现场验收')
