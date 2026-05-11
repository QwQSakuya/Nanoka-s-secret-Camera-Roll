import time
from PySide6.QtGui import QClipboard, QImage
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageQt
from Core.logger import logger


class ClipboardManager:
    """剪贴板管理器：拦截、读取、重写剪贴板内容 (QClipboard + Pillow)"""
    def __init__(self):
        self.clipboard = QApplication.clipboard()
        self.cached_image: Image.Image | None = None
        logger.debug("ClipboardManager 已初始化")

    def get_text(self) -> str:
        """获取剪贴板中的纯文本"""
        text = self.clipboard.text()
        if text:
            logger.debug(f"剪贴板获取文本: {len(text)} 字符")
        return text

    def get_image(self) -> Image.Image | None:
        mime_data = self.clipboard.mimeData()
        if mime_data.hasImage():
            qimage = self.clipboard.image()
            if qimage and not qimage.isNull():
                pil_img = ImageQt.fromqimage(qimage)
                logger.debug(f"剪贴板获取图片: {pil_img.size} {pil_img.mode}")
                return pil_img
        return None

    def set_image(self, pil_img: Image.Image):
        try:
            qimage = ImageQt.ImageQt(pil_img)
            self.clipboard.setImage(qimage)
            logger.debug(f"图片已写入剪贴板: {pil_img.size}")
        except Exception:
            logger.exception("剪贴板写入图片时发生异常")

    def clear(self):
        self.clipboard.clear()
        logger.debug("剪贴板已清空")

    @staticmethod
    def robust_clear():
        """稳健清空剪贴板（多轮尝试，确保文字和图片都被清除）。"""
        cb = QApplication.clipboard()
        for _ in range(3):
            cb.clear()
            cb.setText("")
            QApplication.processEvents()
            if not cb.mimeData().hasImage() and not cb.mimeData().hasText():
                return
            time.sleep(0.01)
        logger.debug("剪贴板清理：多次尝试后仍残留内容")

    def check_and_backup_image(self) -> bool:
        img = self.get_image()
        if img:
            self.cached_image = img
            logger.debug(f"剪贴板图片已备份: {img.size}")
            return True
        else:
            self.cached_image = None
            return False

    def get_cached_image(self) -> Image.Image | None:
        return self.cached_image

    def grab_text_after_cut(self, delay: float = 0.15) -> str:
        time.sleep(delay)
        return self.get_text()
