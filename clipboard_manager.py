"""
验证码助手 - 剪贴板管理模块
支持 Windows 官方安全规范：
注入 CanIncludeInClipboardHistory、CanUploadToCloudClipboard 等格式，彻底阻断 Win+V 记录；
引入 Generation 版本令牌机制，彻底根除高并发/短间隔下旧定时器竞态误清空新验证码的严重漏洞；
支持用户自主开关剪贴板自动清理功能，并支持手动配置超时秒数。
"""
import ctypes
from ctypes import wintypes
import time
import threading
from typing import Optional, Callable
import pyperclip
import keyboard
from config import PASTE_CLEANUP_DELAY_SECONDS
from logger import app_logger, mask_code

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wintypes.UINT

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040

class ClipboardManager:
    def __init__(
        self,
        cleanup_enabled: bool = True,
        timeout_seconds: float = 60.0,
        paste_delay_seconds: float = PASTE_CLEANUP_DELAY_SECONDS,
        on_copied_callback: Optional[Callable[[str], None]] = None
    ):
        self.cleanup_enabled = cleanup_enabled
        self.timeout_seconds = timeout_seconds
        self.paste_delay_seconds = paste_delay_seconds
        self.on_copied_callback = on_copied_callback

        self._current_code: Optional[str] = None
        self._copy_timestamp: float = 0.0
        self._copy_generation: int = 0 # 自增版本令牌，彻底防止旧 Timer 误删新验证码
        self._lock = threading.Lock()
        self._timeout_timer: Optional[threading.Timer] = None
        self._paste_timer: Optional[threading.Timer] = None
        self._hotkey_hooked = False

        # 注册 Windows 敏感数据防记录格式
        self._cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
        self._cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
        self._cf_ignore = user32.RegisterClipboardFormatW("Clipboard Viewer Ignore")
        self._cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")

    def update_config(self, cleanup_enabled: bool, timeout_seconds: float):
        """动态更新自动清理开关与超时时间"""
        with self._lock:
            self.cleanup_enabled = cleanup_enabled
            self.timeout_seconds = max(1.0, float(timeout_seconds))

            if not self.cleanup_enabled:
                if self._timeout_timer and self._timeout_timer.is_alive():
                    self._timeout_timer.cancel()
                    self._timeout_timer = None
                if self._paste_timer and self._paste_timer.is_alive():
                    self._paste_timer.cancel()
                    self._paste_timer = None

    def get_remaining_countdown(self) -> int:
        with self._lock:
            if not self.cleanup_enabled:
                return -1
            if not self._current_code or self._copy_timestamp <= 0:
                return 0
            elapsed = time.time() - self._copy_timestamp
            remaining = int(self.timeout_seconds - elapsed)
            return max(0, remaining)

    def is_holding_code(self) -> bool:
        with self._lock:
            return self._current_code is not None

    def start_listener(self):
        if self._hotkey_hooked:
            return
        try:
            keyboard.add_hotkey('ctrl+v', self._on_ctrl_v, suppress=False)
            self._hotkey_hooked = True
        except Exception as e:
            app_logger.warning(f"注册 Ctrl+V 热键监听失败: {e}")

    def stop_listener(self):
        with self._lock:
            if self._timeout_timer and self._timeout_timer.is_alive():
                self._timeout_timer.cancel()
                self._timeout_timer = None

            if self._paste_timer and self._paste_timer.is_alive():
                self._paste_timer.cancel()
                self._paste_timer = None

            self._current_code = None
            self._copy_timestamp = 0.0
            self._copy_generation += 1

        if self._hotkey_hooked:
            try:
                keyboard.remove_hotkey('ctrl+v')
            except Exception:
                pass
            self._hotkey_hooked = False

    def copy_code(self, code: str, notification_id: int):
        """将提取到的验证码安全复制到剪贴板，并注入防 Win+V 记录标记"""
        if not code:
            return

        with self._lock:
            success = self._safe_set_secure_clipboard(code)
            if not success:
                app_logger.error(f"写入系统剪贴板失败 (通知 ID: {notification_id})")
                return

            self._current_code = code
            self._copy_timestamp = time.time()
            self._copy_generation += 1 # 递增版本令牌，旧定时器自动失效
            current_gen = self._copy_generation

            masked = mask_code(code)
            app_logger.info(f"验证码安全复制成功 (通知 ID: {notification_id}, 验证码: {masked}, 版本: {current_gen})")

            # 启动带版本令牌绑定的定时器
            if self.cleanup_enabled:
                if self._timeout_timer and self._timeout_timer.is_alive():
                    self._timeout_timer.cancel()

                self._timeout_timer = threading.Timer(
                    self.timeout_seconds,
                    self._timeout_cleanup_callback,
                    args=[code, current_gen]
                )
                self._timeout_timer.daemon = True
                self._timeout_timer.start()

        if self.on_copied_callback:
            try:
                self.on_copied_callback(code)
            except Exception as e:
                app_logger.warning(f"执行复制通知回调异常: {e}")

    def _on_ctrl_v(self):
        """用户按下 Ctrl+V 时的响应逻辑"""
        with self._lock:
            if not self.cleanup_enabled or not self._current_code:
                return

            target_code = self._current_code
            target_gen = self._copy_generation

            if self._paste_timer and self._paste_timer.is_alive():
                self._paste_timer.cancel()

            self._paste_timer = threading.Timer(
                self.paste_delay_seconds,
                self._paste_cleanup_callback,
                args=[target_code, target_gen]
            )
            self._paste_timer.daemon = True
            self._paste_timer.start()

    def _timeout_cleanup_callback(self, expected_code: str, expected_gen: int):
        """超时清理：原子比对版本令牌与剪贴板内容，杜绝竞态误删新验证码"""
        with self._lock:
            # 1. 检查版本令牌：如果后续有新的复制，旧定时器直接退出
            if self._copy_generation != expected_gen or not self.cleanup_enabled:
                return

            current_clipboard = self._safe_get_clipboard()
            if current_clipboard == expected_code:
                self._safe_set_secure_clipboard("")
                self._current_code = None
                self._copy_timestamp = 0.0
                app_logger.info(f"剪贴板超时已达 {self.timeout_seconds} 秒，安全清空验证码 (版本: {expected_gen})")
            else:
                if self._current_code == expected_code:
                    self._current_code = None
                    self._copy_timestamp = 0.0

    def _paste_cleanup_callback(self, expected_code: str, expected_gen: int):
        """Ctrl+V 延迟清理：原子比对版本令牌与剪贴板内容"""
        with self._lock:
            if self._copy_generation != expected_gen or not self.cleanup_enabled:
                return

            current_clipboard = self._safe_get_clipboard()
            if current_clipboard == expected_code:
                self._safe_set_secure_clipboard("")
                self._current_code = None
                self._copy_timestamp = 0.0
                app_logger.info(f"检测到用户完成 Ctrl+V 粘贴，延迟安全清空验证码 (版本: {expected_gen})")
            else:
                if self._current_code == expected_code:
                    self._current_code = None
                    self._copy_timestamp = 0.0

    def _safe_get_clipboard(self) -> str:
        for _ in range(3):
            try:
                return pyperclip.paste()
            except Exception:
                time.sleep(0.05)
        return ""

    def _safe_set_secure_clipboard(self, text: str) -> bool:
        opened = False
        for _ in range(10):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.05)

        if not opened:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                return False

        try:
            user32.EmptyClipboard()

            if text:
                text_bytes = (text + '\0').encode('utf-16le')
                h_text = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if h_text:
                    p_text = kernel32.GlobalLock(h_text)
                    if p_text:
                        ctypes.memmove(p_text, text_bytes, len(text_bytes))
                        kernel32.GlobalUnlock(h_text)
                        user32.SetClipboardData(CF_UNICODETEXT, h_text)

                for cf in (self._cf_history, self._cf_cloud, self._cf_ignore, self._cf_exclude):
                    if cf:
                        h_flag = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, 4)
                        if h_flag:
                            p_flag = kernel32.GlobalLock(h_flag)
                            if p_flag:
                                ctypes.memset(p_flag, 0, 4)
                                kernel32.GlobalUnlock(h_flag)
                                user32.SetClipboardData(cf, h_flag)

            return True
        except Exception as e:
            app_logger.warning(f"设置安全剪贴板异常: {e}")
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                return False
        finally:
            user32.CloseClipboard()
