"""COTW 工具集中英文双语国际化 (i18n) 模块。
支持自动检测系统语言、手动切换语言，并持久化到用户配置文件。
"""
import json
from pathlib import Path
from PySide6.QtCore import QLocale

LANG_ZH = 'zh'
LANG_EN = 'en'

_CURRENT_LANG = None
_SETTINGS_PATH = None


def init_i18n(settings_file: Path = None):
    global _CURRENT_LANG, _SETTINGS_PATH
    if settings_file:
        _SETTINGS_PATH = settings_file
        if settings_file.exists():
            try:
                data = json.loads(settings_file.read_text(encoding='utf-8'))
                if data.get('language') in (LANG_ZH, LANG_EN):
                    _CURRENT_LANG = data['language']
                    return _CURRENT_LANG
            except Exception:
                pass

    if _CURRENT_LANG is None:
        sys_lang = QLocale.system().name().lower()
        _CURRENT_LANG = LANG_ZH if sys_lang.startswith('zh') else LANG_EN
    return _CURRENT_LANG


def get_lang() -> str:
    global _CURRENT_LANG
    if _CURRENT_LANG is None:
        init_i18n()
    return _CURRENT_LANG


def set_lang(lang: str):
    global _CURRENT_LANG
    if lang in (LANG_ZH, LANG_EN):
        _CURRENT_LANG = lang
        if _SETTINGS_PATH:
            try:
                data = {}
                if _SETTINGS_PATH.exists():
                    data = json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
                data['language'] = lang
                _SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            except Exception:
                pass


def toggle_lang() -> str:
    new_lang = LANG_EN if get_lang() == LANG_ZH else LANG_ZH
    set_lang(new_lang)
    return new_lang


