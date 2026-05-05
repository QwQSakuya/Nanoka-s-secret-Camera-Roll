import glob
import sys
import os
import signal
from PySide6.QtGui import QIcon
import ctypes
from PySide6.QtWidgets import QApplication
from Core.logger import logger
from Core.clipboard_mgr import ClipboardManager
from Core.image_generator import ImageGenerator
from Core.key_listener import ChatBoxController
from Core.config_mgr import ConfigManager
from Ui.main_window import MainWindow


def main():
    # 恢复终端对 Ctrl+C 的响应
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    if os.name == 'nt':
        # 向 Windows 注册独立应用身份，防止任务栏图标归组到 Python 解释器
        myappid = 'NNKs.Camera.Roll'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    app.setQuitOnLastWindowClosed(False)
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

    logger.info("正在挂载并启动后台热键和悬浮窗...")
    
    if controller and config_mgr:
            logger.info("正在自动挂载并启动后台热键监听系统...")
            
            global_cfg = config_mgr.load_global_settings()
            all_emotes = config_mgr.load_all_emotes()
            
            controller.start_listening(
                all_emotes, 
                global_cfg, 
                window.trigger_hud
            )
            
            default_name = "待命..."
            default_img = ""
            
            for emote in all_emotes:
                folder_path = emote.get("_folder_path", "") if isinstance(emote, dict) else ""
                if emote.get("hotkey") == "alt+1" or "anan_normal" in folder_path:
                    default_name = emote.get("name", "安安#正常#")
                    folder_path = emote.get("_folder_path", "")
                    png_files = glob.glob(os.path.join(folder_path, "*.png"))
                    if png_files:
                        default_img = png_files[0]
                    break
                    
            if global_cfg.get("show_hud", True):
                logger.info(f"加载默认初始表情: {default_name}")
                window.trigger_hud(default_name, default_img)
        
    logger.info("引擎全部初始化完毕，现已处于待命状态")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()