"""公开Helper入口/设置/版本门禁；不使用原始游戏资源，不连接游戏。"""
import ast
import hashlib
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from solo_helper import config,builder
from solo_helper.archives import FormatError

ROOT=Path(__file__).resolve().parents[1]


class PublicHelperTests(unittest.TestCase):
    def test_gui_captures_tag_setting_without_original_game(self):
        from PySide6.QtWidgets import QApplication
        from solo_helper.main import SoloWindow,load_settings
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder,patch.object(config,'SETTINGS_FILE',Path(folder)/'settings.json'):
            window=SoloWindow()
            try:
                window.spotting.setChecked(True)
                window.spotting_seconds.setValue(180)
                job=window.build_action()
                window.spotting_seconds.setValue(240)
                with patch('solo_helper.main.build',return_value={}) as build:
                    job()
                self.assertEqual(build.call_args.kwargs['spotting_seconds'],180)
                self.assertEqual(load_settings()['spotting_seconds'],180)
            finally:
                window.close()

    def test_unknown_build_is_reported_truthfully_and_strict_mode_rejects(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); exe=path/'game.exe'; exe.write_bytes(b'not the supported game')
            manifest=path/'appmanifest.acf'; manifest.write_text('"buildid" "0"',encoding='utf-8')
            with patch.object(config,'GAME_EXE',exe),patch.object(config,'MANIFEST',manifest):
                reported=builder.verify_build()
                self.assertEqual(reported['sha256'],hashlib.sha256(exe.read_bytes()).hexdigest())
                self.assertEqual(reported['steam_build'],'0')
                with self.assertRaises(FormatError): builder.verify_build(strict=True)

    def test_spec_uses_helper_entry_and_no_upx(self):
        source=(ROOT/'COTW_SoloHelper.spec').read_text(encoding='utf-8')
        self.assertIn("['solo_helper_launcher.py']",source)
        self.assertNotIn('upx=True',source)
        tree=ast.parse((ROOT/'solo_helper_launcher.py').read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(n,ast.ImportFrom) and n.module=='solo_helper.main' for n in ast.walk(tree)))
