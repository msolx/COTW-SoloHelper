"""所有运行参数集中于此；默认模拟模式，不连接游戏。"""
import sys
from pathlib import Path
from services.path_finder import detect_steam_cotw_dir, detect_cotw_save_dir, detect_crash_dir

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).resolve().parent
    SOURCE = 'field_test'
else:
    ROOT = Path(__file__).resolve().parent
    SOURCE = 'mock'  # mock / live；live 仍要求本地已验证的哈希配置

def _find_resource(relative: str) -> Path:
    p = ROOT / relative
    if p.exists():
        return p
    internal_p = ROOT / '_internal' / relative
    if internal_p.exists():
        return internal_p
    return p
PROCESS_NAME = 'theHunterCotW_F.exe'
OFFSETS_DIR = _find_resource('offsets')
REFRESH_SECONDS = 1
REFRESH_CHOICES = (1, 2, 5)
RADAR_RANGES = (100, 200, 400)
RADAR_RANGE = 400
GRID_METERS = 50
MAX_ANIMALS = 512
MAX_DISTANCE = 1000
MAX_COORDINATE = 1_000_000
MAX_READ_BYTES = 8192
MOCK_DISCONNECT_TICK = 18
MOCK_RECONNECT_TICK = 22

# 研究探针独立于正式数据源：仅针对指定构建执行少量只读采样，
# 采样成功不自动将偏移标记为已验证。
PROBE_EXPECTED_SHA256 = '89dbab025114090c91a63ae7f0533ee84eee3c48f4b8543224b359c31b794c22'
PROBE_OFFSETS_FILE = OFFSETS_DIR / 'research_2026_09_16.json'
PROBE_REPORT = ROOT / 'animal_details_probe.json'  # 动物详情与尸体对照报告，保留位置证据
PROBE_SAMPLES = 3
PROBE_INTERVAL_SECONDS = 1
PROBE_MAX_ENTITIES = 64  # 探针采样上限，避免小样本遗漏可见目标
PROBE_HISTORY_DIR = ROOT / 'probe_history'
PROBE_PRINT_DETAILS = False  # 完整样本保存在本地JSON，控制台默认仅输出摘要

# 安装参数。TUNA为公开PyPI镜像，只对安装子进程生效，不修改pip全局配置。
# 若本地可直连官方源，可改为 https://pypi.org/simple
INSTALL_INDEX_URL = 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple'
INSTALL_RETRIES = 2
INSTALL_TIMEOUT_SECONDS = 60

# 游戏路径自动探测，优先探测注册表和运行实例，支持多盘库目录
GAME_EXE_PATH = detect_steam_cotw_dir() / 'theHunterCotW_F.exe'
STEAM_MANIFEST_PATH = GAME_EXE_PATH.parent.parent / 'appmanifest_518790.acf'
BUILD_REPORT = ROOT / 'build_inspection.json'

# 移动校准只读摄像机float3。每个步骤需现场配合，不自动批准方向校准。
CALIBRATION_RESERVE = 'medved'  # 手动指定的校准保护区，不代表从内存自动识别
CALIBRATION_LABEL = 'east_endpoint'
CALIBRATION_REFERENCE_LABEL = 'north_endpoint'  # 东行起点是刚才的北行终点，不能用累计位移
CALIBRATION_REPORT = ROOT / 'movement_calibration_medved.json'  # 保留莱顿原始证据
CALIBRATION_SAMPLES = 3
CALIBRATION_INTERVAL_SECONDS = 1
CALIBRATION_MAX_SPREAD_METERS = 2

# 朝向探针仅验证公开摄像机世界矩阵线索，不进行全进程搜索或屏幕投影。
HEADING_PROBE_LABEL = 'east'
HEADING_PROBE_RESERVE = 'medved'
HEADING_PROBE_REPORT = ROOT / 'heading_calibration_medved.json'
HEADING_PROBE_SAMPLES = 3
HEADING_PROBE_INTERVAL_SECONDS = 1
HEADING_MATRIX_TOLERANCE = .03  # 齐次分量、单位基与正交误差上限
HEADING_DETERMINANT_TOLERANCE = .05
HEADING_MIN_HORIZONTAL = .1  # 接近垂直时水平投影不稳定，隐藏箭头

