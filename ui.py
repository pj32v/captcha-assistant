"""
验证码助手 - Windows 11 Fluent Design 高 DPI 自适应轻量桌面界面
支持后台扫描间隔毫秒级精确自定义输入、剪贴板自动清理自主开关与秒数配置。
具备窗口销毁生命周期防护与键盘快捷操作支持。
"""
import ctypes
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
from config import APP_NAME, APP_VERSION, LOG_FILE, APP_DIR, ICON_FILE
from logger import app_logger

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def get_dpi_scale() -> float:
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return max(1.0, dpi_x / 96.0)
    except Exception:
        return 1.0

SCALE = get_dpi_scale()

def s(px: int) -> int:
    return int(round(px * SCALE))

def font_px(size_pt: int) -> int:
    return -max(10, int(round(size_pt * SCALE * (96.0 / 72.0))))


class SettingsDialog:
    """高 DPI 自适应参数设置弹窗 (Fluent 风格)"""
    def __init__(
        self,
        parent,
        current_interval_ms: int,
        current_cleanup_enabled: bool,
        current_timeout_sec: int,
        current_auto_start: bool,
        on_save: Callable[[int, bool, int, bool], None]
    ):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("参数设置")
        self.dialog.configure(bg="#F3F3F3")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.on_save = on_save
        font_family = "Microsoft YaHei UI"

        f_title = (font_family, font_px(10), "bold")
        f_label = (font_family, font_px(9))
        f_hint = (font_family, font_px(8))
        f_btn_bold = (font_family, font_px(9), "bold")
        f_btn = (font_family, font_px(9))

        card = tk.Frame(
            self.dialog, bg="#FFFFFF",
            highlightbackground="#E5E5E5", highlightthickness=1,
            padx=s(20), pady=s(18)
        )
        card.pack(fill="both", expand=True, padx=s(16), pady=s(16))

        # 1. 扫描间隔 (毫秒)
        tk.Label(card, text="后台扫描间隔 (毫秒)", font=f_title, bg="#FFFFFF", fg="#1A1A1A").pack(anchor="w")

        interval_input_frame = tk.Frame(card, bg="#FFFFFF")
        interval_input_frame.pack(fill="x", pady=(s(6), s(2)))

        self.entry_interval = tk.Entry(
            interval_input_frame, font=f_label, bg="#FAFAFA", fg="#1A1A1A",
            relief="solid", bd=1, highlightthickness=0, width=8
        )
        self.entry_interval.insert(0, str(int(current_interval_ms)))
        self.entry_interval.pack(side="left", ipady=s(2))

        tk.Label(interval_input_frame, text="毫秒 (ms)", font=f_label, bg="#FFFFFF", fg="#333333").pack(side="left", padx=(s(8), 0))

        tk.Label(
            card, text="说明：1秒 = 1000毫秒。推荐设置 1000 ~ 5000 毫秒（最低 300 毫秒）",
            font=f_hint, bg="#FFFFFF", fg="#8C8C8C"
        ).pack(anchor="w", pady=(0, s(14)))

        # 2. 剪贴板自动清理设置
        tk.Label(card, text="剪贴板自动清理保护", font=f_title, bg="#FFFFFF", fg="#1A1A1A").pack(anchor="w")

        self.var_cleanup_enable = tk.BooleanVar(value=current_cleanup_enabled)
        chk_cleanup = tk.Checkbutton(
            card, text="启用剪贴板自动清理 (防敏感信息长期滞留)",
            variable=self.var_cleanup_enable, font=f_label,
            bg="#FFFFFF", fg="#1A1A1A", selectcolor="#FFFFFF", activebackground="#FFFFFF",
            cursor="hand2", command=self._toggle_cleanup_input
        )
        chk_cleanup.pack(anchor="w", pady=(s(4), s(4)))

        self.timeout_frame = tk.Frame(card, bg="#FFFFFF")
        self.timeout_frame.pack(fill="x", pady=(0, s(2)), padx=(s(24), 0))

        tk.Label(self.timeout_frame, text="复制后", font=f_label, bg="#FFFFFF", fg="#4A4A4A").pack(side="left")
        self.entry_timeout = tk.Entry(
            self.timeout_frame, font=f_label, bg="#FAFAFA", fg="#1A1A1A",
            relief="solid", bd=1, highlightthickness=0, width=6
        )
        self.entry_timeout.insert(0, str(int(current_timeout_sec)))
        self.entry_timeout.pack(side="left", padx=s(6), ipady=s(2))
        tk.Label(self.timeout_frame, text="秒自动清空 (Ctrl+V 粘贴后亦将延迟清空)", font=f_label, bg="#FFFFFF", fg="#4A4A4A").pack(side="left")

        self.lbl_cleanup_hint = tk.Label(
            card, text="若取消勾选，验证码将持续保留在剪贴板中，直到被新内容覆盖",
            font=f_hint, bg="#FFFFFF", fg="#8C8C8C"
        )
        self.lbl_cleanup_hint.pack(anchor="w", pady=(s(2), s(14)), padx=(s(24), 0))

        self._toggle_cleanup_input()

        # 3. 开机自启动设置
        tk.Label(card, text="系统自启动", font=f_title, bg="#FFFFFF", fg="#1A1A1A").pack(anchor="w")

        self.var_auto_start = tk.BooleanVar(value=current_auto_start)
        chk_autostart = tk.Checkbutton(
            card, text="开机自动启动 (开机后在后台静默常驻托盘)",
            variable=self.var_auto_start, font=f_label,
            bg="#FFFFFF", fg="#1A1A1A", selectcolor="#FFFFFF", activebackground="#FFFFFF",
            cursor="hand2"
        )
        chk_autostart.pack(anchor="w", pady=(s(4), s(2)))

        tk.Label(
            card, text="开启后将在 Windows 登录时自动启动并在后台静默常驻，不弹窗打扰",
            font=f_hint, bg="#FFFFFF", fg="#8C8C8C"
        ).pack(anchor="w", pady=(0, s(16)), padx=(s(24), 0))

        # 4. 底部操作按钮
        btn_box = tk.Frame(card, bg="#FFFFFF")
        btn_box.pack(fill="x", pady=(s(8), 0))

        save_btn = tk.Button(
            btn_box, text="保存设置 (Enter)", font=f_btn_bold,
            bg="#0078D4", fg="#FFFFFF", activebackground="#106EBE", activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=s(18), pady=s(6), cursor="hand2", command=self._save
        )
        save_btn.pack(side="right")

        cancel_btn = tk.Button(
            btn_box, text="取消 (Esc)", font=f_btn,
            bg="#F3F3F3", fg="#333333", activebackground="#E0E0E0",
            relief="flat", bd=0, padx=s(14), pady=s(6), cursor="hand2", command=self.dialog.destroy
        )
        cancel_btn.pack(side="right", padx=(0, s(8)))

        # 快捷键绑定
        self.dialog.bind("<Return>", lambda e: self._save())
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

        self.dialog.update_idletasks()
        req_w = max(s(400), self.dialog.winfo_reqwidth())
        req_h = self.dialog.winfo_reqheight()

        parent.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - req_w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - req_h) // 2
        self.dialog.geometry(f"{req_w}x{req_h}+{max(0, px)}+{max(0, py)}")
        self.dialog.resizable(False, False)

        try:
            hwnd = ctypes.windll.user32.GetAncestor(self.dialog.winfo_id(), 2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
            )
            caption_color = ctypes.c_int(0x00F3F3F3)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def _toggle_cleanup_input(self):
        if self.var_cleanup_enable.get():
            self.entry_timeout.configure(state="normal", bg="#FAFAFA", fg="#1A1A1A")
            self.lbl_cleanup_hint.configure(text="建议设置 30 ~ 120 秒，平衡便利性与安全性")
        else:
            self.entry_timeout.configure(state="disabled", bg="#EEEEEE", fg="#999999")
            self.lbl_cleanup_hint.configure(text="已禁用自动清理：验证码将持续保留在剪贴板中直到被覆盖")

    def _save(self):
        try:
            val_interval = int(self.entry_interval.get().strip())
            if val_interval < 300:
                messagebox.showwarning("提示", "后台扫描间隔过低可能会导致数据库访问冲突，系统已自动调整为最低 300 毫秒！", parent=self.dialog)
                val_interval = 300
        except ValueError:
            messagebox.showerror("错误", "扫描间隔必须为有效整数毫秒数值！", parent=self.dialog)
            return

        val_cleanup_enabled = self.var_cleanup_enable.get()
        val_timeout_sec = 60
        if val_cleanup_enabled:
            try:
                val_timeout_sec = int(self.entry_timeout.get().strip())
                if val_timeout_sec < 5:
                    val_timeout_sec = 5
            except ValueError:
                messagebox.showerror("错误", "超时清理时间必须为有效整数秒数！", parent=self.dialog)
                return

        val_auto_start = self.var_auto_start.get()
        self.on_save(val_interval, val_cleanup_enabled, val_timeout_sec, val_auto_start)
        self.dialog.destroy()