TRANSLATIONS = {
    # ==================== 雷达 (Animal Radar) ====================
    'app_title_radar': {
        LANG_ZH: 'COTW 动物雷达 & 游戏内悬浮窗 (v1.1.0)',
        LANG_EN: 'COTW Live Animal Radar & In-Game Overlay (v1.1.0)',
    },
    'radar_banner_notice': {
        LANG_ZH: '现场测试 · 只读数据 · 摄像机近似 · 支持全19保护区统一北向显示',
        LANG_EN: 'Live Session · Read-Only · Camera Approximate · Calibrated North-Up Supported',
    },
    'enable_north_up': {
        LANG_ZH: '启用已测北向',
        LANG_EN: 'Enable North-Up',
    },
    'north_up_enabled': {
        LANG_ZH: '已启用北向',
        LANG_EN: 'North-Up Active',
    },
    'north_up_tooltip': {
        LANG_ZH: '点击切换雷达方位显示（上北-Z／右东+X）',
        LANG_EN: 'Toggle cardinal axis display (North -Z / East +X)',
    },
    'life_filter_alive': {
        LANG_ZH: '存活（含受伤）',
        LANG_EN: 'Alive (incl. injured)',
    },
    'life_filter_all': {
        LANG_ZH: '全部状态',
        LANG_EN: 'All States',
    },
    'scale_meters': {
        LANG_ZH: '{val}米半径',
        LANG_EN: '{val}m Range',
    },
    'interval_seconds': {
        LANG_ZH: '每{val}秒刷新',
        LANG_EN: 'Every {val}s',
    },
    'pause_refresh': {
        LANG_ZH: '暂停刷新',
        LANG_EN: 'Pause',
    },
    'resume_refresh': {
        LANG_ZH: '继续刷新',
        LANG_EN: 'Resume',
    },
    'reconnect': {
        LANG_ZH: '重新连接',
        LANG_EN: 'Reconnect',
    },
    'select_group_details': {
        LANG_ZH: '选择区域查看个体详情；未验证字段显示未知',
        LANG_EN: 'Select a group to view animal details; unverified fields show unknown',
    },
    'click_to_track': {
        LANG_ZH: '点击区域选择探索目标',
        LANG_EN: 'Click a cluster to select tracking target',
    },
    'details_trial_label': {
        LANG_ZH: '属性试验：存档唯一匹配性别/评分；毛色、难度、奖牌为预测',
        LANG_EN: 'Attribute Joining: Match savefile gender/score; estimate fur & trophy',
    },
    'trophy_highlight_label': {
        LANG_ZH: '亮色块提示潜在白银/黄金及💎钻石（评分预测，需有效属性来源）',
        LANG_EN: 'Highlight Silver / Gold & 💎 Diamond trophy candidates',
    },
    'details_headers': {
        LANG_ZH: ['个体', '状态', '性别', '生命值', '毛色', '难度', '存档评分', '潜在评级'],
        LANG_EN: ['ID', 'Status', 'Gender', 'Health', 'Fur', 'Difficulty', 'Save Score', 'Est. Trophy'],
    },
    'overlay_show': {
        LANG_ZH: '显示雷达浮窗 (Ctrl+Alt+R)',
        LANG_EN: 'Show Overlay (Ctrl+Alt+R)',
    },
    'overlay_hide': {
        LANG_ZH: '隐藏雷达浮窗 (Ctrl+Alt+R)',
        LANG_EN: 'Hide Overlay (Ctrl+Alt+R)',
    },
    'overlay_unlock': {
        LANG_ZH: '解锁浮窗 (Ctrl+Alt+E)',
        LANG_EN: 'Unlock Overlay (Ctrl+Alt+E)',
    },
    'overlay_lock': {
        LANG_ZH: '锁定浮窗 (Ctrl+Alt+E)',
        LANG_EN: 'Lock Overlay (Ctrl+Alt+E)',
    },
    'cardinal_north': {
        LANG_ZH: '北',
        LANG_EN: 'N',
    },
    'cardinal_south': {
        LANG_ZH: '南',
        LANG_EN: 'S',
    },
    'cardinal_west': {
        LANG_ZH: '西',
        LANG_EN: 'W',
    },
    'cardinal_east': {
        LANG_ZH: '东',
        LANG_EN: 'E',
    },
    'radar_legend_north_up': {
        LANG_ZH: '现场方向初测 · 上 -Z（北）/ 右 +X（东）',
        LANG_EN: 'Live Cardinal Heading · Up -Z (North) / Right +X (East)',
    },
    'radar_legend_relative': {
        LANG_ZH: '相对坐标 · 仅供距离/实体参考',
        LANG_EN: 'Relative Coordinates · Distance & Entity Reference',
    },
    'overlay_title': {
        LANG_ZH: 'COTW · 探索雷达',
        LANG_EN: 'COTW · Mini Radar',
    },
    'overlay_caption_waiting': {
        LANG_ZH: '等待新采样',
        LANG_EN: 'Waiting for signal',
    },
    'overlay_info': {
        LANG_ZH: '50米区域 · 橙色受伤 / 灰叉尸体',
        LANG_EN: '50m clusters · Amber=Injured, Gray=Dead',
    },
    'overlay_hint': {
        LANG_ZH: '拖动标题移位 · 右下角缩放 · 点击下方锁定',
        LANG_EN: 'Drag title to move · Drag corner to resize · Click Lock below',
    },
    'overlay_lock_btn': {
        LANG_ZH: '锁定',
        LANG_EN: 'Lock',
    },
    'overlay_bg_label': {
        LANG_ZH: '背景',
        LANG_EN: 'Opacity',
    },
    'btn_toggle_overlay': {
        LANG_ZH: '显示 / 隐藏微型雷达',
        LANG_EN: 'Show / Hide Mini-Radar',
    },
    'btn_edit_overlay': {
        LANG_ZH: '调整微型雷达（移位/缩放）',
        LANG_EN: 'Adjust Mini-Radar (Move / Resize)',
    },
    'overlay_hint_text': {
        LANG_ZH: '点击上方按钮直接开关或调整微型雷达（建议游戏设为无边框窗口化）',
        LANG_EN: 'Use buttons above to toggle or adjust mini-radar (Borderless Windowed recommended)',
    },
    'reserve_prefix': {
        LANG_ZH: '当前保护区：',
        LANG_EN: 'Reserve: ',
    },
    'reserve_lock': {
        LANG_ZH: '锁定选择',
        LANG_EN: 'Lock Selection',
    },
    'lang_btn_text': {
        LANG_ZH: 'English',
        LANG_EN: '中文 (Chinese)',
    },

    # ==================== 单人助手 (Solo Helper) ====================
    'app_title_helper': {
        LANG_ZH: 'COTW Solo Helper · 单人助手',
        LANG_EN: 'COTW Solo Helper & Waypoint Fast-Travel',
    },
    'helper_subtitle': {
        LANG_ZH: '单人助手 · 航点快速移动与本地参数设置',
        LANG_EN: 'Solo Helper · Waypoint Fast-Travel & Local Mod Settings',
    },
    'singleplayer_confirm': {
        LANG_ZH: '我确认本次只使用单人模式',
        LANG_EN: 'I confirm this session is Singleplayer mode only',
    },
    'tab_travel': {
        LANG_ZH: '航点传送',
        LANG_EN: 'Waypoint Travel',
    },
    'tab_mods': {
        LANG_ZH: '单人参数',
        LANG_EN: 'Solo Mods',
    },
    'tab_pressure': {
        LANG_ZH: '压力区',
        LANG_EN: 'Hunting Pressure',
    },
    'tab_logs': {
        LANG_ZH: '操作记录',
        LANG_EN: 'Operation Logs',
    },
    'travel_header': {
        LANG_ZH: '把地图航点临时变成可快速移动的帐篷图标',
        LANG_EN: 'Temporarily convert your map waypoint into a fast-travel tent icon',
    },
    'travel_guide': {
        LANG_ZH: '1  在游戏地图设置航点\n2  确认目标地面，点击启用\n3  等待“已就绪”，回游戏点击该临时图标的快速移动一次',
        LANG_EN: '1  Set a User Waypoint on in-game map\n2  Confirm ground safety and click Arm\n3  Once "Ready", switch to game map and Fast Travel to the temporary tent icon',
    },
    'travel_warning': {
        LANG_ZH: '{distance} · 保留高差±{height}米及地形检查。\n水域、障碍和未加载地形尚不能自动保证安全。',
        LANG_EN: '{distance} · Preserves ±{height}m elevation & terrain checks.\nWater, obstacles, and unloaded terrain carry landing risks.',
    },
    'dist_unlimited': {
        LANG_ZH: '水平距离不限',
        LANG_EN: 'Unlimited horizontal distance',
    },
    'dist_limited': {
        LANG_ZH: '水平距离≤{val}米',
        LANG_EN: 'Horizontal distance ≤{val}m',
    },
    'flat_ground_confirm': {
        LANG_ZH: '本次已目视确认航点是干燥、无障碍的陆地',
        LANG_EN: 'I visually confirmed waypoint is dry, obstacle-free land',
    },
    'btn_inspect_waypoint': {
        LANG_ZH: '检查航点（只读）',
        LANG_EN: 'Inspect Waypoint (Read-Only)',
    },
    'btn_arm_waypoint': {
        LANG_ZH: '启用临时帐篷',
        LANG_EN: 'Arm Waypoint Tent',
    },
    'btn_arm_tooltip': {
        LANG_ZH: 'Ctrl+Shift+T，仅在Helper窗口获得焦点时有效；启用后回游戏点击临时图标。',
        LANG_EN: 'Ctrl+Shift+T, requires Helper window focus; once armed, click the icon in-game.',
    },
    'btn_cancel_waiting': {
        LANG_ZH: '取消等待',
        LANG_EN: 'Cancel Waiting',
    },
    'native_status_default': {
        LANG_ZH: '尚未启用。检查和启用均只针对当前航点。',
        LANG_EN: 'Not armed yet. Checks and arming apply to current waypoint only.',
    },
    'mods_hint': {
        LANG_ZH: '修改后点击“应用设置”。需完全退出游戏后安装，再从本工具启动游戏。',
        LANG_EN: 'Configure settings and click Apply. Game must be closed during installation.',
    },
    'group_params': {
        LANG_ZH: '参数',
        LANG_EN: 'Mod Parameters',
    },
    'param_crouch': {
        LANG_ZH: '普通蹲行倍率',
        LANG_EN: 'Crouch Speed Multiplier',
    },
    'param_crouch_suffix': {
        LANG_ZH: ' 倍',
        LANG_EN: 'x',
    },
    'param_carry': {
        LANG_ZH: '基础负重',
        LANG_EN: 'Backpack Capacity',
    },
    'param_carry_suffix': {
        LANG_ZH: ' kg',
        LANG_EN: ' kg',
    },
    'param_spotting': {
        LANG_ZH: '动物标记高亮',
        LANG_EN: 'Spotting Outline Duration',
    },
    'param_spotting_suffix': {
        LANG_ZH: ' 秒',
        LANG_EN: ' sec',
    },
    'param_foxpro': {
        LANG_ZH: 'FOXPRO X360：400米＋100%基础吸引概率',
        LANG_EN: 'FOXPRO X360: 400m range + 100% base attraction rate',
    },
    'mods_notes': {
        LANG_ZH: '蹲行加速的噪声修正仍待开发；高亮需要已学习Tag技能。\n电子哨和高亮新参数待实机验收，100%基础概率仍受其它AI条件影响。',
        LANG_EN: 'Crouch noise suppression in development; tagging requires in-game Tag skill.\nElectronic caller and spotting parameters are subject to in-game AI conditions.',
    },
    'btn_apply_settings': {
        LANG_ZH: '应用设置（需退出游戏）',
        LANG_EN: 'Apply Settings (Game Closed)',
    },
    'btn_launch_game': {
        LANG_ZH: '加载Mod启动游戏',
        LANG_EN: 'Launch Game with Mods',
    },
    'btn_maintenance': {
        LANG_ZH: '维护',
        LANG_EN: 'Maintenance',
    },
    'menu_locate_game': {
        LANG_ZH: '选择游戏安装根目录...',
        LANG_EN: 'Locate Game Directory...',
    },
    'menu_verify_game': {
        LANG_ZH: '检查游戏版本',
        LANG_EN: 'Verify Game Version',
    },
    'menu_build_only': {
        LANG_ZH: '仅生成文件',
        LANG_EN: 'Build Files Only',
    },
    'menu_install': {
        LANG_ZH: '安装已生成文件',
        LANG_EN: 'Install Generated Mod',
    },
    'menu_uninstall': {
        LANG_ZH: '卸载本工具Mod',
        LANG_EN: 'Uninstall Mod',
    },
    'settings_status_default': {
        LANG_ZH: '当前控件为待应用设置；实际安装参数以安装清单为准。',
        LANG_EN: 'Current controls show pending settings; actual installed parameters follow manifest.',
    },
    'pressure_header': {
        LANG_ZH: '清除当前保护区已经产生的紫色压力区',
        LANG_EN: 'Clear accumulated purple hunting pressure circles on active reserve',
    },
    'pressure_hint': {
        LANG_ZH: '立即作用于当前保护区；未来狩猎仍会新增压力。\n不会恢复已消失的需求区，尚未实现停止产生压力的开关。',
        LANG_EN: 'Applies to active reserve immediately; future kills will still create pressure.\nDoes not restore deleted need zones.',
    },
    'btn_read_pressure': {
        LANG_ZH: '读取当前压力（只读）',
        LANG_EN: 'Read Pressure (Read-Only)',
    },
    'btn_clear_pressure': {
        LANG_ZH: '清除已有压力',
        LANG_EN: 'Clear Existing Pressure',
    },
    'pressure_status_default': {
        LANG_ZH: '尚未读取；清除后请关闭再打开游戏地图核对。',
        LANG_EN: 'Not read yet; reopen game map after clearing to verify.',
    },
    'logs_hint': {
        LANG_ZH: '此处保留错误和诊断详情。自动检查通过不等于游戏效果已验收。',
        LANG_EN: 'Diagnostic and operation logs. Automated check pass does not guarantee in-game results.',
    },
    'logs_initial': {
        LANG_ZH: '单人助手已就绪。传送仅保留航点临时帐篷方案。',
        LANG_EN: 'Solo Helper is ready. Fast-travel uses waypoint temporary tent redirection.',
    },
    'activity_ready': {
        LANG_ZH: '就绪',
        LANG_EN: 'Ready',
    },
    'activity_busy': {
        LANG_ZH: '正在处理，请稍候…',
        LANG_EN: 'Processing, please wait...',
    },
}


def t(key: str, **kwargs) -> str:
    lang = get_lang()
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get(LANG_ZH) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
