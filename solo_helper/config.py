"""本工具的全部路径和默认运行参数；不使用 argparse。"""
import sys
from pathlib import Path
from services.path_finder import detect_steam_cotw_dir

if getattr(sys, 'frozen', False):
    PROJECT = Path(sys.executable).resolve().parent
    ROOT = PROJECT / 'solo_helper'
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
    except OSError:
        ROOT = Path.home() / 'AppData' / 'Local' / 'COTW_Toolkit' / 'solo_helper'
        ROOT.mkdir(parents=True, exist_ok=True)
else:
    ROOT = Path(__file__).resolve().parent
    PROJECT = ROOT.parent
GAME_DIR = detect_steam_cotw_dir()
GAME_EXE = GAME_DIR / 'theHunterCotW_F.exe'
EXPECTED_SHA256 = '89dbab025114090c91a63ae7f0533ee84eee3c48f4b8543224b359c31b794c22'
SUPPORTED_HASHES = {
    EXPECTED_SHA256,
    '33c8306e52c5541a5b87e4af576f4149f3da0c23b36775372ec6c41adbab73ca',
}
COMPATIBILITY_MODE = getattr(sys, 'frozen', False)


def is_compatible_build(sha256: str) -> bool:
    if getattr(sys, 'frozen', False) or COMPATIBILITY_MODE:
        return True
    return str(sha256).lower() in {h.lower() for h in SUPPORTED_HASHES}