# 单独的现场测试入口：正式live门禁不变，仅开放已现场核对的核心字段。
FIELD_TEST_SOURCE = 'field_test'
FIELD_TEST_MAX_ENTITIES = MAX_ANIMALS  # 连续雷达使用512只硬上限；64只仅保留给一次性研究探针
FIELD_TEST_STATUS_FILE = ROOT / 'field_test_status.json'
FIELD_TEST_RESERVE_LABEL = '未知（未从内存识别；在窗口手动确认）'
FIELD_TEST_SESSION_SECONDS = 0  # 0=持续运行到手动关闭；正整数可选定时停止
RECONNECT_SECONDS = 3
MAX_CONSECUTIVE_SCAN_FAILURES = 3
SCENE_JUMP_METERS = 750  # 只触发清理和保护区重新确认，不推断传送或地图ID
FIELD_TEST_NORTH_UP = True  # 东行+X、北行-Z，白尾鹿南向+Z交叉核对；非朝向跟随
ALL_RESERVE_IDS = ('hirschfelden','layton','medved','vurhonga','parque',
    'yukon','cuatro','silver','te_awaroa','rancho','mississippi',
    'revontuli','new_england','emerald','sundarpatan','salzwiesen',
    'askiy','scotland','intisuyu')
NORTH_UP_RESERVES = ALL_RESERVE_IDS  # 引擎全地图统一坐标系统（+X东/-Z北）；所有19个保护区均支持启用已测北向（显示东南西北）
INITIAL_RESERVE = None  # None=未确认；其它值参见 data/reserves.json 的 id
RESERVE_CATALOG_FILE = _find_resource('data/reserves.json')
EXPECTED_RESERVE_COUNT = 19  # 游戏新增保护区时需核对资料、名录及此值
CATALOG_REPORT_FILE = ROOT / 'RESERVE_CATALOG.md'
UI_FONT_PATH = Path(r'C:\Windows\Fonts\msyh.ttc')  # 只读系统已有微软雅黑，不下载/分发字体

# 独立桌面浮窗；不嵌入、不修改游戏窗口。位置尺寸为 Qt 逻辑像素。
OVERLAY_ENABLED = True
OVERLAY_SETTINGS_FILE = ROOT / 'overlay_settings.json'
OVERLAY_STATUS_FILE = ROOT / 'overlay_status.json'  # 仅界面/窗口状态，不含动物位置
OVERLAY_SIZE = 320
OVERLAY_HEIGHT = 420
OVERLAY_MIN_SIZE = 260
OVERLAY_MAX_SIZE = 600
OVERLAY_OFFSET = (20, 20)
OVERLAY_BACKGROUND_ALPHA = 180  # 仅背景透明度，文字和标记保持清晰
OVERLAY_POLL_MS = 250
OVERLAY_HOTKEY_MODIFIERS = 0x4003  # Ctrl + Alt + 禁止按住重复触发
OVERLAY_TOGGLE_KEY = 0x52  # R：显示/隐藏
OVERLAY_EDIT_KEY = 0x45  # E：解锁/锁定

# 个体属性研究：自动读取当前用户实际的 COTW 存档目录
POPULATION_SAVE_DIR = detect_cotw_save_dir()
POPULATION_RESEARCH_FILE = POPULATION_SAVE_DIR / 'animal_population_1'
POPULATION_MAX_BYTES = 16 * 1024 * 1024
POPULATION_MAX_NODES = 200_000
DETAILS_RESEARCH_REPORT = ROOT / 'details_structure_probe.json'
DETAILS_ENTITY_BYTES = 0x400  # 仅当前已验证实体附近的小块，不做全进程搜索
DETAILS_CANDIDATE_REPORT = ROOT / 'details_candidate_validation.json'
DETAILS_CANDIDATE_START = 0x180  # 前轮组件匹配：体重/评分+0x19C，外观种子+0x1B0
DETAILS_CANDIDATE_BYTES = 0x40
ATTRIBUTE_ESTIMATES_FILE = _find_resource('data/attribute_estimates.json')
TROPHY_THRESHOLDS_FILE = _find_resource('data/trophy_thresholds.json')
TROPHY_HIGHLIGHT_ENABLED = True  # 仅有明确评分来源及阈值时高亮“潜在白银+”
DETAILS_JOIN_ENABLED = False  # 完成现场性别/毛色对照前不接入连续雷达
DETAILS_TRIAL_RESERVE = 'layton'  # 研究报告明确使用莱顿存档，不作为自动保护区识别
DETAILS_TRIAL_REPORT = ROOT / 'details_trial_preview.json'
POPULATION_RELOAD_SECONDS = 10
# 存档编号与保护区菜单相互独立；不是实时地图识别。来源见 APS 研究文档。
POPULATION_RESERVE_IDS = {'hirschfelden':0,'layton':1,'medved':2,'vurhonga':3,'parque':4,
    'yukon':6,'cuatro':8,'silver':9,'te_awaroa':10,'rancho':11,'mississippi':12,
    'revontuli':13,'new_england':14,'emerald':16,'sundarpatan':17,'salzwiesen':18,
    'askiy':19,'scotland':20,'intisuyu':21}

# 崩溃离线诊断目录
CRASH_ANALYSIS_DIR = detect_crash_dir()
CRASH_ANALYSIS_REPORT = ROOT / 'crash_analysis_20261023.json'