class MainWindow:
    """高 DPI 自适应 Windows 11 Fluent 主界面"""
    def __init__(
        self,
        on_toggle_pause: Callable[[], None],
        on_open_log: Callable[[], None],
        on_open_dir: Callable[[], None],
        on_save_settings: Callable[[int, bool, int, bool], None],
        get_status_snapshot: Callable[[], dict],
        on_request_exit: Callable[[], None],
        start_minimized: bool = False
    ):
        self.on_toggle_pause = on_toggle_pause
        self.on_open_log = on_open_log
        self.on_open_dir = on_open_dir
        self.on_save_settings = on_save_settings
        self.get_status_snapshot = get_status_snapshot
        self.on_request_exit = on_request_exit

        self._is_destroyed = False
        self._refresh_after_id = None

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.configure(bg="#F3F3F3")

        if os.path.exists(ICON_FILE):
            try:
                self.root.iconbitmap(ICON_FILE)
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self._build_ui()
        self._auto_size_and_center()
        self._apply_dwm_fluent_styles()
        self._schedule_refresh()

        if start_minimized:
            self.root.withdraw()

    def _build_ui(self):
        font_family = "Microsoft YaHei UI"

        f_app_title = (font_family, font_px(14), "bold")
        f_app_sub = (font_family, font_px(8))
        f_card_title = (font_family, font_px(10), "bold")
        f_label = (font_family, font_px(9))
        f_label_bold = (font_family, font_px(9), "bold")
        f_btn = (font_family, font_px(9))
        f_btn_toggle = (font_family, font_px(9), "bold")
        f_hint = (font_family, font_px(8))

        # 1. 顶部 Header 区域
        header_frame = tk.Frame(self.root, bg="#F3F3F3", padx=s(20), pady=s(14))
        header_frame.pack(fill="x")

        title_box = tk.Frame(header_frame, bg="#F3F3F3")
        title_box.pack(side="left")

        title_lbl = tk.Label(
            title_box, text=f"{APP_NAME} v{APP_VERSION}",
            font=f_app_title, bg="#F3F3F3", fg="#1A1A1A"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            title_box, text="Windows 11 手机连接短信验证码同步",
            font=f_app_sub, bg="#F3F3F3", fg="#6E6E6E"
        )
        subtitle_lbl.pack(anchor="w", pady=(s(2), 0))

        self.toggle_btn = tk.Button(
            header_frame, text="● 监控中", font=f_btn_toggle,
            bg="#E8F5E9", fg="#2E7D32", activebackground="#C8E6C9", activeforeground="#1B5E20",
            relief="flat", bd=0, padx=s(14), pady=s(6), cursor="hand2", command=self.on_toggle_pause
        )
        self.toggle_btn.pack(side="right")

        # 2. 卡片 1：系统运行状态 (Status Card)
        card1 = tk.Frame(
            self.root, bg="#FFFFFF",
            highlightbackground="#E5E5E5", highlightthickness=1,
            padx=s(16), pady=s(12)
        )
        card1.pack(fill="x", padx=s(20), pady=(0, s(10)))

        c1_title = tk.Label(card1, text="系统运行状态", font=f_card_title, bg="#FFFFFF", fg="#1A1A1A")
        c1_title.pack(anchor="w", pady=(0, s(8)))

        row1 = tk.Frame(card1, bg="#FFFFFF")
        row1.pack(fill="x", pady=s(3))
        tk.Label(row1, text="当前监控状态", font=f_label, bg="#FFFFFF", fg="#6E6E6E").pack(side="left")
        self.val_monitor_status = tk.Label(row1, text="● 正在监控短信", font=f_label_bold, bg="#FFFFFF", fg="#107C41")
        self.val_monitor_status.pack(side="right")

        row2 = tk.Frame(card1, bg="#FFFFFF")
        row2.pack(fill="x", pady=s(3))
        tk.Label(row2, text="数据库连接状态", font=f_label, bg="#FFFFFF", fg="#6E6E6E").pack(side="left")
        self.val_db_status = tk.Label(row2, text="● 已连接 (只读安全模式)", font=f_label_bold, bg="#FFFFFF", fg="#0078D4")
        self.val_db_status.pack(side="right")

        row3 = tk.Frame(card1, bg="#FFFFFF")
        row3.pack(fill="x", pady=s(3))
        tk.Label(row3, text="最近一次扫描时间", font=f_label, bg="#FFFFFF", fg="#6E6E6E").pack(side="left")
        self.val_scan_time = tk.Label(row3, text="正在初始化...", font=f_label, bg="#FFFFFF", fg="#333333")
        self.val_scan_time.pack(side="right")

        # 3. 卡片 2：验证码与剪贴板动态
        card2 = tk.Frame(
            self.root, bg="#FFFFFF",
            highlightbackground="#E5E5E5", highlightthickness=1,
            padx=s(16), pady=s(12)
        )
        card2.pack(fill="x", padx=s(20), pady=(0, s(10)))

        c2_title = tk.Label(card2, text="验证码与剪贴板动态", font=f_card_title, bg="#FFFFFF", fg="#1A1A1A")
        c2_title.pack(anchor="w", pady=(0, s(8)))

        row4 = tk.Frame(card2, bg="#FFFFFF")
        row4.pack(fill="x", pady=s(3))
        tk.Label(row4, text="最近识别状态", font=f_label, bg="#FFFFFF", fg="#6E6E6E").pack(side="left")
        self.val_recognition_status = tk.Label(row4, text="等待接收新短信...", font=f_label_bold, bg="#FFFFFF", fg="#6E6E6E")
        self.val_recognition_status.pack(side="right")

        self.cd_frame = tk.Frame(
            card2, bg="#F9F9F9", padx=s(10), pady=s(8),
            highlightbackground="#EBEBEB", highlightthickness=1
        )
        self.cd_frame.pack(fill="x", pady=(s(8), s(2)))

        self.cd_label = tk.Label(self.cd_frame, text="剪贴板当前处于空闲安全状态", font=f_label, bg="#F9F9F9", fg="#7A7A7A")
        self.cd_label.pack(anchor="center")

        # 4. 卡片 3：快捷控制与设置
        btn_box = tk.Frame(self.root, bg="#F3F3F3", padx=s(20))
        btn_box.pack(fill="x", pady=(0, s(10)))

        self.btn_log = tk.Button(
            btn_box, text="📄 查看运行日志", font=f_btn,
            bg="#FFFFFF", fg="#333333", activebackground="#F0F0F0",
            relief="flat", bd=0, padx=s(10), pady=s(8), highlightbackground="#E5E5E5", highlightthickness=1,
            cursor="hand2", command=self.on_open_log
        )
        self.btn_log.pack(side="left", expand=True, fill="x", padx=(0, s(4)))

        self.btn_settings = tk.Button(
            btn_box, text="⚙ 参数设置", font=f_btn,
            bg="#FFFFFF", fg="#333333", activebackground="#F0F0F0",
            relief="flat", bd=0, padx=s(10), pady=s(8), highlightbackground="#E5E5E5", highlightthickness=1,
            cursor="hand2", command=self._open_settings_dialog
        )
        self.btn_settings.pack(side="left", expand=True, fill="x", padx=(s(4), s(4)))

        self.btn_dir = tk.Button(
            btn_box, text="📁 程序目录", font=f_btn,
            bg="#FFFFFF", fg="#333333", activebackground="#F0F0F0",
            relief="flat", bd=0, padx=s(10), pady=s(8), highlightbackground="#E5E5E5", highlightthickness=1,
            cursor="hand2", command=self.on_open_dir
        )
        self.btn_dir.pack(side="left", expand=True, fill="x", padx=(s(4), 0))

        # 5. 底部帮助说明
        footer_frame = tk.Frame(self.root, bg="#F3F3F3", padx=s(20))
        footer_frame.pack(fill="x", side="bottom", pady=(0, s(12)))

        footer_lbl = tk.Label(
            footer_frame,
            text="提示：点击右上角关闭按钮将最小化隐藏至系统托盘，后台持续守护\n若需完全退出程序，请右键托盘图标选择「退出程序」",
            font=f_hint, bg="#F3F3F3", fg="#8C8C8C", justify="center"
        )
        footer_lbl.pack(anchor="center")

    def _auto_size_and_center(self):
        self.root.update_idletasks()
        target_w = max(s(440), self.root.winfo_reqwidth())
        target_h = self.root.winfo_reqheight() + s(10)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(0, (screen_w - target_w) // 2)
        pos_y = max(0, (screen_h - target_h) // 2)

        self.root.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self.root.minsize(target_w, target_h - s(30))
        self.root.resizable(True, True)

    def _apply_dwm_fluent_styles(self):
        try:
            hwnd = ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
            )
            caption_color = ctypes.c_int(0x00F3F3F3)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(ctypes.c_int)
            )
        except Exception as e:
            app_logger.warning(f"应用 Windows 11 DWM 样式警告: {e}")

    def _open_settings_dialog(self):
        snap = self.get_status_snapshot()
        SettingsDialog(
            self.root,
            current_interval_ms=snap.get("scan_interval_ms", 3000),
            current_cleanup_enabled=snap.get("cleanup_enabled", True),
            current_timeout_sec=snap.get("clipboard_timeout_sec", 60),
            current_auto_start=snap.get("auto_start", False),
            on_save=self.on_save_settings
        )

    def _schedule_refresh(self):
        if self._is_destroyed:
            return
        try:
            self.refresh_state()
        except Exception:
            pass
        if not self._is_destroyed:
            self._refresh_after_id = self.root.after(250, self._schedule_refresh)

    def refresh_state(self):
        if self._is_destroyed:
            return
        snap = self.get_status_snapshot()
        is_paused = snap.get("is_paused", False)
        db_ready = snap.get("db_ready", False)
        last_scan_time = snap.get("last_scan_time", "")
        last_status_msg = snap.get("last_status_msg", "等待接收新短信...")
        countdown = snap.get("countdown", 0)
        scan_interval_ms = snap.get("scan_interval_ms", 3000)
        cleanup_enabled = snap.get("cleanup_enabled", True)

        if is_paused:
            self.toggle_btn.configure(text="❚❚ 已暂停", bg="#FFEBEE", fg="#C62828")
            self.val_monitor_status.configure(text="❚❚ 监控已暂停", fg="#D32F2F")
        else:
            self.toggle_btn.configure(text="● 监控中", bg="#E8F5E9", fg="#2E7D32")
            self.val_monitor_status.configure(text="● 正在监控短信", fg="#107C41")

        if db_ready:
            self.val_db_status.configure(text="● 已连接 (只读安全模式)", fg="#0078D4")
        else:
            self.val_db_status.configure(text="○ 正在检测系统数据库...", fg="#E65100")

        if last_scan_time:
            self.val_scan_time.configure(text=f"{last_scan_time} (间隔 {scan_interval_ms}ms)", fg="#333333")
        else:
            self.val_scan_time.configure(text=f"等待首次扫描 (间隔 {scan_interval_ms}ms)", fg="#8C8C8C")

        if "成功" in last_status_msg or "已提取" in last_status_msg:
            self.val_recognition_status.configure(text=last_status_msg, fg="#0078D4")
        else:
            self.val_recognition_status.configure(text=last_status_msg, fg="#6E6E6E")

        if not cleanup_enabled:
            self.cd_frame.configure(bg="#F5F5F5", highlightbackground="#E0E0E0")
            self.cd_label.configure(
                text="🛡 剪贴板自动清理已禁用 (验证码将持续保留)",
                bg="#F5F5F5", fg="#616161", font=("Microsoft YaHei UI", font_px(9))
            )
        else:
            if countdown > 0:
                self.cd_frame.configure(bg="#F0F7FF", highlightbackground="#D0E3F8")
                self.cd_label.configure(
                    text=f"⏱ 剪贴板自动清理倒计时: {countdown} 秒 (Ctrl+V 粘贴后延迟清理)",
                    bg="#F0F7FF", fg="#0067B8", font=("Microsoft YaHei UI", font_px(9), "bold")
                )
            else:
                self.cd_frame.configure(bg="#F9F9F9", highlightbackground="#EBEBEB")
                self.cd_label.configure(
                    text="剪贴板当前处于空闲安全状态",
                    bg="#F9F9F9", fg="#7A7A7A", font=("Microsoft YaHei UI", font_px(9))
                )

    def show_window(self):
        if self._is_destroyed:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        if self._is_destroyed:
            return
        self.root.withdraw()

    def destroy_window(self):
        self._is_destroyed = True
        if self._refresh_after_id:
            try:
                self.root.after_cancel(self._refresh_after_id)
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
