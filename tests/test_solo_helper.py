"""独立单人工具测试：临时目录与合成容器；本机原始参数仅用于只读构建核对。"""
import hashlib
import json
import struct
import tempfile
import unittest
import sys
import time
from pathlib import Path
from unittest.mock import patch,Mock
from solo_helper import config
from solo_helper.archives import Sarc,FormatError,pack_aaf,unpack_aaf,path_hash
from solo_helper.builder import patch_movement,patch_capacity,verify_build,digest,get_cell
from solo_helper.adf import GameADF
from solo_helper import installer


def sarc_fixture(compressed=False,variant=2):
    if variant == 2:
        data = struct.pack('<I4s2I',4,b'SARC',2,16)
        data += struct.pack('<I4s2I',4,b'a\0\0\0',32,4)+b'DATA'
    else:
        name = b'file.bin'
        data = struct.pack('<I4s2I',4,b'SARC',3,48)+struct.pack('<I',len(name)+1)+name+b'\0'
        data += struct.pack('<5I',0,64,4,path_hash(name),path_hash(b'.bin'))
        data = data.ljust(64,b'\0')+b'DATA'
    return pack_aaf(data) if compressed else data


class ArchiveTests(unittest.TestCase):
    def test_aaf_roundtrip_and_invalid_sections(self):
        data = bytes(range(256))*200
        encoded = pack_aaf(data)
        self.assertEqual(unpack_aaf(encoded),(data,True))
        for offset in (4,36,48,52,56,60):
            bad = bytearray(encoded)
            bad[offset:offset+4] = b'BAD!'
            with self.subTest(offset=offset),self.assertRaises((FormatError,ValueError)):
                unpack_aaf(bad)
        with self.assertRaises(FormatError): unpack_aaf(encoded[:-5])

    def test_sarc_variants_and_same_size_replacement(self):
        for variant in (2,3):
            for compressed in (False,True):
                with self.subTest(variant=variant,compressed=compressed):
                    before = Sarc(sarc_fixture(compressed,variant))
                    name = 'a' if variant == 2 else 'file.bin'
                    self.assertEqual(before.extract(name),b'DATA')
                    encoded = before.replace_same_size(name,b'TEST')
                    after = Sarc(encoded)
                    self.assertEqual(after.extract(name),b'TEST')
                    self.assertEqual(after.entries,before.entries)
                    self.assertEqual(after.compressed,compressed)
                    with self.assertRaises(FormatError): before.replace_same_size(name,b'BIG TOO BIG')

    def test_sarc_rejects_invalid_entry_boundaries_and_hash(self):
        raw = bytearray(sarc_fixture())
        struct.pack_into('<I',raw,24,999999)
        with self.assertRaises(FormatError): Sarc(raw)
        raw = bytearray(sarc_fixture(variant=3))
        struct.pack_into('<I',raw,41,0)
        with self.assertRaises(FormatError): Sarc(raw)
        self.assertEqual(path_hash(b''),0xdeadbeef)


@unittest.skipUnless((config.WORK/'elmer_movement.mtunec').is_file() and
                     (config.WORK/'player_skills.bin').is_file(),'先从匹配构建提取原始参数，才能运行本机资源核对')
