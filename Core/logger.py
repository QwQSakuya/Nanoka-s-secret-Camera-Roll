import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal

# 防御 PyInstaller noconsole 模式下 stdout/stderr 为 None 导致崩溃
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if getattr(sys, '__stdout__', None) is None:
    sys.__stdout__ = sys.stdout
if getattr(sys, '__stderr__', None) is None:
    sys.__stderr__ = sys.stderr


class LogEmitter(QObject):
    """用于跨线程向 UI 传递日志数据的信号发射器"""
    new_log = Signal(str, str)  # level_name, formatted_message


_log_emitter = None


def _get_log_emitter():
    global _log_emitter
    if _log_emitter is None:
        _log_emitter = LogEmitter()
    return _log_emitter


class QtUIHandler(logging.Handler):
    """将日志发送到 Qt UI 线程的自定义处理器"""
    def emit(self, record):
        msg = self.format(record)
        _get_log_emitter().new_log.emit(record.levelname, msg)


# 全局 logger 实例 (惰性初始化)
_logger_instance = None


def _build_logger():
    log_dir = "./Logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    app_logger = logging.getLogger("Sketchbook")
    app_logger.setLevel(logging.DEBUG)

    # 避免重复添加 Handler
    if not app_logger.handlers:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        ui_handler = QtUIHandler()
        ui_handler.setLevel(logging.DEBUG)
        ui_formatter = logging.Formatter(
            '[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%H:%M:%S'
        )
        ui_handler.setFormatter(ui_formatter)

        app_logger.addHandler(file_handler)
        app_logger.addHandler(ui_handler)

        safe_stream = sys.__stdout__ if hasattr(sys.__stdout__, 'write') else sys.stdout
        if safe_stream is not None and hasattr(safe_stream, 'write'):
            console_handler = logging.StreamHandler(safe_stream)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(ui_formatter)
            app_logger.addHandler(console_handler)

    app_logger.propagate = False

    return app_logger


def get_logger():
    """惰性获取全局唯一的 logger 实例"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = _build_logger()
    return _logger_instance


def set_log_level(level):
    """
    运行时动态调整日志级别。
    参数可以是字符串 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    或 logging 模块常量 (如 logging.INFO)。
    """
    log = get_logger()
    log.setLevel(level)
    for handler in log.handlers:
        handler.setLevel(level)


class _LoggerProxy:
    """惰性代理，使 ``from Core.logger import logger`` 返回 get_logger() 实例"""
    def __getattr__(self, name):
        return getattr(get_logger(), name)

    def __repr__(self):
        return repr(get_logger())


logger = _LoggerProxy()
