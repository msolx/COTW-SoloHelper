"""独立GUI入口：生成和管理单人参数Mod，不连接雷达扫描线程。"""
import json
import math
import sys
from PySide6.QtCore import QThread,Signal,QLockFile
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QApplication,QWidget
from solo_helper import config
from solo_helper.builder import build,verify_build
from solo_helper.installer import install,uninstall,launch,require_closed
from solo_helper.native_request_trial import inspect_trial as inspect_native_trial,run as run_native_trial
from solo_helper.pressure import preview_current_pressure,run_clear as clear_current_pressure


def load_settings():
    values = dict(multiplier=config.CROUCH_MULTIPLIER,capacity=int(config.BASE_CAPACITY_KG),
                  crouch=True,carry=True,
                  foxpro=config.FOXPRO_RANGE_ENABLED,
                  spotting=config.SPOTTING_ENABLED,spotting_seconds=config.SPOTTING_SECONDS)
    try:
        raw = json.loads(config.SETTINGS_FILE.read_text(encoding='utf-8'))
        multiplier,capacity = raw.get('multiplier'),raw.get('capacity')
        if type(multiplier) in (float,int) and math.isfinite(multiplier) and 1 <= multiplier <= config.MAX_CROUCH_MULTIPLIER:
            values['multiplier'] = multiplier
        if type(capacity) is int and 1 <= capacity <= 999:
            values['capacity'] = capacity
        for key in ('crouch','carry','foxpro','spotting'):
            if type(raw.get(key)) is bool:
                values[key] = raw[key]
        seconds=raw.get('spotting_seconds')
        if type(seconds) is int and 120<=seconds<=999:
            values['spotting_seconds']=seconds
    except (OSError,ValueError,AttributeError):
        pass
    return values