class LocalAssetTests(unittest.TestCase):
    def test_crouch_only_changes_two_fields_and_preserves_shift_product(self):
        raw = (config.WORK/'elmer_movement.mtunec').read_bytes()
        patched,report = patch_movement(raw,1.5)
        self.assertEqual(len(raw),len(patched))
        self.assertEqual(report['normal_after'],.75)
        self.assertAlmostEqual(report['shift_product_after'],report['shift_product_before'],places=6)
        original = GameADF(raw).roots[0].value['FpsSettings'].value
        after = GameADF(patched).roots[0].value['FpsSettings'].value
        for name in original:
            if name not in ('KeyboardStanceCrouchSpeedModifier','KeyboardStanceCrouchSprintModifier'):
                self.assertEqual(original[name],after[name])

    def test_capacity_changes_only_target_strings_and_not_shared_cells(self):
        raw = (config.WORK/'player_skills.bin').read_bytes()
        patched,report = patch_capacity(raw,512)
        self.assertEqual(len(raw),len(patched))
        a,b = GameADF(raw),GameADF(patched)
        self.assertEqual(get_cell(b,'skill_component_descriptions',2,44)[1].value,'(512)')
        self.assertEqual(get_cell(b,'skills_strategic',7,11)[1].value,'set_player_carry_capacity(512)')
        before_strings = [s.value for s in a.roots[0].value['StringData'].value]
        after_strings = [s.value for s in b.roots[0].value['StringData'].value]
        self.assertEqual(sum(x != y for x,y in zip(before_strings,after_strings)),2)
        for name in ('Sheet','Cell','ValueData','BoolData','DateData','ColorData','Attribute'):
            self.assertEqual(a.roots[0].value[name],b.roots[0].value[name])

    def test_wrong_original_or_invalid_settings_rejected(self):
        movement = (config.WORK/'elmer_movement.mtunec').read_bytes()
        capacity = (config.WORK/'player_skills.bin').read_bytes()
        for value in (0,config.MAX_CROUCH_MULTIPLIER+1,float('nan'),True):
            with self.assertRaises(ValueError): patch_movement(movement,value)
        for value in (0,1000,1.5,True):
            with self.assertRaises(ValueError): patch_capacity(capacity,value)
        with self.assertRaises(FormatError): patch_movement(movement[:-1]+b'?',1.5)

    def test_ten_times_trial_preserves_shift_and_default(self):
        raw = (config.WORK/'elmer_movement.mtunec').read_bytes()
        patched,report = patch_movement(raw,10)
        self.assertEqual(report['normal_after'],5.0)
        self.assertAlmostEqual(report['shift_product_after'],1.0,places=6)
        self.assertEqual(config.CROUCH_MULTIPLIER,1.5)
        self.assertEqual(len(raw),len(patched))


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch.object(config,'SETTINGS_FILE',self.root/'settings.json'))
        self.game = self.root/'game'
        self.game.mkdir()
        self.vanilla = self.game/'original.arc'
        self.vanilla.write_bytes(b'original game asset')
        self.output = self.root/'output'
        source = self.output/'active'
        target = source/config.SKILLS_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(b'only our generated mod')
        report = dict(version={'sha256':config.EXPECTED_SHA256},
                      files=[dict(path=config.SKILLS_PATH,size=22,sha256=digest(target.read_bytes()))])
        report['files'][0]['size'] = target.stat().st_size
        (source/'manifest.json').write_text(json.dumps(report),encoding='utf-8')
        self.enterContext(patch.object(config,'GAME_DIR',self.game))
        self.enterContext(patch.object(config,'OUTPUT',self.output))
        self.enterContext(patch('solo_helper.installer.verify_build',return_value=report['version']))
        self.running = self.enterContext(patch('solo_helper.installer.game_running',return_value=False))

    def test_install_uninstall_preserves_vanilla_and_unknown_files(self):
        with self.assertRaises(RuntimeError): installer.install(False)
        report = installer.install(True)
        root = installer.install_root()
        self.assertEqual(report['owner'],installer.OWNER)
        self.assertTrue((root/config.SKILLS_PATH).is_file())
        unknown = root/'user-note.txt'
        unknown.write_text('keep me')
        installer.uninstall()
        self.assertFalse((root/config.SKILLS_PATH).exists())
        self.assertEqual(unknown.read_text(),'keep me')
        self.assertEqual(self.vanilla.read_bytes(),b'original game asset')

    def test_running_game_blocks_install_uninstall_and_launch(self):
        self.running.return_value = True
        for operation in (lambda:installer.install(True),installer.uninstall,lambda:installer.launch(True)):
            with self.assertRaises(RuntimeError): operation()
        self.assertFalse(installer.install_root().exists())

    def test_tampered_owned_files_never_overwritten_or_deleted(self):
        installer.install(True)
        path = installer.install_root()/config.SKILLS_PATH
        path.write_bytes(b'changed by user')
        with self.assertRaises(RuntimeError): installer.install(True)
        with self.assertRaises(RuntimeError): installer.uninstall()
        self.assertEqual(path.read_bytes(),b'changed by user')

    def test_unowned_directory_and_manifest_traversal_rejected(self):
        root = installer.install_root()
        root.mkdir()
        (root/'other-mod').write_bytes(b'keep')
        with self.assertRaises(RuntimeError): installer.install(True)
        for name in ('../original.arc','/absolute',config.SKILLS_PATH+'/../original.arc'):
            with self.assertRaises(ValueError): installer.safe_target(root,name)

    def test_launcher_uses_temporary_isolated_vfs_args(self):
        installer.install(True)
        with patch('solo_helper.installer.subprocess.Popen',return_value=Mock(pid=123)) as launch:
            result = installer.launch(True)
        self.assertEqual(result['pid'],123)
        args = launch.call_args.args[0]
        self.assertEqual(args[1:3],['--vfs-fs',config.INSTALL_FOLDER])
        self.assertNotIn('dropzone',args)
        with self.assertRaises(RuntimeError): installer.launch(False)

    def test_wrong_build_fails_before_install(self):
        with patch('solo_helper.installer.verify_build',side_effect=FormatError('版本不同')):
            with self.assertRaises(FormatError): installer.install(True)
        self.assertFalse(installer.install_root().exists())

    def test_failed_install_rolls_back_without_partial_owned_files(self):
        original = installer.write_atomic
        def fail_state(target,data):
            if target.name == installer.STATE_FILE:
                raise OSError('模拟写入状态失败')
            return original(target,data)
        with patch('solo_helper.installer.write_atomic',side_effect=fail_state):
            with self.assertRaises(OSError): installer.install(True)
        self.assertFalse(installer.install_root().exists())
        self.assertEqual(self.vanilla.read_bytes(),b'original game asset')

    def test_gui_job_captures_values_before_background_execution(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from solo_helper.main import SoloWindow
        app = QApplication.instance() or QApplication([])
        with patch.object(config,'SETTINGS_FILE',self.root/'settings.json'):
            (self.root/'settings.json').write_text(json.dumps({'game_dir':'D:/custom','language':'zh'}))
            window = SoloWindow()
            try:
                window.multiplier.setValue(1.5)
                job = window.build_action()
                window.multiplier.setValue(2)
                with patch('solo_helper.main.build',return_value={}) as build:
                    job()
                self.assertEqual(build.call_args.args[:2],(1.5,512))
                saved = json.loads(config.SETTINGS_FILE.read_text())
                self.assertEqual(saved['multiplier'],1.5)
                self.assertEqual(saved['game_dir'],'D:/custom')
                self.assertEqual(saved['language'],'zh')
            finally:
                window.close()

    def test_select_game_dir_cancelled(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from solo_helper.main import SoloWindow
        app = QApplication.instance() or QApplication([])
        orig_game_dir = config.GAME_DIR
        window = SoloWindow()
        try:
            with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=''):
                window.select_game_dir()
            self.assertEqual(config.GAME_DIR, orig_game_dir)
        finally:
            window.close()

    def test_select_game_dir_invalid_rejected(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from solo_helper.main import SoloWindow
        app = QApplication.instance() or QApplication([])
        orig_game_dir = config.GAME_DIR
        window = SoloWindow()
        try:
            invalid_dir = self.root / 'invalid_game_dir'
            invalid_dir.mkdir()
            with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(invalid_dir)):
                window.select_game_dir()
            self.assertEqual(config.GAME_DIR, orig_game_dir)
            self.assertIn('未找到 theHunterCotW_F.exe', window.activity.text())
        finally:
            window.close()

    def test_select_game_dir_valid_updates_and_persists(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from solo_helper.main import SoloWindow
        app = QApplication.instance() or QApplication([])
        window = SoloWindow()
        try:
            valid_dir = self.root / 'custom_valid_game'
            valid_dir.mkdir()
            (valid_dir / 'theHunterCotW_F.exe').write_bytes(b'FAKE_COTW_EXE')
            with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(valid_dir)):
                window.select_game_dir()
            self.assertEqual(config.GAME_DIR, valid_dir.resolve())
            self.assertEqual(config.GAME_EXE, (valid_dir / 'theHunterCotW_F.exe').resolve())
            self.assertIn('已指定游戏目录', window.activity.text())
            saved = json.loads(config.SETTINGS_FILE.read_text(encoding='utf-8'))
            self.assertEqual(saved['game_dir'], str(valid_dir.resolve()))
        finally:
            window.close()

    def test_path_finder_prioritizes_exe_settings_over_cwd(self):
        from services.path_finder import detect_steam_cotw_dir
        exe_dir = self.root / 'tool_dist'
        exe_dir.mkdir()
        (exe_dir / 'solo_helper').mkdir()
        cwd_dir = self.root / 'cwd_dir'
        cwd_dir.mkdir()
        game_a = self.root / 'game_canonical'
        game_a.mkdir()
        (game_a / 'theHunterCotW_F.exe').write_bytes(b'EXE_A')
        game_b = self.root / 'game_cwd'
        game_b.mkdir()
        (game_b / 'theHunterCotW_F.exe').write_bytes(b'EXE_B')

        (exe_dir / 'solo_helper' / 'settings.json').write_text(json.dumps({'game_dir': str(game_a)}), encoding='utf-8')
        (cwd_dir / 'settings.json').write_text(json.dumps({'game_dir': str(game_b)}), encoding='utf-8')

        prev_cwd = Path.cwd()
        try:
            import os
            os.chdir(cwd_dir)
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe_dir / 'COTW_SoloHelper.exe')):
                found = detect_steam_cotw_dir()
            self.assertEqual(found, game_a.resolve())
            self.assertNotEqual(found, game_b.resolve())
        finally:
            os.chdir(prev_cwd)
