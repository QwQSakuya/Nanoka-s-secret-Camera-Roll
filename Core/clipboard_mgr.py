import time
from PySide6.QtGui import QClipboard, QImage
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageQt

class ClipboardManager:
    """
    剪贴板管理器
    负责拦截、读取和重写剪贴板内容
    结合 PySide6 的 QClipboard 和 Pillow 进行图片转换
    """
    def __init__(self):
        # 获取全局的 QApplication 剪贴板实例
        self.clipboard = QApplication.clipboard()
        # 用于暂存底图的变量
        self.cached_image: Image.Image | None = None

    def get_text(self) -> str:
        """获取剪贴板中的纯文本"""
        return self.clipboard.text()

    def get_image(self) -> Image.Image | None:
        """
        获取剪贴板中的图片
        返回: PIL.Image 对象，如果没有图片则返回 None
        """
        mime_data = self.clipboard.mimeData()
        if mime_data.hasImage():
            qimage = self.clipboard.image()
            # 将 Qt 的 QImage 转换为 Pillow 可以处理的 Image 对象
            pil_img = ImageQt.fromqimage(qimage)
            return pil_img
        return None

    def set_image(self, pil_img: Image.Image):
        """
        将生成的 Pillow 图像写入系统剪贴板
        准备供 Ctrl+V 粘贴使用
        """
        # 将 Pillow Image 转换为 QImage
        qimage = ImageQt.ImageQt(pil_img)
        self.clipboard.setImage(qimage)

    def clear(self):
        """清空剪贴板内容"""
        self.clipboard.clear()

    def check_and_backup_image(self) -> bool:
        """
        【步骤 1】检查剪贴板内是否存在图片，如果存在，存储在 self.cached_image 变量中。
        返回 True 表示成功备份了图片，False 表示没有图片。
        """
        img = self.get_image()
        if img:
            self.cached_image = img
            return True
        else:
            self.cached_image = None
            return False

    def get_cached_image(self) -> Image.Image | None:
        """获取暂存的图片"""
        return self.cached_image

    def grab_text_after_cut(self, delay: float = 0.15) -> str:
        """
        【步骤 2】在模拟了 Ctrl+A 和 Ctrl+X (全选剪切) 后，调用此方法提取文字。
        """
        time.sleep(delay)
        return self.get_text()

# 测试代码 (仅在直接运行此文件时执行)
if __name__ == "__main__":
    import sys
    # QClipboard 必须在 QApplication 实例化后才能使用
    app = QApplication(sys.argv)
    
    mgr = ClipboardManager()
    
    print("--- 剪贴板接管逻辑测试 ---")
    print("【真实工作流模拟】")
    
    # 1. 模拟按下快捷键瞬间
    print("1. 检查剪贴板是否存在图片并备份...")
    has_img = mgr.check_and_backup_image()
    if has_img:
        print(f"   -> [成功] 图片已存入变量！尺寸: {mgr.get_cached_image().size}")
    else:
        print("   -> [提示] 当前无图片，变量存为 None。")
        
    # 2. 这里假设按键监听模块发送了 Ctrl+A 和 Ctrl+X ...
    print("2. 执行全选剪切 (模拟延时) 以获取文字...")
    text = mgr.grab_text_after_cut(delay=0.1)
    
    if text:
        print(f"   -> [成功] 提取到文本: '{text}'")
    else:
        print("   -> [提示] 没有提取到文本。")