class Task(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(object)
    def __init__(self,action,*,with_progress=False):
        super().__init__()
        self.action = action
        self.with_progress = with_progress
    def run(self):
        try:
            self.completed.emit(self.action(self.progress.emit) if self.with_progress else self.action())
        except Exception as exc:
            self.failed.emit(str(exc))


class SoloWindow(QWidget):
    def __init__(self):
        super().__init__()
        helper_ico = config.PROJECT / 'icons' / 'helper.ico'
        if helper_ico.exists():
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(str(helper_ico)))
        self.task = None
        self.native_trial_blocked = False
        self.native_waiting = False
        self.pressure_blocked = False
        self.task_action = None
        from solo_helper.window_layout import build_layout
        build_layout(self,load_settings())
        self.singleplayer.toggled.connect(self.update_trial_button)
        self.flat_ground.toggled.connect(self.update_trial_button)
        self.shortcuts = []
        for key,action in (('Ctrl+B','build'),('Ctrl+L','launch'),('Ctrl+Shift+T','native_virtual')):
            shortcut=QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(lambda a=action:self.dispatch(a))
            self.shortcuts.append(shortcut)
        self.update_trial_button()

    def settings_changed(self,*args):
        self.settings_status.setText('设置已更改，尚未应用。游戏退出后点击“应用设置”。')

    def update_trial_button(self):
        busy = bool(self.task and self.task.isRunning())
        if busy and self.task_action=='native_virtual' and self.native_waiting and not self.singleplayer.isChecked():
            self.cancel_native()
        self.native_enable.setEnabled(not busy and not self.native_trial_blocked
                                      and self.singleplayer.isChecked() and self.flat_ground.isChecked())
        self.native_cancel.setEnabled(busy and self.task_action=='native_virtual' and self.native_waiting)
        self.pressure_clear.setEnabled(not busy and not self.pressure_blocked and self.singleplayer.isChecked())

    def pressure_action(self):
        if self.pressure_blocked or not self.singleplayer.isChecked():
            raise RuntimeError('请先确认单人；若本轮压力写入失败，先保留日志，不反复操作')
        return lambda:clear_current_pressure(singleplayer_confirmed=True,approved=True)

    def cancel_native(self):
        if not (self.task and self.task.isRunning() and self.task_action=='native_virtual'):
            return
        try:
            config.NATIVE_REDIRECT_CANCEL_FILE.write_text('cancel waiting\n',encoding='utf-8')
        except OSError as exc:
            self.log.appendPlainText('取消请求未能保存：'+str(exc))
            return
        self.native_cancel.setEnabled(False)
        self.native_waiting = False
        self.native_status.setText('已请求取消等待；若原生移动已提交，将只完成观察与清理，不回写旧位置。')
        self.activity.setText(self.native_status.text())

    def display_progress(self,value):
        event = value.get('event')
        if event=='armed':
            self.native_waiting = True
            xyz = value['target_position']
            self.native_status.setText(f'已就绪：地图航点约{xyz[0]:.1f}、{xyz[2]:.1f}已临时转换。回游戏点该图标的快速移动一次；不要重设航点或点击真实帐篷。')
        elif event=='request_written':
            self.native_waiting = False
            self.native_status.setText('已提交本次原生请求；留在游戏等待加载，只点一次，不重复快速移动。')
        elif event=='marker_restored':
            self.log.appendPlainText('临时图标清理：'+json.dumps(value['restoration'],ensure_ascii=False))
        elif event=='idle_observing':
            self.native_status.setText(f'原生移动已结束，继续观察约{value["seconds"]:g}秒。先站稳，再检查走动；不要再次快速移动。')
        self.activity.setText(self.native_status.text())
        self.update_trial_button()

    def native_action(self):
        if self.native_trial_blocked:
            raise RuntimeError('原生功能因权限或清理错误已停止；查看日志，不重复写入')
        if not (self.singleplayer.isChecked() and self.flat_ground.isChecked()):
            raise RuntimeError('先确认本机单人及本次干燥无障碍落点')
        self.flat_ground.setChecked(False)
        def job(progress):
            preview = inspect_native_trial(virtual_marker=True)
            if preview.get('status')!='ready_for_confirmed_trial':
                return dict(kind='native_preflight',status='preflight_rejected',write_attempted=False,
                            preflight=preview,error=preview.get('error','当前航点不满足条件'),
                            access_error=preview.get('access_error'))
            return run_native_trial(approved=True,single_player_confirmed=True,flat_ground_confirmed=True,
                                    expected_waypoint_marker=tuple(preview['waypoint_marker']),
                                    virtual_marker=True,progress=progress)
        return job

    def display_result(self,value):
        if isinstance(value,dict) and value.get('kind') in ('pressure_preview','clear_current_reserve_pressure'):
            if value.get('access_error') or (value.get('write_attempted') and value.get('status')!='cleared_current_reserve_pressure'):
                self.pressure_blocked=True
            if value.get('status')=='pressure_readonly':
                self.pressure_status.setText(f'当前保护区槽位{value["pressure"]["reserve_slot"]}：非零压力网格{value["pressure"]["nonzero_cells"]}格；尚未清除。')
            elif value.get('status')=='cleared_current_reserve_pressure':
                self.pressure_status.setText('当前保护区已有压力已复读为零；请正常重开地图核对紫色区域。未来狩猎仍会新增压力。')
            else:
                self.pressure_status.setText('压力操作停止：'+str(value.get('error',value.get('status'))))
            self.update_trial_button()
        if self.task_action in ('native_virtual','native_preview') and isinstance(value,dict):
            self.native_waiting = False
            restoration = value.get('marker_restoration',{})
            if (value.get('access_error') or value.get('cleanup_access_error')
                    or value.get('marker_restore_error')
                    or restoration.get('status') in ('restore_failed_no_retry','not_retried_after_api_error')):
                self.native_trial_blocked = True
                self.update_trial_button()
            status = value.get('status')
            if status=='ready_for_confirmed_trial':
                evidence=value.get('ground_evidence') or {}
                if evidence.get('kind')=='base_collision_mesh_crosscheck':
                    delta=evidence['waypoint'][1]-evidence['target_mesh_height']
                    self.native_status.setText(f'基础碰撞网格复核通过：目标差{delta:+.2f}米；'
                                              '仍须确认干燥无障碍，再启用本次临时航点帐篷。')
                else:
                    self.native_status.setText('只读检查通过；确认地面后可启用本次临时航点帐篷。')
            elif status in ('position_reached_observation_required','position_reached_later_position_changed'):
                self.native_status.setText('已观测到原生移动到达航点；请核对画面和正常走动。临时图标清理结果见日志。')
            else:
                self.native_status.setText('本轮已结束：'+str(value.get('error',status))+'；图标清理结果见日志。')
        if self.task_action in ('apply','install'):
            self.settings_status.setText('专用目录已安装。参数将在重新启动游戏后加载；实际效果仍需核对。')
        elif self.task_action=='build':
            self.settings_status.setText('文件已生成，尚未安装。可在退出游戏后点击“应用设置”。')
        elif self.task_action=='uninstall':
            self.settings_status.setText('本工具Mod已卸载。当前控件仅为待应用设置。')
        self.activity.setText('操作完成；详情见“操作记录”。')
        if self.task_action in ('native_virtual','native_preview'):
            self.activity.setText(self.native_status.text())
        elif self.task_action in ('pressure_preview','pressure_clear'):
            self.activity.setText(self.pressure_status.text())
        if isinstance(value,dict) and 'samples' in value:
            samples = value['samples']
            value = {k:v for k,v in value.items() if k != 'samples'}
            value['采样数量'] = len(samples)
            if samples:
                value['最终状态'] = samples[-1]
        self.log.appendPlainText(json.dumps(value,ensure_ascii=False,indent=2) if isinstance(value,dict) else str(value))

    def task_failed(self,error):
        self.log.appendPlainText('操作未完成：'+error)
        self.activity.setText('操作未完成：'+error)
        if self.task_action in ('native_virtual','native_preview'):
            self.native_waiting = False
            self.native_status.setText('操作未完成：'+error)
            self.update_trial_button()

    def build_action(self):
        values = dict(multiplier=self.multiplier.value(),capacity=self.capacity.value(),
                      crouch=self.crouch.isChecked(),carry=self.carry.isChecked(),foxpro=self.foxpro.isChecked(),
                      spotting=self.spotting.isChecked(),spotting_seconds=self.spotting_seconds.value())
        config.SETTINGS_FILE.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
        return lambda:build(values['multiplier'],values['capacity'],values['crouch'],values['carry'],
                            foxpro_enabled=values['foxpro'],spotting_enabled=values['spotting'],
                            spotting_seconds=values['spotting_seconds'])

    def dispatch(self,action):
        if self.task and self.task.isRunning():
            return
        try:
            if action == 'build':
                job = self.build_action()
            elif action == 'apply':
                if not self.singleplayer.isChecked():
                    raise RuntimeError('请先确认本次只使用单人模式')
                build_job=self.build_action()
                def job():
                    # 游戏仍运行时立即停止；不先生成，更不会安装一半。
                    require_closed()
                    build_job()
                    return install(True)
            elif action == 'native_preview':
                job = lambda:inspect_native_trial(virtual_marker=True)
            elif action == 'native_virtual':
                job = self.native_action()
            elif action == 'pressure_preview':
                job = preview_current_pressure
            elif action == 'pressure_clear':
                job = self.pressure_action()
            else:
                # 确认值在创建任务时捕获；后台不读取QCheckBox。
                confirmed = self.singleplayer.isChecked()
                job = {'verify':verify_build,'install':lambda:install(confirmed),
                       'launch':lambda:launch(confirmed),'uninstall':uninstall}[action]
        except Exception as exc:
            self.log.appendPlainText('操作未完成：'+str(exc))
            self.activity.setText('操作未完成：'+str(exc))
            return
        self.task_action = action
        self.native_waiting = False
        self.task = Task(job,with_progress=action=='native_virtual')
        for button in self.buttons:
            button.setEnabled(False)
        for control in self.setting_inputs:
            control.setEnabled(False)
        self.task.completed.connect(self.display_result)
        self.task.progress.connect(self.display_progress)
        self.task.failed.connect(self.task_failed)
        self.task.finished.connect(self.finished)
        self.activity.setText('正在处理，请稍候…')
        self.log.appendPlainText('开始操作：'+action)
        self.task.start()

    def finished(self):
        self.native_waiting = False
        for button in self.buttons:
            button.setEnabled(True)
        for control in self.setting_inputs:
            control.setEnabled(True)
        self.update_trial_button()

    def closeEvent(self,event):
        if self.task and self.task.isRunning():
            self.log.appendPlainText('请先取消等待并等图标清理完成，或等待当前操作结束后关闭；不会强制终止后台任务。')
            self.activity.setText('当前操作尚未结束；如在等待传送，请先取消等待，清理完成后再关闭。')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv[:1])
    from services.fonts import setup_fonts
    setup_fonts(app)
    lock = QLockFile(str(config.ROOT/'solo_helper.lock'))
    if not lock.tryLock(0):
        return 1
    window = SoloWindow()
    window.show()
    try:
        return app.exec()
    finally:
        lock.unlock()


if __name__ == '__main__':
    raise SystemExit(main())
