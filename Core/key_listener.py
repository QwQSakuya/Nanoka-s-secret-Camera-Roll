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
from Core.logger import logger

class ChatBoxController(QObject):
    """键盘监听 → HUD → 剪贴板 → 图像引擎 工作流控制器"""
    arm_signal = Signal(dict)
    execute_signal = Signal()
    quit_signal = Signal()
    quick_search_signal = Signal()

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
        # 快速搜索回调函数
        self.quick_search_callback = None
        
        # Ctrl+A 触发快速搜索的防抖状态
        self._last_ctrl_a_time = 0
        self._ctrl_a_trigger_enabled = False

        # 绑定信号槽，确保多线程跨越时在主 GUI 线程执行
        self.arm_signal.connect(self._arm_emote, Qt.QueuedConnection)
        self.execute_signal.connect(self._execute_workflow, Qt.QueuedConnection)
        self.quit_signal.connect(QApplication.instance().quit, Qt.QueuedConnection)
        self.quick_search_signal.connect(self._on_quick_search_triggered, Qt.QueuedConnection)

    def trigger_arm(self, emote_cfg):
        """按下具体表情的快捷键，触发装填信号"""
        self.arm_signal.emit(emote_cfg)

    def trigger_execute(self):
        """按下全局发送的快捷键，触发合成信号"""
        if not self.is_target_app_active():
            logger.debug("当前焦点不在白名单软件中，发射指令被忽略。")
            return
        self.execute_signal.emit()

    def trigger_quick_search(self):
        """按下快速搜索快捷键，触发快速搜索信号"""
        self.quick_search_signal.emit()

    def _on_ctrl_a_pressed(self):
        """Ctrl+A 全选快捷键处理 —— 仅在白名单应用中触发快速搜索"""
        if not self._ctrl_a_trigger_enabled:
            return
        
        if not self.is_target_app_active():
            logger.debug("[快速搜索] Ctrl+A 已按下，但当前不在白名单应用中，跳过")
            return
        
        current_time = time.time()
        if current_time - self._last_ctrl_a_time < 0.5:
            return
        self._last_ctrl_a_time = current_time
        
        logger.info("[快速搜索] Ctrl+A 在白名单应用中触发，准备弹出搜索面板")
        self.trigger_quick_search()

    @Slot()
    def _on_quick_search_triggered(self):
        """在主 GUI 线程执行快速搜索回调"""
        if self.quick_search_callback:
            try:
                self.quick_search_callback()
            except Exception:
                logger.exception("[快速搜索] 回调执行异常")

    def quit(self):
        self.quit_signal.emit()

    def is_target_app_active(self):
        """检查当前焦点窗口是否属于指定的应用程序白名单"""
        raw_procs = self.global_settings.get("target_processes", []) if self.global_settings else []

        if isinstance(raw_procs, str):
            target_list = [p.strip().lower() for p in raw_procs.split(",") if p.strip()]
        else:
            target_list = [str(p).strip().lower() for p in raw_procs if str(p).strip()]

        if not target_list:
            return True

        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                logger.debug("无法获取前景窗口句柄")
                return False

            pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            try:
                process = psutil.Process(pid.value)
                active_process_name = process.name().lower()
                logger.debug(f"前台进程: {active_process_name}, 白名单: {target_list}")
                return active_process_name in target_list
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"无法获取进程信息 (PID={pid.value}): {e}")
                return False
        except Exception:
            logger.exception("进程焦点检测时发生意外异常")
            return False

    def _clear_clipboard(self):
        ClipboardManager.robust_clear()

    def _write_image_to_clipboard(self, img) -> bool:
        cb = QApplication.clipboard()
        for attempt in range(5):
            self.clipboard_mgr.set_image(img)
            for _ in range(5):
                QApplication.processEvents()
                if cb.mimeData().hasImage():
                    return True
                time.sleep(0.01)
            time.sleep(0.05)
        logger.error("剪贴板图片写入失败：经过5轮重试仍未成功")
        return False

    def _extract_text_from_input(self):
        """模拟 Ctrl+A, Ctrl+X 从当前输入框提取文字"""
        self._clear_clipboard()
        time.sleep(0.05)
        keyboard.send('ctrl+a')
        time.sleep(0.04)
        keyboard.send('ctrl+x')

        extracted_text = ""
        for i in range(50):
            QApplication.processEvents()
            extracted_text = QApplication.clipboard().text().strip()
            if extracted_text:
                logger.debug(f"成功提取文字 ({len(extracted_text)} 字符)")
                break
            if i == 25:
                logger.debug("尝试补发 Ctrl+X...")
                keyboard.send('ctrl+x')
            time.sleep(0.01)

        return extracted_text

    def _compose_and_send(self, extracted_text: str, has_base_img: bool):
        """合成图像，写入剪贴板并粘贴发送"""
        emote_name = self.armed_emote_cfg.get("name", "未知")
        logger.info(f"开始合成图像 | 表情: {emote_name} | 文字长度: {len(extracted_text)}")

        img_path = os.path.join(
            self.armed_emote_cfg.get("_folder_path", ""),
            self.armed_emote_cfg.get("base_image", "base.png")
        )
        if os.path.exists(img_path):
            base_image = Image.open(img_path).convert("RGB")
            logger.debug(f"底图加载成功: {img_path} ({base_image.size})")
        else:
            base_image = Image.new('RGB', (400, 300), color=(40, 42, 54))
            logger.warning(f"底图未找到，使用默认背景: {img_path}")

        copied_image = self.clipboard_mgr.get_cached_image()
        if copied_image:
            logger.info("检测到剪贴板缓存图片，已作为内联元素加入合成")
            self.armed_emote_cfg["inline_image"] = copied_image
        else:
            self.armed_emote_cfg.pop("inline_image", None)

        final_image = self.image_gen.generate(
            base_image, extracted_text, config=self.armed_emote_cfg
        )

        if final_image.mode == 'RGBA':
            bg = Image.new('RGB', final_image.size, (255, 255, 255))
            mask = final_image.split()[3] if len(final_image.split()) == 4 else None
            bg.paste(final_image, mask=mask)
            final_image = bg

        if not self._write_image_to_clipboard(final_image):
            logger.error("剪贴板写入失败，发送流程中断")
            return False

        keyboard.send('ctrl+v')
        logger.info("图片已粘贴到输入框")

        delay_ms = 150
        if self.global_settings:
            delay_ms = self.global_settings.get("delay_ms", 150)

        time.sleep(delay_ms / 1000.0)

        for _ in range(3):
            keyboard.send('enter')
            time.sleep(delay_ms / 1000.0)
        logger.info(f"✓ 成功发送: {emote_name}")

        return True

    @Slot(dict)
    def _arm_emote(self, emote_cfg: dict):
        """将表情配置装入内存，并呼出悬浮窗提示"""
        self.armed_emote_cfg = emote_cfg
        emote_name = emote_cfg.get("name", "未知表情")

        logger.info(f"已装填表情 -> {emote_name}")

        if not self.hud_callback:
            logger.warning("无法弹出悬浮窗: HUD 回调未绑定 (请检查主界面 start_listening 传参)")
            return

        if not self.global_settings.get("show_hud", True):
            logger.debug("全局设置中关闭了悬浮窗显示，已跳过弹出。")
            return

        try:
            img_path = os.path.join(
                emote_cfg.get("_folder_path", ""),
                emote_cfg.get("base_image", "base.png")
            )
            self.hud_callback(emote_name, img_path)
            logger.debug("悬浮窗弹窗指令已成功下发至 UI 层。")
        except Exception:
            logger.exception("悬浮窗唤起时发生意外异常")

    @Slot()
    def _execute_workflow(self):
        """提取文字、生成图片并发送"""
        if not self.armed_emote_cfg:
            logger.warning("尚未装填任何表情，请先按下表情对应的快捷键！")
            return

        workflow_start_time = time.perf_counter()
        emote_name = self.armed_emote_cfg.get("name", "未知")

        try:
            logger.info(f"开始执行工作流 | 当前表情: {emote_name}")

            for key in ['alt', 'ctrl', 'shift', 'win', 'enter']:
                keyboard.release(key)
            time.sleep(0.01)

            has_base_img = self.clipboard_mgr.check_and_backup_image()
            if has_base_img:
                logger.debug("已备份剪贴板中的图片")

            extracted_text = self._extract_text_from_input()

            if not extracted_text and not has_base_img:
                logger.info("工作流中断 | 没有选中任何文本且无底图")
                return

            success = self._compose_and_send(extracted_text, has_base_img)

            if success:
                elapsed = time.perf_counter() - workflow_start_time
                logger.debug(f"工作流完成 | 耗时: {elapsed:.2f}s")

            self._clear_clipboard()

            for key in ['alt', 'ctrl', 'shift', 'win', 'enter']:
                keyboard.release(key)
            time.sleep(0.01)

        except Exception:
            logger.exception("工作流执行时发生致命异常")

    def start_listening(self, emotes_configs=None, global_settings=None, hud_callback=None, quick_search_callback=None):
        if self.is_running:
            self.stop_listening()

        if emotes_configs is not None:
            self.emotes_configs = emotes_configs
        if global_settings is not None:
            self.global_settings = global_settings
        if hud_callback is not None:
            self.hud_callback = hud_callback
        if quick_search_callback is not None:
            self.quick_search_callback = quick_search_callback

        is_block = self.global_settings.get("block_keys", True) if self.global_settings else True

        for cfg in self.emotes_configs:
            hotkey = cfg.get("hotkey")
            if hotkey and cfg.get("is_enabled", True):
                try:
                    keyboard.add_hotkey(
                        hotkey, self.trigger_arm, args=(cfg,), suppress=is_block
                    )
                    self.active_hotkeys.append(hotkey)
                    logger.debug(f"注册表情快捷键: {hotkey} ({cfg.get('name', '?')})")
                except Exception:
                    logger.exception(f"快捷键注册失败: {hotkey}")

        global_hk = (self.global_settings or {}).get("global_trigger_key", "alt+enter").lower()
        if global_hk:
            try:
                keyboard.add_hotkey(
                    global_hk, self.trigger_execute, suppress=is_block
                )
                self.active_hotkeys.append(f"全局输出:{global_hk}")
                logger.info(f"注册全局发送快捷键: {global_hk}")
            except Exception:
                logger.exception(f"全局快捷键注册失败: {global_hk}")

        # 注册快速搜索快捷键 (默认 alt+/)
        qs_hk = (self.global_settings or {}).get("quick_search_hotkey", "alt+/").lower()
        if qs_hk:
            try:
                keyboard.add_hotkey(
                    qs_hk, self.trigger_quick_search, suppress=is_block
                )
                self.active_hotkeys.append(f"快速搜索:{qs_hk}")
                logger.info(f"注册快速搜索快捷键: {qs_hk}")
            except Exception:
                logger.exception(f"快速搜索快捷键注册失败: {qs_hk}")

        # 注册 Ctrl+A 全选快捷键触发快速搜索 (仅在白名单应用中生效)
        self._ctrl_a_trigger_enabled = self.global_settings.get("ctrl_a_trigger_quick_search", True)
        if self._ctrl_a_trigger_enabled:
            try:
                keyboard.add_hotkey(
                    "ctrl+a", self._on_ctrl_a_pressed, suppress=False
                )
                self.active_hotkeys.append("快速搜索:ctrl+a")
                logger.info("[快速搜索] 已注册 Ctrl+A 触发 (仅白名单应用生效)")
            except Exception:
                logger.exception("[快速搜索] Ctrl+A 注册失败")

        # 打印当前白名单
        raw_procs = self.global_settings.get("target_processes", []) if self.global_settings else []
        if raw_procs:
            if isinstance(raw_procs, str):
                target_list = [p.strip() for p in raw_procs.split(",") if p.strip()]
            else:
                target_list = [str(p).strip() for p in raw_procs if str(p).strip()]
            logger.info(f"[快速搜索] 当前白名单应用: {target_list}")
        else:
            logger.info("[快速搜索] 未设置白名单，Ctrl+A 将在所有应用中触发快速搜索")

        self.is_running = True
        logger.info(f"后台监听已启动 | 监控键位: {self.active_hotkeys}")

    def stop_listening(self):
        keyboard.unhook_all()
        self.active_hotkeys.clear()
        self.is_running = False
        logger.info("后台监听已停止")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    logger.info("--- 两步走监听器独立测试 ---")
    cb_mgr = ClipboardManager()
    img_gen = ImageGenerator()
    controller = ChatBoxController(cb_mgr, img_gen)

    test_emotes = [
        {"name": "测试表情", "hotkey": "alt+1", "_folder_path": "", "is_enabled": True}
    ]
    test_globals = {
        "global_trigger_key": "alt+s",
        "block_keys": True,
        "show_hud": True,
        "quick_search_hotkey": "alt+/",
        "ctrl_a_trigger_quick_search": True
    }

    def mock_hud(name, path):
        logger.info(f">>> [HUD 悬浮窗真实验证] 成功收到弹窗指令！当前已装备: {name}")

    def mock_quick_search():
        logger.info(">>> [快速搜索真实验证] 快捷搜索信号已触发！")

    controller.start_listening(test_emotes, test_globals, mock_hud, mock_quick_search)
    logger.info("请按 Alt+1 装填，Alt+S 发射，Alt+/ 或 Ctrl+A(白名单) 测试快速搜索。按 Ctrl+C 退出...")
    sys.exit(app.exec())