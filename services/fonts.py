"""显式使用本机中文字体，避免Qt离屏平台及精简安装出现方框字。"""
from PySide6.QtGui import QFont, QFontDatabase
import config


def setup_fonts(app):
    if config.UI_FONT_PATH.is_file():
        font_id = QFontDatabase.addApplicationFont(str(config.UI_FONT_PATH))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0],10))
                return True
    return False
