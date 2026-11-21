"""
验证码助手 - 全局配置模块
管理运行路径、系统常量、用户持久化设置与 Windows 开机自启管理
"""
import os
import sys
import json
import winreg

APP_NAME = "验证码助手"
APP_VERSION = "1.3.0"
AUTORUN_KEY_NAME = "CaptchaAssistant"
AUTORUN_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_writable_app_dir() -> str:
    """获取可写主目录，若 EXE 位于受限目录自动降级至 %LOCALAPPDATA%\\CaptchaAssistant"""
    if getattr(sys, 'frozen', False):
        candidate = os.path.dirname(os.path.abspath(sys.executable))
    else:
        candidate = os.path.dirname(os.path.abspath(__file__))

    test_file = os.path.join(candidate, ".perm_test")
    try:
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return candidate
    except Exception:
        local_app = os.environ.get('LOCALAPPDATA', '')
        if not local_app:
            local_app = os.path.expanduser('~')
        fallback = os.path.join(local_app, "CaptchaAssistant")
        os.makedirs(fallback, exist_ok=True)
        return fallback

def get_resource_path(relative_path: str) -> str:
    """获取只读静态资源路径（支持 PyInstaller _MEIPASS 与本地覆盖）"""
    app_dir = get_writable_app_dir()
    local_path = os.path.join(app_dir, relative_path)
    if os.path.exists(local_path):
        return local_path

    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        bundle_path = os.path.join(meipass, relative_path)
        if os.path.exists(bundle_path):
            return bundle_path

    return local_path

APP_DIR = get_writable_app_dir()
LAST_ID_FILE = os.path.join(APP_DIR, "last_id.txt")
LOG_FILE = os.path.join(APP_DIR, "app.log")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
ICON_FILE = get_resource_path("captcha.ico")

def get_notification_db_path() -> str:
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if not local_app_data:
        user_profile = os.environ.get('USERPROFILE', '')
        local_app_data = os.path.join(user_profile, 'AppData', 'Local')
    return os.path.join(local_app_data, 'Microsoft', 'Windows', 'Notifications', 'wpndatabase.db')

NOTIFICATION_DB_PATH = get_notification_db_path()

DEFAULT_SETTINGS = {
    "scan_interval_ms": 3000,
    "enable_clipboard_cleanup": True,
    "clipboard_timeout_sec": 60,
    "auto_start": False,
}

def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "scan_interval" in data and "scan_interval_ms" not in data:
                        settings["scan_interval_ms"] = int(data["scan_interval"] * 1000)
                    if "clipboard_timeout" in data and "clipboard_timeout_sec" not in data:
                        settings["clipboard_timeout_sec"] = int(data["clipboard_timeout"])
                    settings.update(data)
        except Exception:
            pass
    # 结合注册表状态进行双重校验
    settings["auto_start"] = is_auto_start_enabled()
    return settings

def save_settings(new_settings: dict):
    try:
        temp_file = f"{SETTINGS_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=2, ensure_ascii=False)
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
        os.rename(temp_file, SETTINGS_FILE)
    except Exception:
        pass

# ── 开机自启管理接口 (基于 HKCU 注册表，无需管理员权限) ──

def is_auto_start_enabled() -> bool:
    """查询当前是否已设置开机自启动"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_REG_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, AUTORUN_KEY_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception:
        return False

def set_auto_start(enabled: bool) -> bool:
    """开启或关闭开机自启（开机时附加 --minimized 参数，静默启动至托盘）"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_REG_PATH, 0, winreg.KEY_ALL_ACCESS) as key:
            if enabled:
                if getattr(sys, 'frozen', False):
                    target_path = os.path.abspath(sys.executable)
                    cmd = f'"{target_path}" --minimized'
                else:
                    python_exe = sys.executable
                    script_path = os.path.abspath(sys.argv[0])
                    cmd = f'"{python_exe}" "{script_path}" --minimized'
                winreg.SetValueEx(key, AUTORUN_KEY_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, AUTORUN_KEY_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        return False

NOTIFICATION_SCAN_LIMIT = 50
PASTE_CLEANUP_DELAY_SECONDS = 2.0
MAX_LOG_SIZE_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3
