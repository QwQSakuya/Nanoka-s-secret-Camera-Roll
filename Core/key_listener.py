import keyboard
import time
import sys
import os
import signal
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QApplication

# 获取当前文件所在目录和父目录
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# 确保父目录在 sys.path 中，以便可以基于根目录进行导入
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# 直接明确使用大写的 Core 进行导入
try:
    from Core.clipboard_mgr import ClipboardManager
    from Core.image_generator import ImageGenerator
except ModuleNotFoundError:
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    from clipboard_mgr import ClipboardManager
    from image_generator import ImageGenerator

class ChatBoxController(QObject):
    """
    核心工作流控制器 (防弹重构版)
    负责桥接: 键盘监听 <-> 剪贴板管理 <-> 图像引擎
    """
    trigger_workflow = Signal(str)
    quit_app = Signal()

    def __init__(self, clipboard_mgr: ClipboardManager, image_generator: ImageGenerator):
        super().__init__()
        self.clipboard = clipboard_mgr
        self.image_generator = image_generator
        self.is_running = False
        self.registered_hotkeys = []
        
        self.trigger_workflow.connect(self._process_workflow, Qt.QueuedConnection)
        self.quit_app.connect(QApplication.instance().quit, Qt.QueuedConnection)

    def on_trigger(self, emote_name: str):
        self.trigger_workflow.emit(emote_name)
        
    def safe_quit(self):
        print("\n[系统] 收到退出指令，正在安全关闭...")
        self.quit_app.emit()

    def _safe_clear_clipboard(self):
        """带有重试机制的剪贴板清空 (状态隔离)"""
        cb = QApplication.clipboard()
        for _ in range(3):
            cb.clear()
            cb.setText("")  # 覆盖可能存在的格式化数据
            QApplication.processEvents()
            time.sleep(0.05)
            if not cb.mimeData().hasImage() and not cb.mimeData().hasText():
                return

    def _safe_set_image(self, img) -> bool:
        """带有防死锁重试机制的图片写入 (终结 COM Error 0x800401d0)"""
        cb = QApplication.clipboard()
        for attempt in range(5): # 最多重试 5 次
            self.clipboard.set_image(img)
            QApplication.processEvents()
            time.sleep(0.1)
            
            # 验证写入是否成功
            if cb.mimeData().hasImage():
                return True
                
            # 虽然 Qt 底层可能已经在终端打印了 C++ 级别的 COM 警告，但我们在这里成功拦截并重试
            print(f" -> [系统警告] 剪贴板正被其他程序锁定，正在重试写入 ({attempt + 1}/5)...")
            time.sleep(0.2) # 避让系统锁
        return False

    @Slot(str)
    def _process_workflow(self, emote_name: str):
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] 🚀 [开始] 触发表情: {emote_name}")
            
            # --- 阶段 1: 环境清理与状态备份 ---
            # 释放物理按键，防止与自动按键粘连引发错误 (如 Alt+Enter 变成换行)
            for key in ['alt', 'ctrl', 'shift', 'win']:
                keyboard.release(key)
            time.sleep(0.05)

            # 备份底层图片 (必须在任何剪贴板操作前进行)
            has_img = self.clipboard.check_and_backup_image()
            if has_img:
                print(f" -> [1/5] 📦 已备份底图，尺寸: {self.clipboard.get_cached_image().size}")
            else:
                print(" -> [1/5] 📦 剪贴板无底图，准备生成纯文本气泡。")

            # --- 阶段 2: 提取文本 ---
            # 清理系统剪贴板，防止上一轮的残留干扰
            self._safe_clear_clipboard()
            
            print(" -> [2/5] ✂️ 模拟全选与剪切 (Ctrl+A -> Ctrl+X)...")
            keyboard.send('ctrl+a')
            time.sleep(0.1) # 增加微小停顿，确保目标软件已全选
            keyboard.send('ctrl+x')
            
            # 【核心修复：主动轮询抓取文本】
            # 抛弃纯 sleep，引入 processEvents 强刷系统剪贴板状态，完美解决抓不到字的 Bug
            text = ""
            for _ in range(10): # 最多轮询等待 1 秒钟
                time.sleep(0.1)
                QApplication.processEvents() # 强制 Qt 更新底层系统事件！
                text = QApplication.clipboard().text().strip()
                if text:
                    break
            
            print(f" -> [3/5] 📝 提取到文字: '{text}'")

            # --- 阶段 3: 图像生成与写入 ---
            print(" -> [4/5] 🎨 图像引擎渲染中...")
            base_image = self.clipboard.get_cached_image()
            generated_image = self.image_generator.generate(base_image, text)
            
            # 安全写入剪贴板 (核心防弹区域)
            if self._safe_set_image(generated_image):
                print(" -> [4/5] ✅ 图片已稳妥写入剪贴板！")
            else:
                print(" -> [4/5] ❌ 写入剪贴板彻底失败，终止本次发送保护现场。")
                return # 放弃粘贴，避免把剪切的文字直接发出去

            # --- 阶段 4: 粘贴与发送 ---
            print(" -> [5/5] 🚀 正在粘贴与发送...")
            keyboard.send('ctrl+v')
            
            # 【动态等待策略】
            # 图片粘贴到聊天框需要被解码和渲染。底图越大，耗时越长。
            render_wait_time = 1.0 if has_img else 0.5
            time.sleep(render_wait_time)
            
            # 独立敲击回车，确保发送成功
            keyboard.press('enter')
            time.sleep(0.05)
            keyboard.release('enter')

            # --- 阶段 5: 现场清理 ---
            # 【修复点】发送完成后，立刻强制清空剪贴板的图片，防止污染下一次触发
            time.sleep(0.15) 
            self._safe_clear_clipboard()
            
            print(f"[{time.strftime('%H:%M:%S')}] ✨ [完成] 完美结束单次工作流！已打扫剪贴板现场。")
        except Exception as e:
            print(f"\n❌ [严重崩溃] 工作流遇到未捕获异常: {e}")
            import traceback
            traceback.print_exc()

    def start_listening(self):
        if self.is_running:
            return
        keyboard.add_hotkey('alt+1', self.on_trigger, args=('默认猫猫表情',), suppress=True)
        self.registered_hotkeys.append('alt+1')
        self.is_running = True
        print("✅ 监听服务已激活！请尝试在聊天框按下 [Alt + 1]。")

    def stop_listening(self):
        keyboard.unhook_all()
        self.registered_hotkeys.clear()
        self.is_running = False
        print("❌ 监听服务已关闭。")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) 
    
    mgr = ClipboardManager()
    generator = ImageGenerator()
    controller = ChatBoxController(mgr, generator)
    
    print("========================================")
    print("      🌟 全流程终极联合测试 🌟         ")
    print("========================================")
    print("请按以下步骤操作：")
    print("1. 随便复制一张图片 (当作表情底图)。")
    print("2. 打开微信/QQ聊天框，打一句骚话。")
    print("3. 按下快捷键 [Alt + 1] 见证奇迹！")
    print("----------------------------------------\n")
    
    try:
        controller.start_listening()
        keyboard.add_hotkey('esc', controller.safe_quit)
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop_listening()