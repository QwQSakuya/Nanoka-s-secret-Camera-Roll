import sys
import os
import signal
from PySide6.QtWidgets import QApplication

# 确保能正确导入项目根目录下的 Core 和 Ui 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 尽早导入 logger，以确保异常拦截器第一时间生效
from Core.logger import logger 
from Core.clipboard_mgr import ClipboardManager
from Core.image_generator import ImageGenerator
from Core.key_listener import ChatBoxController
from Core.config_mgr import ConfigManager
from Ui.main_window import MainWindow

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
    
def main():
    # 恢复终端对 Ctrl+C 的响应
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    
    # 允许主窗口关闭后，后台引擎继续挂载在托盘运行
    app.setQuitOnLastWindowClosed(False) 
    
    # 全局去除所有控件被选中时的虚线框 (Focus Outline)
    app.setStyleSheet("* { outline: none; }")

    logger.info("正在初始化底层引擎组件...")
    clip_mgr = ClipboardManager()
    img_gen = ImageGenerator()
    controller = ChatBoxController(clip_mgr, img_gen)
    
    logger.info("正在加载配置管理器...")
    config_mgr = ConfigManager()
    config_mgr.load_global_settings()
    config_mgr.load_all_emotes()

    logger.info("正在启动UI 主界面...")
    window = MainWindow(config_mgr=config_mgr, controller=controller)
    window.show()

    # ==============================================================
    # 新增：在此处统一调度，完成所有组件加载后自动启动后台系统
    # ==============================================================
    logger.info("正在挂载并启动后台热键监听系统...")
    
    # 从 window 实例中动态获取悬浮窗回调函数
    hud_callback = getattr(window, 'show_floating_hud', None) 
    if not hud_callback:
        hud_callback = getattr(window, 'show_hud', lambda n, p: None)
        
    controller.start_listening(
        config_mgr.emotes_configs, 
        config_mgr.global_settings, 
        hud_callback
    )
    logger.info("✅ 引擎全部初始化完毕，现已处于待命状态！")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()