EXPECTED_BUILD = '25131233'
EXPECTED_BUILDS = {'25131233', '26051119'}
MANIFEST = GAME_DIR.parent.parent / 'appmanifest_518790.acf'
CROUCH_MULTIPLIER = 1.5
MAX_CROUCH_MULTIPLIER = 10.0  # 允许临时夸大倍率验证；默认仍为1.5
BASE_CAPACITY_KG = 512.0
WORK = ROOT / 'work'
OUTPUT = ROOT / 'output'
SETTINGS_FILE = ROOT / 'settings.json'
INSTALL_FOLDER = 'navigator_solo'
ORIGINAL_HASHES = {
    'elmer_movement.mtunec':'de4c271c219363c7f0ef572b61c7a2ba38c7af10c8b2954ad2e6fcc177699f00',
    'player_skills.bin':'272cd266475dbd6f07b293381e3be3a5eedbd493d436314952ff82786a6adf50',
}
MAX_ASSET_BYTES = 256 * 1024 * 1024
MOVEMENT_PATH = 'editor/entities/hp_characters/main_characters/elmer/elmer_movement.mtunec'
SKILLS_PATH = 'settings/hp_settings/player_skills.bin'
LOCAL_PLAYER_PATH = 'editor/entities/hp_characters/main_characters/local_player_character.ee'
ASSET_PATHS = (SKILLS_PATH,LOCAL_PLAYER_PATH)
CALLER_INTEREST_PATH = 'settings/hp_settings/animal_interest.bin'
FOXPRO_RANGE_ENABLED = False  # 静态范围Mod须选择、生成、安装并重启；成功率不冒充已实现。
FOXPRO_RANGE_METERS = 400.0
SPOTTING_ENABLED = True  # 延长已学习Tag技能的高亮；不自动解锁技能。
SPOTTING_SECONDS = 120  # 至少两分钟；切换目标/卸载等原版清除规则仍存在。
CALLER_TEST_SPECIES = 'black bear'
CALLER_TEST_CALL = '哀痛的鹿鸣'
CALLER_TEST_SECONDS = 45.0
CALLER_TEST_INTERVAL = 1.0
CALLER_TEST_ANCHOR_ERROR = 5.0  # 用户站在已放置哨旁，使用人物位置近似；不是直接读到的道具坐标。
WAYPOINT_REPORTED_MAP_XZ = (9919.0,10279.0)  # 用户第二次放置，报告约5米；非内存地址
WAYPOINT_RESEARCH_REPORT = ROOT / 'waypoint_static_research.json'
WAYPOINT_RUNTIME_REPORT = ROOT / 'waypoint_runtime_probe.json'
WAYPOINT_MANAGER_CANDIDATE = 0x27e2660  # 仅研究：Show/HideUserWaypoint两处RIP引用一致
WAYPOINT_MAX_MARKERS = 4096
PLAYER_REGISTRY_CANDIDATE = 0x27f1478  # GetLocalPlayerCharacter回调中的RIP引用，仅研究
PHYSICS_MAX_BODY_CAPACITY = 1 << 20  # 物理索引异常时停止，只读取人物对应一条记录
USER_WAYPOINT_ID = 0x123456789  # BE5F60初始化用户标记；共享/任务标记不使用此ID
POSITION_TRIAL_REPORT = ROOT / 'position_trial_report.json'  # 单次微移实验，不接入雷达
POSITION_TRIAL_LOCK = ROOT / 'position_trial.lock'  # Helper与独立现场测试共用互斥，不允许并行位置实验
FAST_TRAVEL_CAPTURE_SECONDS = 90.0  # 留出切回游戏与菜单操作时间；只读窗口到时自动结束
FAST_TRAVEL_CAPTURE_INTERVAL = 0.05
FAST_TRAVEL_CAPTURE_NATIVE_REQUEST = True  # 后续对照增加已定位的原生请求阶段，不改请求
TRAVEL_RESEARCH_MAX_MARKERS = 512  # 只检查既有地图标记容器，不搜索任意内存
TRAVEL_RESEARCH_MARKER_RADIUS = 60.0  # 仅记录原生快速移动落点附近的候选
TRAVEL_RESEARCH_REFERENCE_XZ = (9964.0, 10387.0)  # 用户给出的既有帐篷，仅作只读对照
TRAVEL_RESEARCH_REFERENCE_RADIUS = 15.0
NATIVE_TRAVEL_MAX_POINTS = 512  # A84710中的已注册传送点弱引用列表，仅只读核对
NATIVE_REDIRECT_MIN_REMAINING = 0.5  # 阶段2至少还剩半秒才尝试一次；不能追写加载中请求
NATIVE_REDIRECT_ARM_SECONDS = 180.0
NATIVE_REDIRECT_OBSERVE_SECONDS = 45.0
NATIVE_REDIRECT_IDLE_OBSERVE_SECONDS = 20.0  # 空闲后继续观察，不能仅2秒稳定就把后续目标重置漏掉
NATIVE_REDIRECT_POLL_SECONDS = 0.01
NATIVE_REDIRECT_MAX_DISTANCE = None  # 用户要求取消原生航点水平距离上限；None不限，不改变旧直接移动阶段。
NATIVE_REDIRECT_MAX_HEIGHT = 1000.0  # 放宽原生快速移动高差门禁（允许跨越山峰、高地、河谷）
NATIVE_BASE_MESH_ENABLED = True  # 粗表失配时独立只读核对基础碰撞网格；不扩大距离/高差。
NATIVE_BASE_MESH_MAX_ERROR = 0.25  # 基础网格默认严格贴地阈值（单体物理微移/单元测试）
NATIVE_PLAYER_MESH_MAX_ERROR = 2.0  # 人物当前站立点放宽容差（允许斜坡、蹲姿、树桩、微地形起伏）
NATIVE_TARGET_MESH_MAX_ERROR = 3.0  # 目标落点放宽至3米自然网格容限，自动吸附贴地防误拒
NATIVE_WAYPOINT_FALLBACK_ENABLED = True  # 当粗表偏差>3米且网格复核受阻时，安全回退至航点引擎射线地面高度
VIRTUAL_TENT_MAX_FALLBACK_DISTANCE = None  # 不以真实后备点距离间接限制远航点；身份/请求阶段检查仍保留。
NATIVE_REDIRECT_CANCEL_FILE = ROOT/'native_redirect.cancel'
NATIVE_GROUND_WITNESS_REPORT = ROOT/'fast_travel_observation_1792843697.json'
NATIVE_GROUND_WITNESS_ENABLED = False  # 锚点已出现变化；地面证据旁路默认关闭，等待重新验证
NATIVE_GROUND_WITNESS_SHA256 = '09338f4e80c9d83feee242b13c78bc707d83796ca630df4293962bfbe08fa518'
NATIVE_GROUND_WITNESS_ANCHOR_ID = 0x74d77526e6e00023  # 本轮只读核对的真实帐篷；不是通用游戏ID
NATIVE_GROUND_WITNESS_ANCHOR_POSITION = (9964.3642578125,1049.14501953125,10387.0068359375)
NATIVE_GROUND_WITNESS_MAX_AGE = 7200.0  # 本次研究记录最多保留两小时资格，不冒充实时地面查询
NATIVE_GROUND_WITNESS_RADIUS = 1.0
NATIVE_GROUND_WITNESS_MAX_DISTANCE = 200.0
NATIVE_GROUND_WITNESS_MAX_HEIGHT = 25.0
# 分阶段扩大验证：新高度适配阶段不等于已完成任意地点的自动安全传送。
SURFACE_TRIAL_MAX_DISTANCE = 25.0
SURFACE_RESEARCH_DISTANCE_STAGES = (25.0, 50.0, 100.0, 200.0)  # 较远阶段仅供明确选择的独立实验；Helper默认不扩距
SURFACE_TRIAL_MAX_GROUND_CHANGE = 2.0
SURFACE_RESEARCH_GROUND_CHANGE = {25.0: 2.0, 50.0: 2.0, 100.0: 2.0, 200.0: 5.0}  # 200米高度扩展仍属受控实验
SURFACE_RESEARCH_HEIGHT_STAGES = (2.0, 5.0, 20.0)  # 独立高差阶段；未显式选择时仍使用距离阶段默认值
SURFACE_TRIAL_CLEARANCE = 0.15  # 目标候选地面上方15厘米，由正常物理落地
SURFACE_TRIAL_MAX_SLOPE_RATIO = 0.15
SURFACE_TRIAL_COARSE_TOLERANCE = 3.0  # 粗表64米分辨率，仅用于交叉检查
SURFACE_TRIAL_FALLBACK_OFFSET = 12.0  # 97D940在碰撞高度查询失败时的粗表回退加值
SURFACE_TRIAL_FALLBACK_TOLERANCE = 0.5
DEFAULT_SURFACE_TRIAL = False  # 25米高度适配仍由用户明确选择；默认保留原10米模式
WAYPOINT_PREVIEW_REPORT = ROOT / 'waypoint_preview_report.json'
RESEARCH_ASSET_PATHS = (
    'settings/hp_settings/global_simulation.bin',
    'settings/hp_settings/animal_interest.bin',
    'settings/hp_settings/equipment_data.bin',
    'settings/hp_settings/equipment_stats_ui.bin',
    'settings/hunting_pressure.huntingpresstunec',
)  # 仅供离线提取研究，不加入Mod安装清单
