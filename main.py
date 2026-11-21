"""
验证码助手 (Captcha Assistant) - 主程序入口
结合 Windows 11 Fluent Design 轻量桌面界面与后台常驻系统托盘
支持扫描间隔毫秒级设置与剪贴板自动清理开关
"""
import os
import sys
import threading
import time
from datetime import datetime
import win32event
import win32api
import winerror

from config import (
    APP_NAME, APP_VERSION, load_settings, save_settings, NOTIFICATION_DB_PATH, APP_DIR, LOG_FILE,
    is_auto_start_enabled, set_auto_start
)
from logger import app_logger, mask_code
from notification_reader import NotificationReader
from code_detector import CodeDetector
from clipboard_manager import ClipboardManager
from tray import SystemTray
from ui import MainWindow

class CaptchaAssistantApp:
    def __init__(self):
        self.stop_event = threading.Event()
        self.is_paused = False
        self.pause_lock = threading.Lock()

        # 加载用户设置
        self.settings = load_settings()
        self.scan_interval_ms = int(self.settings.get("scan_interval_ms", 3000))
        self.cleanup_enabled = bool(self.settings.get("enable_clipboard_cleanup", True))
        self.clipboard_timeout_sec = int(self.settings.get("clipboard_timeout_sec", 60))

        # 状态追踪字段 (线程安全共享给 UI 读取)
        self.state_lock = threading.Lock()
        self.db_ready = False
        self.last_scan_time = ""
        self.last_status_msg = "等待接收新短信..."

        # 单实例句柄
        self.mutex_handle = None

        # 核心子组件
        self.reader = NotificationReader()
        self.clipboard_mgr = ClipboardManager(
            cleanup_enabled=self.cleanup_enabled,
            timeout_seconds=self.clipboard_timeout_sec,
            on_copied_callback=self._on_code_copied
        )

        # 托盘组件
        self.tray = SystemTray(
            on_show_ui=self._request_show_ui,
            on_pause_callback=self.toggle_pause,
            on_resume_callback=self.toggle_pause,
            on_exit_callback=self.stop,
            is_paused_check=lambda: self.is_paused
        )

        # 检查是否以静默模式启动 (例如开机自启或快捷方式携带参数)
        start_minimized = ("--minimized" in sys.argv) or ("--silent" in sys.argv)

        # UI 界面组件 (主线程运行)
        self.ui = MainWindow(
            on_toggle_pause=self.toggle_pause,
            on_open_log=self._open_log,
            on_open_dir=self._open_dir,
            on_save_settings=self._apply_new_settings,
            get_status_snapshot=self.get_status_snapshot,
            on_request_exit=self.stop,
            start_minimized=start_minimized
        )

        self.scan_thread: threading.Thread = None

    def check_single_instance(self) -> bool:
        """使用 Windows 命名互斥体确保同一时间仅运行一个实例"""
        mutex_name = "Global\\CaptchaAssistant_Windows_SingleInstance_Mutex"
        try:
            self.mutex_handle = win32event.CreateMutex(None, False, mutex_name)
            last_error = win32api.GetLastError()
            if last_error == winerror.ERROR_ALREADY_EXISTS:
                app_logger.warning("检测到已有实例正在运行，当前进程退出")
                return False
            return True
        except Exception as e:
            app_logger.warning(f"创建单实例互斥体异常: {e}，继续启动")
            return True

    def _request_show_ui(self):
        """跨线程安全请求显示主窗口"""
        if self.ui and self.ui.root:
            self.ui.root.after(0, self.ui.show_window)

    def _on_code_copied(self, code: str):
        """验证码复制回调"""
        self.tray.notify_code_copied(code)

    def toggle_pause(self):
        """切换暂停/监控状态"""
        with self.pause_lock:
            self.is_paused = not self.is_paused
            current_paused = self.is_paused

        if current_paused:
            app_logger.info("监控已暂停（停止扫描通知与识别）")
        else:
            app_logger.info("监控已恢复（继续正常扫描处理）")

        self.tray.refresh_menu()
        if self.ui:
            self.ui.root.after(0, self.ui.refresh_state)

    def _apply_new_settings(self, new_interval_ms: int, new_cleanup_enabled: bool, new_timeout_sec: int, new_auto_start: bool):
        """保存并应用新设置"""
        self.scan_interval_ms = new_interval_ms
        self.cleanup_enabled = new_cleanup_enabled
        self.clipboard_timeout_sec = new_timeout_sec

        self.clipboard_mgr.update_config(new_cleanup_enabled, new_timeout_sec)

        # 同步开机自启系统设置 (注册表)
        set_auto_start(new_auto_start)

        self.settings["scan_interval_ms"] = new_interval_ms
        self.settings["enable_clipboard_cleanup"] = new_cleanup_enabled
        self.settings["clipboard_timeout_sec"] = new_timeout_sec
        self.settings["auto_start"] = new_auto_start
        save_settings(self.settings)

        app_logger.info(f"已更新设置：扫描间隔={new_interval_ms}毫秒，自动清理={new_cleanup_enabled}，清理超时={new_timeout_sec}秒，开机自启={new_auto_start}")
        if self.ui:
            self.ui.root.after(0, self.ui.refresh_state)

    def _open_log(self):
        try:
            if not os.path.exists(LOG_FILE):
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write("")
            os.startfile(LOG_FILE)
        except Exception as e:
            app_logger.error(f"打开日志文件失败: {e}")

    def _open_dir(self):
        try:
            os.startfile(APP_DIR)
        except Exception as e:
            app_logger.error(f"打开程序目录失败: {e}")

    def get_status_snapshot(self) -> dict:
        """获取当前系统运行状态快照供 UI 渲染"""
        with self.state_lock:
            db_status = self.db_ready
            scan_time = self.last_scan_time
            status_msg = self.last_status_msg

        countdown = self.clipboard_mgr.get_remaining_countdown()

        return {
            "is_paused": self.is_paused,
            "db_ready": db_status,
            "last_scan_time": scan_time,
            "last_status_msg": status_msg,
            "countdown": countdown,
            "scan_interval_ms": self.scan_interval_ms,
            "cleanup_enabled": self.cleanup_enabled,
            "clipboard_timeout_sec": self.clipboard_timeout_sec,
            "auto_start": is_auto_start_enabled()
        }

    def _scan_loop(self):
        """后台独立守护扫描循环"""
        app_logger.info("后台通知扫描线程已启动")

        init_ok = self.reader.initialize()
        with self.state_lock:
            self.db_ready = init_ok

        while not self.stop_event.is_set():
            try:
                now_str = datetime.now().strftime("%H:%M:%S")
                with self.state_lock:
                    self.last_scan_time = now_str
                    self.db_ready = os.path.exists(NOTIFICATION_DB_PATH)

                if not self.is_paused:
                    records = self.reader.get_new_notifications()
                    for record in records:
                        if self.stop_event.is_set():
                            break

                        text = record.parse_text()
                        if text:
                            code = CodeDetector.extract_code(text)
                            if code:
                                masked = mask_code(code)
                                app_logger.info(f"识别到短信验证码 (通知 ID: {record.id}, 验证码: {masked})")
                                self.clipboard_mgr.copy_code(code, record.id)
                                with self.state_lock:
                                    self.last_status_msg = f"成功提取: {masked} (ID: {record.id})"

                        self.reader.update_last_id(record.id)

            except Exception as e:
                app_logger.error(f"后台扫描轮询异常: {e}", exc_info=True)

            # 将毫秒转换为秒进行 wait
            interval_sec = max(0.3, self.scan_interval_ms / 1000.0)
            self.stop_event.wait(interval_sec)

        app_logger.info("后台通知扫描线程已安全退出")

    def start(self):
        app_logger.info(f"===== {APP_NAME} v{APP_VERSION} 启动 =====")
        app_logger.info(f"Python 运行环境: {sys.version.split()[0]}")

        if not self.check_single_instance():
            print("程序已在运行中，请检查系统托盘。")
            return

        self.clipboard_mgr.start_listener()

        self.scan_thread = threading.Thread(target=self._scan_loop, name="ScannerThread", daemon=True)
        self.scan_thread.start()

        self.tray.run_detached()

        try:
            self.ui.run()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            app_logger.error(f"主界面循环异常: {e}", exc_info=True)
            self.stop()

    def stop(self):
        """退出程序并释放所有资源"""
        app_logger.info("正在退出应用程序...")
        self.stop_event.set()

        self.clipboard_mgr.stop_listener()
        self.tray.stop()

        if self.ui:
            try:
                self.ui.destroy_window()
            except Exception:
                pass

        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=1.5)

        if self.mutex_handle:
            try:
                win32api.CloseHandle(self.mutex_handle)
            except Exception:
                pass
            self.mutex_handle = None

        app_logger.info(f"===== {APP_NAME} 已安全退出 =====\n")
        sys.exit(0)

def main():
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        app_logger.error("未捕获的全局严重异常", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    app = CaptchaAssistantApp()
    app.start()

if __name__ == "__main__":
    main()
