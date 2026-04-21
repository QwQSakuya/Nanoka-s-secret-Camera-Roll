import glob
import sys
import os
import signal
from PySide6.QtGui import QIcon
import ctypes
from PySide6.QtWidgets import QApplication
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
    if os.name == 'nt':
        # 告诉 Windows 这是一个独立的应用程序（字符串可以随便写，只要独一无二即可）
        myappid = 'NNKs.Camera.Roll'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    # 设置全局应用程序图标
    # 假设 app.ico 放在你代码的根目录（或者打包后和 exe 放一起）
    # 如果你之前在 config_mgr 里写了 get_root_dir()，可以直接复用那个函数来拼路径
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    
    # 如果你是使用之前教你的 get_root_dir() 方法解决的外部依赖，请使用下面这行：
    # icon_path = os.path.join(get_root_dir(), "app.ico")
    
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
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
    logger.info("正在挂载并启动后台热键和悬浮窗...")
    
    if controller and config_mgr:
            logger.info("正在自动挂载并启动后台热键监听系统...")
            
            # 1. 读取最新配置和表情包
            global_cfg = config_mgr.load_global_settings()
            all_emotes = config_mgr.load_all_emotes()
            
            # 2. 启动监听
            controller.start_listening(
                all_emotes, 
                global_cfg, 
                window.trigger_hud
            )
            
            default_name = "待命..."
            default_img = ""
            
            for emote in all_emotes:
                if emote.get("hotkey") == "alt+1" or "anan_normal" in emote.get("_folder_path", ""):
                    default_name = emote.get("name", "安安#正常#")
                    folder_path = emote.get("_folder_path", "")
                    png_files = glob.glob(os.path.join(folder_path, "*.png"))
                    if png_files:
                        default_img = png_files[0]
                    break
                    
            # 4. 如果配置允许，利用 window 暴露的接口触发悬浮窗显示
            if global_cfg.get("show_hud", True):
                logger.info(f"加载默认初始表情: {default_name}")
                window.trigger_hud(default_name, default_img)
        
    logger.info("✅ 引擎全部初始化完毕，现已处于待命状态！")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()