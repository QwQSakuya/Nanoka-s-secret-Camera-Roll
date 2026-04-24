import keyboard
import time
import sys
import os
import signal
import ctypes
import psutil
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QApplication
from PIL import Image

# 统一路径规范，确保直接运行或被 main.py 调用时都能正确导入 Core 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Core.clipboard_mgr import ClipboardManager
from Core.image_generator import ImageGenerator

class ChatBoxController(QObject):
    """
    核心工作流控制器 (两步走：装填 -> 发射)
    负责桥接: 键盘监听 <-> HUD悬浮窗 <-> 剪贴板管理 <-> 图像引擎
    """
    arm_signal = Signal(dict)
    execute_signal = Signal()
    quit_signal = Signal()

    def __init__(self, clipboard_mgr: ClipboardManager, image_gen: ImageGenerator):
        super().__init__()
        self.clipboard_mgr = clipboard_mgr
        self.image_gen = image_gen
        
        self.is_running = False
        self.active_hotkeys = []  
        self.emotes_configs = []  
        self.global_settings = {}
        
        # 核心状态：当前已经装填完毕待发射的表情
        self.armed_emote_cfg = None 
        # UI 传进来的悬浮窗回调函数
        self.hud_callback = None    
        
        # 绑定信号槽，确保多线程跨越时在主 GUI 线程执行
        self.arm_signal.connect(self._arm_emote, Qt.QueuedConnection)
        self.execute_signal.connect(self._execute_workflow, Qt.QueuedConnection)
        self.quit_signal.connect(QApplication.instance().quit, Qt.QueuedConnection)

    # =============== 键盘 Hook 触发点 ===============
    def trigger_arm(self, emote_cfg):
        """按下具体表情的快捷键 -> 触发装填信号 (不受进程限制)"""
        self.arm_signal.emit(emote_cfg)
        
    def trigger_execute(self):
        """按下全局发送的快捷键 -> 触发执行合成信号"""
        # --- 进程焦点检测限制 ---
        if not self.is_target_app_active():
            print(f"[{time.strftime('%H:%M:%S')}] [DEBUG] 当前焦点不在白名单软件中，发射指令被忽略。")
            return
        # ------------------------
        self.execute_signal.emit()
        
    def quit(self):
        self.quit_signal.emit()

    # =============== 进程焦点辅助函数 ===============
    def is_target_app_active(self):
        """
        检查当前处于焦点的系统窗口是否属于指定的应用程序白名单
        """
        # 从全局设置中获取白名单
        raw_procs = self.global_settings.get("target_processes", [])
        
        # 处理可能的数据格式 (字符串或列表)
        if isinstance(raw_procs, str):
            target_list = [p.strip().lower() for p in raw_procs.split(",") if p.strip()]
        else:
            target_list = [str(p).strip().lower() for p in raw_procs if str(p).strip()]
            
        # 如果白名单为空，代表允许所有软件触发（对应主界面留空的逻辑）
        if not target_list:
            return True
            
        try:
            # 获取当前处于前台的活动窗口句柄
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return False
            
            # 获取该窗口对应的进程 PID
            pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            # 使用 psutil 获取进程名称并进行忽略大小写的比对
            process = psutil.Process(pid.value)
            active_process_name = process.name().lower()
            
            return active_process_name in target_list
        except Exception as e:
            # 捕获可能的进程访问权限不足或进程瞬时退出的情况
            return False

    # =============== 剪贴板辅助函数 ===============
    def _clear_clipboard(self):
        cb = QApplication.clipboard()
        for _ in range(3):
            cb.clear()
            cb.setText("") 
            QApplication.processEvents()
            if not cb.mimeData().hasImage() and not cb.mimeData().hasText(): return
            time.sleep(0.01)

    def _write_image_to_clipboard(self, img) -> bool:
        cb = QApplication.clipboard()
        for attempt in range(5):
            self.clipboard_mgr.set_image(img)
            for _ in range(5):
                QApplication.processEvents()
                if cb.mimeData().hasImage(): return True
                time.sleep(0.01)
            time.sleep(0.05)
        return False

    # =============== 核心逻辑执行 ===============
    @Slot(dict)
    def _arm_emote(self, emote_cfg: dict):
        """阶段 1：将表情配置装入内存，并呼出桌面悬浮窗提示"""
        self.armed_emote_cfg = emote_cfg
        emote_name = emote_cfg.get("name", "未知表情")
        
        print(f"[{time.strftime('%H:%M:%S')}] [INFO] 已装填表情 -> {emote_name}")
        
        if not self.hud_callback:
            print(f"[{time.strftime('%H:%M:%S')}] [WARN] 无法弹出悬浮窗: HUD 回调未绑定 (请检查主界面 start_listening 传参)")
            return

        if not self.global_settings.get("show_hud", True):
            print(f"[{time.strftime('%H:%M:%S')}] [DEBUG] 全局设置中关闭了悬浮窗显示，已跳过弹出。")
            return

        try:
            img_path = os.path.join(emote_cfg.get("_folder_path", ""), emote_cfg.get("base_image", "base.png"))
            self.hud_callback(emote_name, img_path)
            print(f"[{time.strftime('%H:%M:%S')}] [DEBUG] 悬浮窗弹窗指令已成功下发至 UI 层。")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [ERROR] 悬浮窗唤起时发生意外异常: {e}")

    @Slot()
    def _execute_workflow(self):
        """阶段 2：执行提取文字、生成图片并发送"""
        if not self.armed_emote_cfg:
            print(f"[{time.strftime('%H:%M:%S')}] [WARN] 尚未装填任何表情，请先按下表情对应的快捷键！")
            return
            
        workflow_start_time = time.perf_counter()
        emote_name = self.armed_emote_cfg.get("name")
        
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] [INFO] 当前表情: {emote_name} ")
            
            for key in ['alt', 'ctrl', 'shift', 'win', 'enter']:
                keyboard.release(key)
            time.sleep(0.01)

            has_base_img = self.clipboard_mgr.check_and_backup_image()

            self._clear_clipboard()
            
            keyboard.send('ctrl+a')
            time.sleep(0.04) 
            keyboard.send('ctrl+x')
            
            extracted_text = ""
            for i in range(50):
                QApplication.processEvents()
                extracted_text = QApplication.clipboard().text().strip()
                
                if extracted_text: 
                    break
                    
                if i == 25:
                    print(f"[{time.strftime('%H:%M:%S')}] [DEBUG] 尝试补发 Ctrl+X...")
                    keyboard.send('ctrl+x')
                    
                time.sleep(0.01)

            if not extracted_text and not has_base_img:
                print(f"[{time.strftime('%H:%M:%S')}] [INFO] 工作流中断 | 没有选中任何文本或底图")
                return

            # 5. 图像生成核心
            img_path = os.path.join(self.armed_emote_cfg.get("_folder_path", ""), self.armed_emote_cfg.get("base_image", "base.png"))
            if os.path.exists(img_path):
                base_image = Image.open(img_path).convert("RGB")
            else:
                base_image = Image.new('RGB', (400, 300), color=(40, 42, 54))
            
            # 【核心修改】：将事先复制的图片作为一个内联元素(类似超级Emoji)，丢给渲染引擎进行框内排版缩放
            copied_image = self.clipboard_mgr.get_cached_image()
            if copied_image:
                print(f"[{time.strftime('%H:%M:%S')}] [INFO] 检测到图片...")
                self.armed_emote_cfg["inline_image"] = copied_image
            else:
                self.armed_emote_cfg.pop("inline_image", None)
            
            # 统一生成：带有内联图片和文字的最终合成图
            final_image = self.image_gen.generate(base_image, extracted_text, config=self.armed_emote_cfg)

            # 转换成安全的 RGB 格式（如果是透明图层会填上白底，防止在微信复制变黑块）
            if final_image.mode == 'RGBA':
                bg = Image.new('RGB', final_image.size, (255, 255, 255))
                mask = final_image.split()[3] if len(final_image.split()) == 4 else None
                bg.paste(final_image, mask=mask)
                final_image = bg

            # 6. 一次性将完美的终极图片写入剪贴板并粘贴！
            if not self._write_image_to_clipboard(final_image):
                print(f"[{time.strftime('%H:%M:%S')}] [ERROR] 剪贴板重写失败")
                return 

            keyboard.send('ctrl+v')
            
            delay_ms = self.global_settings.get("delay_ms", 150)
            time.sleep(delay_ms / 1000.0)
            
            for _ in range (3):
                keyboard.send('enter')
                time.sleep(delay_ms / 1000.0)
                print(f"[{time.strftime('%H:%M:%S')}] [INFO] 尝试发送 {emote_name}")
            self._clear_clipboard()
            
            print(f"[{time.strftime('%H:%M:%S')}] [INFO] 成功发送 {emote_name}")

            for key in ['alt', 'ctrl', 'shift', 'win', 'enter']:
                keyboard.release(key)
            time.sleep(0.01)
            
        except Exception as e:
            print(f"\n[{time.strftime('%H:%M:%S')}] [ERROR] 致命异常: {e}")

    # =============== 生命周期管理 ===============
    def start_listening(self, emotes_configs=None, global_settings=None, hud_callback=None):
        if self.is_running:
            self.stop_listening()
            
        if emotes_configs is not None:
            self.emotes_configs = emotes_configs
        if global_settings is not None:
            self.global_settings = global_settings
        if hud_callback is not None:
            self.hud_callback = hud_callback
        
        is_block = self.global_settings.get("block_keys", True)
        
        for cfg in self.emotes_configs:
            hotkey = cfg.get("hotkey")
            if hotkey and cfg.get("is_enabled", True):
                try:
                    keyboard.add_hotkey(hotkey, self.trigger_arm, args=(cfg,), suppress=is_block)
                    self.active_hotkeys.append(hotkey)
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] [WARN] 快捷键 {hotkey} 使用失败: {e}")

        global_hk = self.global_settings.get("global_trigger_key", "alt+enter").lower()
        if global_hk:
            try:
                keyboard.add_hotkey(global_hk, self.trigger_execute, suppress=is_block)
                self.active_hotkeys.append(f"全局输出:{global_hk}")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] [WARN]  {global_hk} 注册失败: {e}")

        self.is_running = True
        print(f"[{time.strftime('%H:%M:%S')}] [INFO] 当前监控键位: {self.active_hotkeys}")

    def stop_listening(self):
        keyboard.unhook_all()
        self.active_hotkeys.clear()
        self.is_running = False
        print(f"[{time.strftime('%H:%M:%S')}] [INFO] exit")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    print("--- 两步走监听器独立测试 ---")
    cb_mgr = ClipboardManager()
    img_gen = ImageGenerator()
    controller = ChatBoxController(cb_mgr, img_gen)
    
    test_emotes = [
        {"name": "测试表情", "hotkey": "alt+1", "_folder_path": "", "is_enabled": True}
    ]
    test_globals = {"global_trigger_key": "alt+s", "block_keys": True, "show_hud": True}
    
    def mock_hud(name, path):
        print(f">>> [HUD 悬浮窗真实验证] 成功收到弹窗指令！当前已装备: {name}")

    controller.start_listening(test_emotes, test_globals, mock_hud)
    print("请按 Alt+1 装填，再按 Alt+S 执行发射测试。按 Ctrl+C 退出...")
    sys.exit(app.exec())