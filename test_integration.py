import os
import sys
import time

# 将当前目录加入 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from config import NOTIFICATION_DB_PATH, LAST_ID_FILE, LOG_FILE, ICON_FILE
from logger import app_logger, mask_code
from code_detector import CodeDetector
from notification_reader import NotificationReader, NotificationRecord
from clipboard_manager import ClipboardManager
from tray import SystemTray

print("1. Testing Configuration...")
print("  DB Path:", NOTIFICATION_DB_PATH)
print("  Icon File exists:", os.path.exists(ICON_FILE))
assert os.path.exists(ICON_FILE), "captcha.ico must exist!"

print("\n2. Testing SafeLogger & Masking...")
app_logger.info("Test log entry: Start integration test.")
assert mask_code("123456") == "12****"
assert mask_code("8523") == "85**"
assert mask_code("") == "****"
print("  Logger test passed.")

print("\n3. Testing NotificationReader...")
reader = NotificationReader()
init_ok = reader.initialize()
print("  Reader initialized:", init_ok)
print("  Base Last ID:", reader.last_id)
# Test reading notifications
records = reader.get_new_notifications()
print(f"  Got {len(records)} new notifications with ID > {reader.last_id}")

print("\n4. Testing CodeDetector on real payloads...")
raw_sample = '<toast hint-people="tel:106900000000"><visual><binding template="ToastGeneric"><text id="1">106900000000</text><text id="2">【服务平台】您的验证码是：654321，请于10分钟内填写完成验证。</text></binding></visual></toast>'.encode('utf-8')
rec = NotificationRecord(9999, "toast", raw_sample)
parsed_text = rec.parse_text()
print("  Parsed Text:", repr(parsed_text))
code = CodeDetector.extract_code(parsed_text)
print("  Extracted Code:", code)
assert code == "654321", f"Expected 654321, got {code}"
print("  Code detector test passed.")

print("\n5. Testing ClipboardManager...")
copied_result = []
def on_copied(c):
    copied_result.append(c)

mgr = ClipboardManager(timeout_seconds=1.0, paste_delay_seconds=0.3, on_copied_callback=on_copied)
mgr.copy_code("654987", 9999)
assert len(copied_result) == 1 and copied_result[0] == "654987"
assert mgr._safe_get_clipboard() == "654987"
print("  Waiting for 1.0s timeout cleanup...")
time.sleep(1.2)
assert mgr._safe_get_clipboard() == "", "Clipboard should be cleared after timeout"
mgr.stop_listener()
print("  ClipboardManager test passed.")

print("\n6. Testing Tray Menu Build...")
tray = SystemTray(
    on_show_ui=lambda: None,
    on_pause_callback=lambda: None,
    on_resume_callback=lambda: None,
    on_exit_callback=lambda: None,
    is_paused_check=lambda: False
)
menu = tray._build_menu()
assert menu is not None
print("  Tray menu successfully constructed.")

print("\n7. Testing Auto-start Registry Settings...")
from config import is_auto_start_enabled, set_auto_start
current_state = is_auto_start_enabled()
assert set_auto_start(True) is True
assert is_auto_start_enabled() is True
assert set_auto_start(False) is True
assert is_auto_start_enabled() is False
# restore
set_auto_start(current_state)
print("  Auto-start test passed.")

print("\nALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
