import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal

# ==============================================================================
# 【终极防御】
# 拦截 PyInstaller --noconsole 模式下所有的空流，将它们重定向到系统黑洞
# 这能彻底解决所有隐式的 "NoneType object has no attribute write" 崩溃问题
# ==============================================================================
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
    new_log = Signal(str, str) # level_name, formatted_message

# 全局单例信号发射器
log_emitter = LogEmitter()

class QtUIHandler(logging.Handler):
    """将日志发送到 Qt UI 线程的自定义处理器"""
    def emit(self, record):
        msg = self.format(record)
        log_emitter.new_log.emit(record.levelname, msg)

def setup_logger():
    log_dir = "./Logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # 创建全局 logger
    app_logger = logging.getLogger("Sketchbook")
    app_logger.setLevel(logging.DEBUG)

    # 避免重复添加 Handler
    if not app_logger.handlers:
        # 1. 物理文件 Handler (最大5MB，保留3个备份，崩溃和结束时自动写入磁盘)
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        
        # 2. UI 界面 Handler (格式更精简，适合在界面查看)
        ui_handler = QtUIHandler()
        ui_handler.setLevel(logging.DEBUG)
        ui_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        ui_handler.setFormatter(ui_formatter)
        
        app_logger.addHandler(file_handler)
        app_logger.addHandler(ui_handler)

        # 3. 控制台 Handler (方便终端调试)
        # 添加控制台前做双重安全校验，确保流具有 write 方法
        safe_stream = sys.__stdout__ if hasattr(sys.__stdout__, 'write') else sys.stdout
        if safe_stream is not None and hasattr(safe_stream, 'write'):
            console_handler = logging.StreamHandler(safe_stream)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(ui_formatter)
            app_logger.addHandler(console_handler)

    # 关闭向 Root Logger 传播，避免第三方库日志引发多重打印
    app_logger.propagate = False

    return app_logger

# 实例化全局 logger 供其他模块 (如 config_mgr.py) import 引用
logger = setup_logger()