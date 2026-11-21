"""
验证码助手 - 系统托盘模块
负责系统托盘图标加载、菜单交互、Windows 11 气泡通知、主界面唤起与程序退出
"""
import os
import sys
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray
from config import ICON_FILE, LOG_FILE, APP_DIR, APP_NAME
from logger import app_logger, mask_code

def create_fallback_image() -> Image.Image:
    """生成精致的保底内存图标，防止外部 ICO 文件缺失导致崩溃"""
    size = (64, 64)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=14, fill=(0, 120, 212, 255), outline=(0, 95, 175, 255), width=2)
    draw.rounded_rectangle([12, 16, 52, 46], radius=6, fill=(255, 255, 255, 255))
    for x in (20, 28, 36, 44):
        draw.ellipse([x - 2, 31 - 2, x + 2, 31 + 2], fill=(0, 120, 212, 255))
    return img

class SystemTray:
    def __init__(
        self,
        on_show_ui: Callable[[], None],
        on_pause_callback: Callable[[], None],
        on_resume_callback: Callable[[], None],
        on_exit_callback: Callable[[], None],
        is_paused_check: Callable[[], bool]
    ):
        self.on_show_ui = on_show_ui
        self.on_pause_callback = on_pause_callback
        self.on_resume_callback = on_resume_callback
        self.on_exit_callback = on_exit_callback
        self.is_paused_check = is_paused_check

        self.icon: Optional[pystray.Icon] = None
        self._image = self._load_icon_image()
        self._tray_thread: Optional[threading.Thread] = None

    def _load_icon_image(self) -> Image.Image:
        if os.path.exists(ICON_FILE):
            try:
                img = Image.open(ICON_FILE)
                return img
            except Exception as e:
                app_logger.warning(f"加载 ICO 失败: {e}，使用内置备用图标")
        return create_fallback_image()

    def _build_menu(self) -> pystray.Menu:
        is_paused = self.is_paused_check()
        status_text = "❚❚ 状态：已暂停监控" if is_paused else "● 状态：正在监控短信"

        items = [
            pystray.MenuItem("🖥 打开主界面", self._handle_show_ui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(status_text, lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR
        ]

        if is_paused:
            items.append(pystray.MenuItem("▶ 恢复监控", self._handle_resume))
        else:
            items.append(pystray.MenuItem("❚❚ 暂停监控", self._handle_pause))

        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📄 查看运行日志", self._handle_open_log),
            pystray.MenuItem("📁 打开程序目录", self._handle_open_dir),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ 退出程序", self._handle_exit)
        ])

        return pystray.Menu(*items)

    def _handle_show_ui(self, icon, item):
        if self.on_show_ui:
            self.on_show_ui()

    def _handle_pause(self, icon, item):
        self.on_pause_callback()
        self.refresh_menu()

    def _handle_resume(self, icon, item):
        self.on_resume_callback()
        self.refresh_menu()

    def _handle_open_log(self, icon, item):
        try:
            if not os.path.exists(LOG_FILE):
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write("")
            os.startfile(LOG_FILE)
        except Exception as e:
            app_logger.error(f"打开日志文件失败: {e}")

    def _handle_open_dir(self, icon, item):
        try:
            os.startfile(APP_DIR)
        except Exception as e:
            app_logger.error(f"打开程序目录失败: {e}")

    def _handle_exit(self, icon, item):
        app_logger.info("用户点击托盘菜单【退出程序】")
        if self.icon:
            self.icon.stop()
        self.on_exit_callback()

    def refresh_menu(self):
        if self.icon:
            self.icon.menu = self._build_menu()

    def notify_code_copied(self, code: str):
        if self.icon and self.icon.HAS_NOTIFICATION:
            try:
                masked = mask_code(code)
                self.icon.notify(
                    title=f"{APP_NAME} - 验证码已复制",
                    message=f"识别到短信验证码：{masked}\n已自动复制到剪贴板，可直接 Ctrl+V 粘贴！"
                )
            except Exception as e:
                app_logger.warning(f"托盘弹窗通知异常: {e}")

    def run_detached(self):
        """在独立后台线程中运行托盘消息循环，使主线程可以运行 Tkinter GUI"""
        self.icon = pystray.Icon(
            name="CaptchaAssistant",
            icon=self._image,
            title=f"{APP_NAME} (后台运行中)",
            menu=self._build_menu()
        )
        self._tray_thread = threading.Thread(target=self.icon.run, name="TrayThread", daemon=True)
        self._tray_thread.start()

    def stop(self):
        """停止托盘"""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
