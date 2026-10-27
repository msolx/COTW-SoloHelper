"""Helper窗口布局；支持中英文双语动态切换。"""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from services.i18n import get_lang, init_i18n, set_lang, t, toggle_lang
from solo_helper import config


def note(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName('note')
    return label


def retranslate_helper_ui(w):
    w.setWindowTitle(t('app_title_helper'))
    w.title_label.setText('COTW Solo Helper')
    w.subtitle_label.setText(t('helper_subtitle'))
    w.singleplayer.setText(t('singleplayer_confirm'))
    w.lang_btn.setText(t('lang_btn_text'))

    # 选项卡
    w.tabs.setTabText(0, t('tab_travel'))
    w.tabs.setTabText(1, t('tab_mods'))
    w.tabs.setTabText(2, t('tab_pressure'))
    w.tabs.setTabText(3, t('tab_logs'))

    # 传送标签
    w.travel_header_label.setText(t('travel_header'))
    w.travel_guide_label.setText(t('travel_guide'))
    dist_str = (t('dist_unlimited') if config.NATIVE_REDIRECT_MAX_DISTANCE is None
                else t('dist_limited', val=config.NATIVE_REDIRECT_MAX_DISTANCE))
    w.native_hint.setText(t('travel_warning', distance=dist_str, height=config.NATIVE_REDIRECT_MAX_HEIGHT))
    w.flat_ground.setText(t('flat_ground_confirm'))
    w.native_preview.setText(t('btn_inspect_waypoint'))
    w.native_enable.setText(t('btn_arm_waypoint'))
    w.native_enable.setToolTip(t('btn_arm_tooltip'))
    w.native_cancel.setText(t('btn_cancel_waiting'))

    # 参数标签
    w.settings_hint_label.setText(t('mods_hint'))
    w.box.setTitle(t('group_params'))
    w.crouch.setText(t('param_crouch'))
    w.multiplier.setSuffix(t('param_crouch_suffix'))
    w.carry.setText(t('param_carry'))
    w.capacity.setSuffix(t('param_carry_suffix'))
    w.spotting.setText(t('param_spotting'))
    w.spotting_seconds.setSuffix(t('param_spotting_suffix'))
    w.foxpro.setText(t('param_foxpro'))
    w.mods_notes_label.setText(t('mods_notes'))
    w.apply_settings.setText(t('btn_apply_settings'))
    w.launch_button.setText(t('btn_launch_game'))
    w.advanced.setText(t('btn_maintenance'))

    # 维护菜单
    w.menu_verify.setText(t('menu_verify_game'))
    w.menu_build.setText(t('menu_build_only'))
    w.menu_install.setText(t('menu_install'))
    w.menu_uninstall.setText(t('menu_uninstall'))

    # 压力标签
    w.pressure_header_label.setText(t('pressure_header'))
    w.pressure_hint_label.setText(t('pressure_hint'))
    w.pressure_preview.setText(t('btn_read_pressure'))
    w.pressure_clear.setText(t('btn_clear_pressure'))

    # 日志标签
    w.logs_hint_label.setText(t('logs_hint'))


def build_layout(w, values):
    init_i18n(config.SETTINGS_FILE)
    w.resize(800, 660)
    w.setMinimumSize(700, 590)
    w.setStyleSheet('''
        QWidget { font-size: 13px; color: #243449; }
        SoloWindow { background: #f2f5fa; }
        QLabel#title { font-size: 23px; font-weight: 600; }
        QLabel#note { color: #617188; }
        QLabel#activity { color: #175b97; padding: 8px; background: #e6effa; border-radius: 5px; }
        QTabWidget::pane { background: white; border: 1px solid #dce3ed; border-radius: 6px; }
        QTabBar::tab { padding: 10px 19px; background: #e8edf5; }
        QTabBar::tab:selected { background: white; color: #1265ab; }
        QGroupBox { border: 1px solid #dce3ed; border-radius: 6px; margin-top: 12px; padding: 16px 12px 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
        QPushButton, QToolButton { padding: 8px 12px; border: 1px solid #c7d3e2; border-radius: 5px; background: #f8fafc; }
        QPushButton:hover, QToolButton:hover { background: #eaf2fc; }
        QPushButton#primary { color: white; background: #176bb1; border-color: #176bb1; }
        QPushButton:disabled { color: #8b97a7; background: #edf0f4; border-color: #e0e5eb; }
        QPushButton#primary:disabled { color: #8b97a7; background: #edf0f4; border-color: #e0e5eb; }
        QPushButton#lang_btn { background: #e8f0fe; border: 1px solid #a8c7fa; color: #1967d2; font-weight: 500; }
        QPushButton#lang_btn:hover { background: #d2e3fc; }
        QDoubleSpinBox, QSpinBox { padding: 5px; min-width: 100px; }
        QPlainTextEdit { background: #f7f9fc; border: 1px solid #dce3ed; }
    ''')

    outer = QVBoxLayout(w)
    outer.setContentsMargins(20, 18, 20, 14)
    outer.setSpacing(12)

    # 顶栏：标题 + 语言切换按钮
    top_row = QHBoxLayout()
    header_v = QVBoxLayout()
    w.title_label = QLabel('COTW Solo Helper')
    w.title_label.setObjectName('title')
    header_v.addWidget(w.title_label)
    w.subtitle_label = note('单人助手 · 航点快速移动与本地参数设置')
    header_v.addWidget(w.subtitle_label)
    top_row.addLayout(header_v, 1)

    w.lang_btn = QPushButton()
    w.lang_btn.setObjectName('lang_btn')
    w.lang_btn.clicked.connect(lambda: on_toggle_lang(w))
    top_row.addWidget(w.lang_btn)
    outer.addLayout(top_row)

    w.singleplayer = QCheckBox()
    outer.addWidget(w.singleplayer)
    w.tabs = QTabWidget()
    outer.addWidget(w.tabs, 1)
    w.buttons = []
    w.setting_inputs = []

    def page(tab_title):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        w.tabs.addTab(widget, tab_title)
        return layout

    def button(btn_title, action, primary=False):
        result = QPushButton(btn_title)
        if primary:
            result.setObjectName('primary')
        result.clicked.connect(lambda checked=False: w.dispatch(action))
        w.buttons.append(result)
        return result

    # 1. 航点传送
    travel = page('航点传送')
    w.travel_header_label = QLabel()
    travel.addWidget(w.travel_header_label)
    w.travel_guide_label = note('')
    travel.addWidget(w.travel_guide_label)
    w.native_hint = note('')
    travel.addWidget(w.native_hint)
    w.flat_ground = QCheckBox()
    travel.addWidget(w.flat_ground)
    row = QHBoxLayout()
    w.native_preview = button('', 'native_preview')
    w.native_enable = button('', 'native_virtual', True)
    w.native_cancel = QPushButton()
    w.native_cancel.clicked.connect(w.cancel_native)
    for item in (w.native_preview, w.native_enable, w.native_cancel):
        row.addWidget(item)
    travel.addLayout(row)
    w.native_status = note(t('native_status_default'))
    travel.addWidget(w.native_status)
    travel.addStretch()

    # 2. 单人参数
    settings = page('单人参数')
    w.settings_hint_label = note('')
    settings.addWidget(w.settings_hint_label)
    w.box = QGroupBox('')
    form = QFormLayout(w.box)
    w.crouch = QCheckBox()
    w.crouch.setChecked(values['crouch'])
    w.multiplier = QDoubleSpinBox()
    w.multiplier.setRange(1, config.MAX_CROUCH_MULTIPLIER)
    w.multiplier.setSingleStep(.1)
    w.multiplier.setValue(values['multiplier'])
    form.addRow(w.crouch, w.multiplier)

    w.carry = QCheckBox()
    w.carry.setChecked(values['carry'])
    w.capacity = QSpinBox()
    w.capacity.setRange(1, 999)
    w.capacity.setValue(values['capacity'])
    form.addRow(w.carry, w.capacity)

    w.spotting = QCheckBox()
    w.spotting.setChecked(values['spotting'])
    w.spotting_seconds = QSpinBox()
    w.spotting_seconds.setRange(120, 999)
    w.spotting_seconds.setValue(values['spotting_seconds'])
    form.addRow(w.spotting, w.spotting_seconds)

    w.foxpro = QCheckBox()
    w.foxpro.setChecked(values['foxpro'])
    form.addRow(w.foxpro)
    settings.addWidget(w.box)

    w.mods_notes_label = note('')
    settings.addWidget(w.mods_notes_label)

    row = QHBoxLayout()
    w.apply_settings = button('', 'apply', True)
    w.launch_button = button('', 'launch')
    row.addWidget(w.apply_settings)
    row.addWidget(w.launch_button)

    w.advanced = QToolButton()
    w.advanced.setPopupMode(QToolButton.InstantPopup)
    menu = QMenu(w.advanced)
    w.menu_verify = QAction('', menu)
    w.menu_verify.triggered.connect(lambda checked=False: w.dispatch('verify'))
    menu.addAction(w.menu_verify)

    w.menu_build = QAction('', menu)
    w.menu_build.triggered.connect(lambda checked=False: w.dispatch('build'))
    menu.addAction(w.menu_build)

    w.menu_install = QAction('', menu)
    w.menu_install.triggered.connect(lambda checked=False: w.dispatch('install'))
    menu.addAction(w.menu_install)

    w.menu_uninstall = QAction('', menu)
    w.menu_uninstall.triggered.connect(lambda checked=False: w.dispatch('uninstall'))
    menu.addAction(w.menu_uninstall)

    w.advanced.setMenu(menu)
    row.addWidget(w.advanced)
    settings.addLayout(row)

    w.settings_status = note(t('settings_status_default'))
    settings.addWidget(w.settings_status)
    settings.addStretch()

    w.setting_inputs = [w.crouch, w.multiplier, w.carry, w.capacity, w.spotting, w.spotting_seconds, w.foxpro, w.advanced]
    for control in (w.crouch, w.carry, w.spotting, w.foxpro):
        control.toggled.connect(w.settings_changed)
    for control in (w.multiplier, w.capacity, w.spotting_seconds):
        control.valueChanged.connect(w.settings_changed)

    # 3. 压力区
    pressure = page('压力区')
    w.pressure_header_label = QLabel()
    pressure.addWidget(w.pressure_header_label)
    w.pressure_hint_label = note('')
    pressure.addWidget(w.pressure_hint_label)
    row = QHBoxLayout()
    w.pressure_preview = button('', 'pressure_preview')
    w.pressure_clear = button('', 'pressure_clear', True)
    row.addWidget(w.pressure_preview)
    row.addWidget(w.pressure_clear)
    pressure.addLayout(row)
    w.pressure_status = note(t('pressure_status_default'))
    pressure.addWidget(w.pressure_status)
    pressure.addStretch()

    # 4. 操作记录
    logs = page('操作记录')
    w.logs_hint_label = note('')
    logs.addWidget(w.logs_hint_label)
    w.log = QPlainTextEdit()
    w.log.setReadOnly(True)
    w.log.setMaximumBlockCount(3000)
    w.log.appendPlainText(t('logs_initial'))
    logs.addWidget(w.log, 1)

    w.activity = QLabel(t('activity_ready'))
    w.activity.setObjectName('activity')
    w.activity.setWordWrap(True)
    outer.addWidget(w.activity)

    w.retranslate_ui = lambda: retranslate_helper_ui(w)
    retranslate_helper_ui(w)


def on_toggle_lang(w):
    toggle_lang()
    w.retranslate_ui()
