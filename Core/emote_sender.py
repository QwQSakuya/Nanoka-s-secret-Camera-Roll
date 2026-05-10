import os
import time
import ctypes
from ctypes import wintypes
import keyboard
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from Core.logger import logger


IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'}
ALL_EXTS = IMAGE_EXTS | {'.gif', '.mp4', '.webm', '.mp3', '.wav', '.ogg', '.avi', '.mov'}

# TODO: 未来设置项 — 用户可选择 GIF 是否以首帧静图发送
_SEND_GIF_AS_STATIC = False

# ── Windows CF_HDROP 常量 ──
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040

_DROPFILES_SIZE = ctypes.sizeof(wintypes.DWORD) * 5  # pFiles + pt + fNC + fWide = 20 bytes


def _copy_file_via_cf_hdrop(file_path: str) -> bool:
    """
    使用 Windows 原生 CF_HDROP 格式将文件写入剪贴板。
    这是 QQ/微信等软件能正确识别「文件拖放粘贴」的唯一方式。
    """
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    file_path_w = file_path + '\0'

    # 计算所需内存大小
    dropfiles_size = _DROPFILES_SIZE
    filename_size = len(file_path_w) * ctypes.sizeof(wintypes.WCHAR)
    total_size = dropfiles_size + filename_size + ctypes.sizeof(wintypes.WCHAR)  # 末尾额外 \0

    # 分配全局内存
    h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, total_size)
    if not h_global:
        logger.error("[EmoteSender] GlobalAlloc 失败")
        return False

    try:
        p_global = kernel32.GlobalLock(h_global)
        if not p_global:
            logger.error("[EmoteSender] GlobalLock 失败")
            return False

        try:
            # 写入 DROPFILES 结构头
            ctypes.memmove(p_global,
                           (ctypes.c_uint * 5)(_DROPFILES_SIZE, 0, 0, 0, 1),
                           _DROPFILES_SIZE)

            # 写入文件路径 (宽字符)
            file_offset = ctypes.c_void_p(p_global + _DROPFILES_SIZE)
            ctypes.windll.kernel32.lstrcpyW(file_offset, file_path)

        finally:
            kernel32.GlobalUnlock(h_global)

        # 打开并清空剪贴板
        if not user32.OpenClipboard(0):
            logger.error("[EmoteSender] OpenClipboard 失败")
            kernel32.GlobalFree(h_global)
            return False

        try:
            if not user32.EmptyClipboard():
                logger.error("[EmoteSender] EmptyClipboard 失败")
                kernel32.GlobalFree(h_global)
                return False

            if not user32.SetClipboardData(CF_HDROP, h_global):
                logger.error("[EmoteSender] SetClipboardData 失败")
                kernel32.GlobalFree(h_global)
                return False

            # 所有权已移交系统，不再手动 GlobalFree
        finally:
            user32.CloseClipboard()

        return True

    except Exception:
        logger.exception("[EmoteSender] CF_HDROP 写入异常")
        try:
            kernel32.GlobalFree(h_global)
        except Exception:
            pass
        return False


def copy_file_to_clipboard(file_path: str) -> bool:
    """
    将表情文件以最优方式复制到剪贴板。
    · 静态图片 (png/jpg/webp) → 以 QImage 格式写入
    · GIF/视频/音频 → 以 Windows 原生 CF_HDROP 格式写入，聊天软件直接识别为文件拖放
    """
    if not file_path or not os.path.isfile(file_path):
        logger.error(f"[EmoteSender] 文件不存在: {file_path}")
        return False

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    # ── 静态图片 → QImage ──
    if ext in IMAGE_EXTS:
        img = QImage(file_path)
        if img.isNull():
            logger.error(f"[EmoteSender] 图片加载失败: {file_path}")
            return False
        QApplication.clipboard().setImage(img)
        logger.info(f"[EmoteSender] 已复制图片到剪贴板 ({filename})")
        return True

    # ── GIF/视频/音频 → Windows 原生 CF_HDROP ──
    if _copy_file_via_cf_hdrop(file_path):
        logger.info(f"[EmoteSender] 已复制文件到剪贴板(CF_HDROP) ({filename}, {ext})")
        return True
    else:
        logger.error(f"[EmoteSender] CF_HDROP 写入失败: {file_path}")
        return False


def paste_to_chat(delay_ms: int = 50):
    """
    将剪贴板内容粘贴到聊天框 (Ctrl+V)。
    延迟确保剪贴板数据已被系统完全提交。
    """
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    keyboard.send('ctrl+v')
    logger.debug("[EmoteSender] Ctrl+V 已发送")


def _clear_clipboard():
    """清空剪贴板，防止内容残留。"""
    clipboard = QApplication.clipboard()
    for _ in range(3):
        clipboard.clear()
        clipboard.setText("")
        QApplication.processEvents()
        if not clipboard.mimeData().hasImage() and not clipboard.mimeData().hasText():
            return
        time.sleep(0.01)
    logger.debug("[EmoteSender] 剪贴板清理：多次尝试后仍残留内容")


def send_emote(file_path: str, clear_after: bool = True) -> bool:
    """
    一站式发送：复制 + 粘贴 + (可选)清空剪贴板。
    clear_after=True 时，粘贴完成后会清空剪贴板，避免发送后残留。
    返回是否成功。
    """
    if not copy_file_to_clipboard(file_path):
        return False
    paste_to_chat()
    if clear_after:
        # 留一点时间给目标软件接收粘贴的内容
        time.sleep(0.3)
        _clear_clipboard()
    return True