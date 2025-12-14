import os
import sys
import datetime
from loguru import logger as _loguru_logger


class DailyLoguruFileHandler:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.current_date = None
        self.log_file = None
        self._update_log_file()

    def _get_log_file_path(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{today}.log")

    def _update_log_file(self):
        today = datetime.datetime.now().date()
        if today != self.current_date:
            self.current_date = today
            log_file_path = self._get_log_file_path()
            self.log_file = log_file_path

    def get_log_file(self):
        self._update_log_file()
        return self.log_file


class Logings:
    __instance = None

    def __init__(self):
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 获取项目根目录
        project_dir = os.path.dirname(current_dir)
        # 创建logs目录
        self.logpath = os.path.join(project_dir, "logs")
        if not os.path.exists(self.logpath):
            os.makedirs(self.logpath)

        # 日志文件处理器
        self.file_handler = DailyLoguruFileHandler(self.logpath)

        _loguru_logger.remove()

        def file_sink(message):
            # message 是 Loguru 的 Message 对象/字符串，统一转换为字符串
            try:
                formatted = str(message)
            except Exception:
                formatted = repr(message)

            log_file = self.file_handler.get_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")

        # 添加文件输出
        _loguru_logger.add(
            file_sink,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

        # 控制台输出 (不带颜色，避免Windows多进程重载问题)
        _loguru_logger.add(
            sys.stdout,
            colorize=False,
            format="{time:HH:mm:ss} | {level: <8} | {message}",
        )

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super(Logings, cls).__new__(cls, *args, **kwargs)
        return cls.__instance

    def info(self, msg, *args, **kwargs):
        return _loguru_logger.info(msg, *args, **kwargs)

    def success(self, msg, *args, **kwargs):
        return _loguru_logger.success(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        return _loguru_logger.debug(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        return _loguru_logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        return _loguru_logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        return _loguru_logger.exception(msg, *args, exc_info=True, **kwargs)


# 导出单例 logger，保持与现有代码兼容性（调用 logger.info 等）
logger = Logings()

__all__ = ["logger"]
