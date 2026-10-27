"""位置实验跨进程互斥：只锁本地工具，不访问游戏，不强制终止持锁进程。"""
from contextlib import contextmanager
from functools import wraps

from memory.process_reader import ReadError
from solo_helper import config


@contextmanager
def position_trial_guard():
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(config.POSITION_TRIAL_LOCK))
    if not lock.tryLock(0):
        raise ReadError('另一轮位置实验正在运行，或实验锁不可用；本次未连接或写入游戏')
    try:
        yield
    finally:
        lock.unlock()


def exclusive_position_trial(function):
    @wraps(function)
    def guarded(*args,**kwargs):
        with position_trial_guard():
            return function(*args,**kwargs)
    return guarded
