"""独立探针与Helper共享互斥；竞争失败不能进入实际游戏逻辑。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory.process_reader import ReadError
from solo_helper import config
from solo_helper.trial_guard import position_trial_guard,exclusive_position_trial


class TrialGuardTests(unittest.TestCase):
    def test_second_trial_refused_and_exception_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config,'POSITION_TRIAL_LOCK',Path(temp)/'trial.lock'):
            entered = []

            @exclusive_position_trial
            def attempt():
                entered.append(True)
                raise RuntimeError('模拟实验失败')

            with position_trial_guard():
                with self.assertRaises(ReadError):
                    attempt()
                self.assertEqual(entered,[])
            with self.assertRaises(RuntimeError):
                attempt()
            self.assertEqual(entered,[True])
            with position_trial_guard():
                pass
