"""
验证码助手 - 日志模块
遵循隐私安全规范：严禁在日志中记录完整短信内容或明文验证码
使用 RotatingFileHandler 防止日志文件无限膨胀
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from config import LOG_FILE, MAX_LOG_SIZE_BYTES, LOG_BACKUP_COUNT

def mask_code(code: str) -> str:
    """
    对验证码进行脱敏脱除明文，仅保留前两位作为审计参考。
    例如: 123456 -> 12****, 8523 -> 85**
    """
    if not code:
        return "****"
    if len(code) <= 2:
        return "*" * len(code)
    return code[:2] + "*" * (len(code) - 2)

class SafeLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SafeLogger, cls).__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        self.logger = logging.getLogger("CaptchaAssistant")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # 清除已有的 handlers 防止重复
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 格式化器
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        try:
            # 循环轮转文件日志 Handler (UTF-8)
            file_handler = RotatingFileHandler(
                filename=LOG_FILE,
                maxBytes=MAX_LOG_SIZE_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            # 如果文件句柄失败，打印到 stderr 作为保底
            print(f"Failed to initialize file logger: {e}")

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str, exc_info=False):
        self.logger.error(message, exc_info=exc_info)

# 导出单例实例
app_logger = SafeLogger()
