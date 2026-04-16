import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

class ImageGenerator:
    """
    图像合成生成器
    负责将获取到的文字绘制到底图上
    """
    def __init__(self, fonts_dir="./Fonts"):
        self.fonts_dir = fonts_dir
        # 默认字体名称（建议后续在 Fonts 文件夹中放入一个中文字体，比如 msyh.ttc 微软雅黑）
        self.default_font_name = "MiHeavy.ttf" 
        
    def _get_font(self, font_size: int) -> ImageFont.FreeTypeFont:
        """尝试获取中文字体，如果本地没有提供，回退到 Windows 系统自带微软雅黑"""
        local_font_path = os.path.join(self.fonts_dir, self.default_font_name)
        sys_font_path = f"C:/Windows/Fonts/{self.default_font_name}"
        
        try:
            if os.path.exists(local_font_path):
                return ImageFont.truetype(local_font_path, font_size)
            elif os.path.exists(sys_font_path):
                return ImageFont.truetype(sys_font_path, font_size)
            else:
                print("⚠️ [警告] 找不到中文字体，正在使用 PIL 默认英文字体 (中文会显示为方块)！")
                return ImageFont.load_default()
        except Exception as e:
            print(f"⚠️ [错误] 字体加载失败: {e}")
            return ImageFont.load_default()

    def generate(self, base_image: Image.Image, text: str, config: dict = None) -> Image.Image:
        """
        核心方法：在底图上绘制文字
        :param base_image: PIL Image 对象 (从剪贴板抓取的图)
        :param text: 聊天框剪切出来的文本
        :param config: 绘制参数 (颜色、位置等)
        :return: 合成后的新 PIL Image 对象
        """
        if not base_image:
            # 如果用户没复制图片，我们生成一张默认的带背景色的占位图
            base_image = Image.new('RGB', (400, 300), color=(40, 42, 54))
            
        # 防止污染原图，复制一份
        img = base_image.copy()
        draw = ImageDraw.Draw(img)
        
        # 提取配置（没有则使用默认值）
        config = config or {}
        text_color = config.get("text_color", (255, 255, 255))     # 默认白字
        stroke_color = config.get("stroke_color", (0, 0, 0))       # 默认黑边
        stroke_width = config.get("stroke_width", 3)               # 描边宽度
        
        # 动态计算字体大小：取图片高度的 15%（限制在 20px 到 100px 之间）
        calc_size = int(img.height * 0.15)
        font_size = config.get("font_size", max(20, min(calc_size, 100)))
        font = self._get_font(font_size)

        # ====== 文字自动换行处理 ======
        # 假设最大宽度是图片宽度的 90%
        # 根据粗略的字号估算每行最大字数（中文约占一整个 font_size 宽度）
        max_chars_per_line = max(1, int((img.width * 0.9) / font_size))
        wrapped_text = "\n".join(textwrap.wrap(text, width=max_chars_per_line))

        # ====== 计算文字排版位置 ======
        # 使用 multiline_textbbox 获取多行文字的边界框
        bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, stroke_width=stroke_width)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # 默认放置在图片底部居中 (距离底部留白 20px)
        x = (img.width - text_w) / 2
        y = img.height - text_h - 20
        
        # 绘制带描边的文字，确保在任何背景下都清晰可见
        draw.multiline_text(
            (x, y), 
            wrapped_text, 
            font=font, 
            fill=text_color, 
            stroke_width=stroke_width, 
            stroke_fill=stroke_color,
            align="center"
        )
        
        return img

# 独立测试代码
if __name__ == "__main__":
    generator = ImageGenerator()
    
    print("--- 图像生成模块独立测试 ---")
    # 创建一张测试底图 (红色的正方形)
    test_base = Image.new('RGB', (500, 500), color=(220, 60, 60))
    test_text = "这是一段用来测试自动换行和描边效果的长文本内容，喵喵喵！"
    
    print("1. 开始生成图片...")
    result_img = generator.generate(test_base, test_text)
    print("2. 生成成功，准备显示预览...")
    
    # 直接弹窗显示结果，方便你在本地肉眼确认效果
    result_img.show()