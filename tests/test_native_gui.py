"""原生航点GUI确认、后台参数、进度和取消；游戏接口全部模拟。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtGui import QCloseEvent
from solo_helper import config
from solo_helper.main import SoloWindow,Task


class NativeGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(config,'SETTINGS_FILE',root/'settings.json'),
                        patch.object(config,'NATIVE_REDIRECT_CANCEL_FILE',root/'cancel')]
        for p in self.patches:
            p.start()
        self.window = SoloWindow()

    def tearDown(self):
        self.window.task = None
        self.window.close()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_ready_status_explains_independent_mesh_evidence(self):
        self.assertIn('水平距离不限',self.window.native_hint.text())
        self.window.task_action='native_preview'
        self.window.display_result(dict(status='ready_for_confirmed_trial',
                 ground_evidence=dict(kind='base_collision_mesh_crosscheck',
                                      waypoint=[0,1000,0],target_mesh_height=1000.12)))
        self.assertIn('基础碰撞网格复核通过',self.window.native_status.text())
        self.assertIn('-0.12',self.window.native_status.text())
        self.assertIn('干燥无障碍',self.window.native_status.text())

    def test_confirmation_and_readonly_failure_gate_native_writer(self):
        window = self.window
        with self.assertRaises(RuntimeError):
            window.native_action()
        window.singleplayer.setChecked(True)
        window.flat_ground.setChecked(True)
        job = window.native_action()
        self.assertFalse(window.flat_ground.isChecked())
        with patch('solo_helper.main.inspect_native_trial',return_value={'status':'stopped','error':'未加载'}),patch('solo_helper.main.run_native_trial') as writer:
            result = job(Mock())
        self.assertEqual(result['status'],'preflight_rejected')
        writer.assert_not_called()

    def test_approved_native_job_binds_preview_coordinate_and_progress(self):
        window = self.window
        window.singleplayer.setChecked(True)
        window.flat_ground.setChecked(True)
        job = window.native_action()
        progress = Mock()
        preview = dict(status='ready_for_confirmed_trial',waypoint_marker=[100,1032,200])
        with patch('solo_helper.main.inspect_native_trial',return_value=preview),patch('solo_helper.main.run_native_trial',return_value={}) as writer:
            job(progress)
        self.assertTrue(writer.call_args.kwargs['virtual_marker'])
        self.assertEqual(writer.call_args.kwargs['expected_waypoint_marker'],(100,1032,200))
        self.assertIs(writer.call_args.kwargs['progress'],progress)

    def test_progress_cancel_and_permission_error_states(self):
        window = self.window
        window.singleplayer.setChecked(True)
        window.task = Mock()
        window.task.isRunning.return_value = True
        window.task_action = 'native_virtual'
        window.display_progress(dict(event='armed',target_position=[100,1030,200]))
        self.assertTrue(window.native_cancel.isEnabled())
        window.cancel_native()
        self.assertTrue(config.NATIVE_REDIRECT_CANCEL_FILE.exists())
        self.assertFalse(window.native_waiting)
        window.display_progress(dict(event='request_written'))
        self.assertFalse(window.native_cancel.isEnabled())
        window.display_result(dict(status='stopped',access_error=dict(stage='test',winerror=5)))
        self.assertTrue(window.native_trial_blocked)
        self.assertFalse(window.native_enable.isEnabled())

    def test_task_progress_and_result_are_separate_signals(self):
        events,results = [],[]
        def job(progress):
            progress(dict(event='armed'))
            return dict(status='done')
        task = Task(job,with_progress=True)
        task.progress.connect(events.append)
        task.completed.connect(results.append)
        task.run()
        self.assertEqual(events,[dict(event='armed')])
        self.assertEqual(results,[dict(status='done')])

    def test_only_virtual_tent_is_exposed_and_old_actions_cannot_start(self):
        window=self.window
        self.assertEqual([window.tabs.tabText(i) for i in range(window.tabs.count())],
                         ['航点传送','单人参数','压力区','操作记录'])
        self.assertFalse(hasattr(window,'teleport'))
        self.assertFalse(hasattr(window,'surface_distance'))
        self.assertNotIn('Ctrl+T',[s.key().toString() for s in window.shortcuts])
        for action in ('waypoint_trial','waypoint_preview'):
            with patch('solo_helper.main.Task') as task:
                window.dispatch(action)
                task.assert_not_called()

    def test_old_stage_settings_are_ignored_and_not_resaved(self):
        import json
        from solo_helper.main import load_settings
        config.SETTINGS_FILE.write_text(json.dumps(dict(multiplier=10,capacity=512,
             surface_trial=True,surface_distance=200,surface_height=20)),encoding='utf-8')
        values=load_settings()
        self.assertEqual(values['multiplier'],10)
        self.assertEqual(values['capacity'],512)
        self.assertFalse(any(key.startswith('surface_') for key in values))
        self.window.build_action()
        saved=json.loads(config.SETTINGS_FILE.read_text(encoding='utf-8'))
        self.assertFalse(any(key.startswith('surface_') for key in saved))

    def test_apply_without_confirmation_does_not_create_task(self):
        with patch('solo_helper.main.Task') as task:
            self.window.dispatch('apply')
        task.assert_not_called()
        self.assertIn('单人',self.window.activity.text())

    def test_apply_stops_before_build_or_install_if_game_is_running(self):
        window=self.window
        window.singleplayer.setChecked(True)
        with patch.object(Task,'start'):
            window.dispatch('apply')
        with patch('solo_helper.main.require_closed',side_effect=RuntimeError('游戏尚未退出')),patch(
                'solo_helper.main.build') as build,patch('solo_helper.main.install') as install:
            window.task.run()
        build.assert_not_called(); install.assert_not_called()
        self.assertIn('游戏尚未退出',window.activity.text())

    def test_apply_runs_closed_check_build_install_in_order_and_captures_settings(self):
        window=self.window
        window.singleplayer.setChecked(True)
        window.multiplier.setValue(10)
        window.capacity.setValue(512)
        with patch.object(Task,'start'):
            window.dispatch('apply')
        self.assertFalse(window.multiplier.isEnabled())
        window.multiplier.setValue(2)  # 模拟后续状态改变，后台仍须使用创建任务时的值。
        order=[]
        with patch('solo_helper.main.require_closed',side_effect=lambda:order.append('closed')),patch(
                'solo_helper.main.build',side_effect=lambda *a,**kw:order.append(('build',a[0],a[1]))),patch(
                'solo_helper.main.install',side_effect=lambda confirmed:order.append(('install',confirmed))):
            window.task.run()
        self.assertEqual(order,['closed',('build',10,512),('install',True)])
        self.assertIn('重新启动',window.settings_status.text())
        window.finished()
        self.assertTrue(window.multiplier.isEnabled())

    def test_busy_close_is_rejected_and_unchecking_singleplayer_cancels_wait(self):
        window=self.window
        window.singleplayer.setChecked(True)
        window.task=Mock(); window.task.isRunning.return_value=True
        window.task_action='native_virtual'
        window.display_progress(dict(event='armed',target_position=[1,1000,2]))
        event=QCloseEvent()
        window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        window.singleplayer.setChecked(False)
        self.assertTrue(config.NATIVE_REDIRECT_CANCEL_FILE.exists())
        self.assertFalse(window.native_waiting)
