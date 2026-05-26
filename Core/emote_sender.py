import os
import sys
import time
import ctypes
from ctypes import wintypes
import keyboard
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData, QUrl, Qt, QByteArray, QTimer
from PySide6.QtSvg import QSvgRenderer
from Core.logger import logger

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'}
ALL_EXTS = IMAGE_EXTS | {'.gif', '.mp4', '.webm', '.mp3', '.wav', '.ogg', '.avi', '.mov'}

# TODO: 未来设置项 — 用户可选择 GIF 是否以首帧静图发送
_SEND_GIF_AS_STATIC = False

# 剪贴板清理总开关
_ENABLE_CLEANUP = True

# Windows CF_HDROP 常量
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


def set_cleanup_after_send(enabled: bool):
    """设置发送后是否自动清理剪贴板（总开关）。"""
    global _ENABLE_CLEANUP
    _ENABLE_CLEANUP = enabled
    logger.info(f"[EmoteSender] 剪贴板清理已{'启用' if enabled else '禁用'}")


def _set_windows_clipboard_hdrop(file_path: str):
    """
    使用 ctypes 直接向 Windows 剪贴板注入 CF_HDROP 格式。
    仅追加格式，不清空已有数据（保留 QMimeData 写入的其他格式）。
    仅在 Windows 上有效。
    """
    if os.name != 'nt':
        return

    try:
        # 路径必须以双 NULL 结尾，且使用宽字符 (utf-16-le)
        files = file_path.replace("/", "\\") + "\0" + "\0"
        data = files.encode("utf-16-le")

        # 准备 DROPFILES 结构体
        df = DROPFILES()
        df.pFiles = ctypes.sizeof(DROPFILES)
        df.fWide = True  # 使用 Unicode (WideChar)

        # 合并结构体和路径数据
        combined_data = bytes(df) + data
        size = len(combined_data)

        # 打开 Windows 剪贴板
        if not ctypes.windll.user32.OpenClipboard(0):
            logger.debug("[EmoteSender] OpenClipboard 失败 (可能被其他进程占用)")
            return

        try:
            # 注意：不调用 EmptyClipboard()，保留已有的 QMimeData 格式
            h_global = ctypes.windll.kernel32.GlobalAlloc(
                GMEM_MOVEABLE | GMEM_ZEROINIT, size
            )
            if not h_global:
                logger.error("[EmoteSender] GlobalAlloc 失败")
                return

            p_global = ctypes.windll.kernel32.GlobalLock(h_global)
            try:
                ctypes.memmove(p_global, combined_data, size)
            finally:
                ctypes.windll.kernel32.GlobalUnlock(h_global)

            ctypes.windll.user32.SetClipboardData(CF_HDROP, h_global)
            logger.debug("[EmoteSender] CF_HDROP 已注入剪贴板")
        finally:
            ctypes.windll.user32.CloseClipboard()

    except Exception as e:
        logger.warning(f"[EmoteSender] Windows 原生剪贴板注入失败: {e}")


def copy_file_to_clipboard(file_path: str) -> bool:
    """
    将表情文件以最优方式复制到剪贴板。
    · 图片 (png/jpg/webp/gif) → QMimeData URL + PNG 原始字节 + Windows CF_HDROP
        （避免 QImage→DIB 转换丢失 Alpha 通道）
    · 视频/音频 → 以文件引用 (text/uri-list) 写入，由聊天软件自行处理
    """
    if not file_path or not os.path.isfile(file_path):
        logger.error(f"[EmoteSender] 文件不存在: {file_path}")
        return False

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    # 所有图片文件 → QMimeData URL + CF_HDROP（避免 DIB 丢失 Alpha 通道）
    if ext in IMAGE_EXTS or ext == '.gif':
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(file_path)])

        # 对于 PNG 文件，同时写入原始 PNG 字节数据以保留 Alpha 通道
        if ext == '.png':
            with open(file_path, 'rb') as f:
                png_data = f.read()
            mime.setData('image/png', QByteArray(png_data))
            logger.debug(f"[EmoteSender] 已附加 PNG 原始数据 ({filename})")

        QApplication.clipboard().setMimeData(mime)
        logger.debug(f"[EmoteSender] QMimeData URL 已写入 ({filename})")

        # 追加 Windows 原生 CF_HDROP
        _set_windows_clipboard_hdrop(file_path)
        logger.info(f"[EmoteSender] 已复制图片到剪贴板 ({filename})")
        return True

    # 视频/音频 → 文件引用
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(file_path)])
    QApplication.clipboard().setMimeData(mime)
    logger.info(f"[EmoteSender] 已复制文件引用到剪贴板 ({filename}, {ext})")
    return True


def paste_to_chat(delay_ms: int = 50):
    """将剪贴板内容粘贴到聊天框 (Ctrl+V)，延迟后按需清理剪贴板"""
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    keyboard.send('ctrl+v')
    logger.debug("[EmoteSender] Ctrl+V 已发送")

    # 粘贴后延迟清理剪贴板，避免残留数据
    # 使用 QTimer.singleShot 在主线程事件循环中触发，安全执行 Qt GUI 操作
    if _ENABLE_CLEANUP:
        QTimer.singleShot(500, _cleanup_clipboard)
        logger.debug(f"[EmoteSender] 将在 500ms 后清理剪贴板")


def _cleanup_clipboard():
    """清空剪贴板（使用稳健清理，确保文字和图片都被清除）。"""
    try:
        from Core.clipboard_mgr import ClipboardManager
        ClipboardManager.robust_clear()
        logger.debug("[EmoteSender] 剪贴板已清理")
    except Exception:
        logger.exception("[EmoteSender] 剪贴板清理时发生异常")


def send_emote(file_path: str, delay_ms: int = 50) -> bool:
    """一站式发送：复制 + 粘贴，返回是否成功"""
    if not copy_file_to_clipboard(file_path):
        return False
    paste_to_chat(delay_ms=delay_ms)
    return True


def get_video_first_frame_pixmap(video_path: str, width: int, height: int) -> "QPixmap|None":
    """使用 OpenCV 提取视频首帧，返回缩放后的 QPixmap，失败返回 None"""
    try:
        import cv2
        import numpy as np
        from PySide6.QtGui import QImage, QPixmap
    except ImportError:
        logger.warning("[EmoteSender] opencv-python-headless 未安装，无法提取视频首帧")
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.debug(f"[EmoteSender] 无法打开视频: {video_path}")
        return None

    ret, frame = cap.read()
    cap.release()
    if not ret:
        logger.debug(f"[EmoteSender] 无法读取视频帧: {video_path}")
        return None

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = frame_rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg)
    return pixmap.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)


def get_external_resource_path(relative_path: str) -> str:
    """Get absolute path for external resources (supports both dev and frozen exe)."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def load_svg_pixmap(svg_filename: str, width: int, height: int):
    """Load an SVG from Assets/Svg/ and render it to a QPixmap of given size.  Returns None on failure."""
    svg_path = get_external_resource_path(f"Assets/Svg/{svg_filename}")
    if not os.path.exists(svg_path):
        return None
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
        if not renderer.isValid():
            return None
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        from PySide6.QtGui import QPainter
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap
    except Exception:
        return None
