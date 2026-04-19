import os
from PIL import Image, ImageDraw, ImageFont
from Core.logger import logger

class ImageGenerator:
    """
    图像合成生成器
    负责将获取到的文字绘制到底图上，支持自适应缩放、字间距与行间距调节
    支持伪斜体、下划线（带独立颜色控制），支持文字整体旋转
    支持底图位置/大小/旋转修改，支持无限层叠覆盖图层及其优先级与独立旋转
    常驻像素级物理防溢出与自动换行引擎
    """
    def __init__(self, fonts_dir="./Fonts"):
        self.fonts_dir = fonts_dir
        self.default_font_name = "msyh.ttc" 
        
    def _get_font(self, font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
        if not font_name:
            font_name = self.default_font_name
        local_font_path = os.path.join(self.fonts_dir, font_name)
        sys_font_path = f"C:/Windows/Fonts/{font_name}"
        try:
            if os.path.exists(local_font_path):
                return ImageFont.truetype(local_font_path, font_size)
            elif os.path.exists(sys_font_path):
                return ImageFont.truetype(sys_font_path, font_size)
            else:
                return ImageFont.truetype("msyh.ttc", font_size)
        except:
            return ImageFont.load_default()

    def generate(self, base_image: Image.Image, text: str, config: dict = None) -> Image.Image:
        if not base_image:
            base_image = Image.new('RGB', (400, 300), color=(40, 42, 54))
            
        config = config or {}

        text_color = tuple(config.get("text_color", [255, 255, 255]))
        stroke_color = tuple(config.get("stroke_color", [0, 0, 0]))
        underline_color = tuple(config.get("underline_color", config.get("text_color", [255, 255, 255])))
        stroke_width = config.get("stroke_width", 3)
        font_name = config.get("font_name", "msyh.ttc")
        align = config.get("text_align", "center")
        valign = config.get("valign", "bottom")
        
        letter_spacing = config.get("letter_spacing", 0)  
        line_spacing = config.get("line_spacing", 4)      
        is_italic = config.get("is_italic", False)
        is_underline = config.get("is_underline", False)
        text_rotation = config.get("text_rotation", 0)

        orig_w, orig_h = base_image.size
        canvas_w = config.get("canvas_w", 0) or orig_w
        canvas_h = config.get("canvas_h", 0) or orig_h
        
        base_x = config.get("base_x", 0)
        base_y = config.get("base_y", 0)
        base_w = config.get("base_w", 0) or orig_w
        base_h = config.get("base_h", 0) or orig_h
        base_rotation = config.get("base_rotation", 0)

        box_x, box_y = config.get("box_x", 0), config.get("box_y", 0)
        box_w = config.get("box_w", 0) or canvas_w
        box_h = config.get("box_h", 0) or canvas_h
        max_chars = config.get("max_chars", 0)
        offset_x, offset_y = config.get("offset_x", 0), config.get("offset_y", 0)

        img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        
        if base_image.mode != 'RGBA':
            base_image = base_image.convert('RGBA')
        base_resized = base_image.resize((base_w, base_h), Image.LANCZOS)
        
        if base_rotation != 0:
            base_rotated = base_resized.rotate(-base_rotation, resample=Image.BILINEAR, expand=True)
            rx = int(base_x + base_w / 2 - base_rotated.width / 2)
            ry = int(base_y + base_h / 2 - base_rotated.height / 2)
            img.paste(base_rotated, (rx, ry), mask=base_rotated)
        else:
            img.paste(base_resized, (base_x, base_y), mask=base_resized)

        overlays_cfg = config.get("overlays", [])
        
        old_overlay = config.get("overlay_image", "")
        if old_overlay and not overlays_cfg:
            overlays_cfg = [{
                "image": old_overlay,
                "x": config.get("overlay_x", 0),
                "y": config.get("overlay_y", 0),
                "w": config.get("overlay_w", 0),
                "h": config.get("overlay_h", 0),
                "z": config.get("overlay_z", 2),
                "rotation": 0
            }]

        loaded_overlays = []
        for ov_cfg in overlays_cfg:
            img_name = ov_cfg.get("image", "")
            if not img_name: continue
            
            ov_path = os.path.join(config.get("_folder_path", ""), img_name)
            if os.path.exists(ov_path):
                try:
                    ov_img = Image.open(ov_path).convert('RGBA')
                    ow = ov_cfg.get("w", 0) or ov_img.width
                    oh = ov_cfg.get("h", 0) or ov_img.height
                    ov_rot = ov_cfg.get("rotation", 0)
                    
                    ov_img = ov_img.resize((ow, oh), Image.LANCZOS)
                    
                    if ov_rot != 0:
                        ov_rotated = ov_img.rotate(-ov_rot, resample=Image.BILINEAR, expand=True)
                        rx = int(ov_cfg.get("x", 0) + ow / 2 - ov_rotated.width / 2)
                        ry = int(ov_cfg.get("y", 0) + oh / 2 - ov_rotated.height / 2)
                        loaded_overlays.append({
                            "img": ov_rotated,
                            "x": rx,
                            "y": ry,
                            "z": ov_cfg.get("z", 2)
                        })
                    else:
                        loaded_overlays.append({
                            "img": ov_img,
                            "x": ov_cfg.get("x", 0),
                            "y": ov_cfg.get("y", 0),
                            "z": ov_cfg.get("z", 2)
                        })
                except Exception as e:
                    logger.warning(f"覆盖图层 {img_name} 加载失败: {e}")

        loaded_overlays.sort(key=lambda x: x["z"])

        for ov in loaded_overlays:
            if ov["z"] <= 0:
                img.paste(ov["img"], (ov["x"], ov["y"]), mask=ov["img"])

        draw = ImageDraw.Draw(img)

        font_size = config.get("font_size", 0) or int(box_h * 0.15)
        total_h = 0
        max_line_w = 0
        line_datas = [] 
        
        while font_size > 8:
            font = self._get_font(font_name, font_size)
            italic_offset = int(font_size * 0.25) if is_italic else 0

            # 修复：获取包含最高字母的基准边界，提取字体自带的留白偏移 (y0)
            ref_bbox = draw.textbbox((0, 0), "Hg国", font=font, stroke_width=stroke_width)
            font_y_offset = ref_bbox[1]  
            line_height = ref_bbox[3] - ref_bbox[1]

            line_datas = [] 
            
            for paragraph in text.split('\n'):
                if not paragraph:
                    line_datas.append({"text": "", "width": 0, "height": line_height, "char_widths": []})
                    continue
                    
                current_line_text = ""
                current_line_w = 0
                current_char_widths = []
                
                for char in paragraph:
                    c_bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
                    ink_w = c_bbox[2] - c_bbox[0]
                    try:
                        typographic_w = draw.textlength(char, font=font)
                    except AttributeError:
                        typographic_w = font.getlength(char) if hasattr(font, 'getlength') else font.getsize(char)[0]
                    
                    cw = max(typographic_w, ink_w)
                    
                    if max_chars > 0:
                        if len(current_line_text) >= max_chars:
                            line_datas.append({
                                "text": current_line_text, 
                                "width": current_line_w - letter_spacing, 
                                "height": line_height,
                                "char_widths": current_char_widths
                            })
                            current_line_text = char
                            current_line_w = cw + letter_spacing
                            current_char_widths = [cw]
                        else:
                            current_line_text += char
                            current_line_w += cw + letter_spacing
                            current_char_widths.append(cw)
                    else:
                        if current_line_w + cw + italic_offset > (box_w - 20) and current_line_text:
                            line_datas.append({
                                "text": current_line_text, 
                                "width": current_line_w - letter_spacing, 
                                "height": line_height,
                                "char_widths": current_char_widths
                            })
                            current_line_text = char
                            current_line_w = cw + letter_spacing
                            current_char_widths = [cw]
                        else:
                            current_line_text += char
                            current_line_w += cw + letter_spacing
                            current_char_widths.append(cw)
                            
                if current_line_text:
                    line_datas.append({
                        "text": current_line_text, 
                        "width": current_line_w - letter_spacing, 
                        "height": line_height,
                        "char_widths": current_char_widths
                    })
            
            total_h = len(line_datas) * line_height + (len(line_datas) - 1) * line_spacing if line_datas else 0
            max_line_w = max([ld["width"] for ld in line_datas]) + italic_offset if line_datas else 0

            if (max_line_w > box_w - 10 or total_h > box_h - 10) and font_size > 10:
                font_size -= 2
                continue
                
            break 

        if config.get("show_box"):
            overlay_box = Image.new('RGBA', img.size, (0,0,0,0))
            od = ImageDraw.Draw(overlay_box)
            bc = tuple(config.get("box_color", [0,0,0,128]))
            bbc = tuple(config.get("box_border_color", [255,255,255,255]))
            bbw = config.get("box_border_width", 0)
            
            fill_color = bc if len(bc) == 4 else bc + (255,)
            outline_color = bbc if len(bbc) == 4 else bbc + (255,)
            
            od.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=fill_color, outline=outline_color, width=bbw)
            img = Image.alpha_composite(img, overlay_box)

        for ov in loaded_overlays:
            if ov["z"] == 1:
                img.paste(ov["img"], (ov["x"], ov["y"]), mask=ov["img"])

        text_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        
        curr_y = 0
        if valign == "middle": curr_y = box_y + (box_h - total_h) / 2
        elif valign == "bottom": curr_y = box_y + box_h - total_h - 10
        else: curr_y = box_y + 10 # top
        
        curr_y += config.get("offset_y", 0)
        
        # ⬅️ 【核心修复】：向上提拉，抵消 Pillow 字体的隐形顶部留白，实现绝对物理居中
        curr_y -= font_y_offset 

        for ld in line_datas:
            line_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            line_draw = ImageDraw.Draw(line_layer)
            
            if align == "center": curr_x = box_x + (box_w - ld["width"]) / 2
            elif align == "right": curr_x = box_x + box_w - ld["width"] - 10
            else: curr_x = box_x + 10 # left
            
            curr_x += config.get("offset_x", 0)
            
            temp_x = curr_x
            for i, char in enumerate(ld["text"]):
                line_draw.text((temp_x, curr_y), char, font=font, fill=text_color, 
                               stroke_width=stroke_width, stroke_fill=stroke_color)
                
                if is_underline:
                    ul_y = curr_y + ld["height"] + max(1, font_size // 15)
                    ul_width = max(1, font_size // 15)
                    line_draw.line([(temp_x, ul_y), (temp_x + ld["char_widths"][i], ul_y)], 
                                   fill=underline_color, width=ul_width)
                
                temp_x += ld["char_widths"][i] + letter_spacing

            if is_italic:
                baseline_y = curr_y + ld["height"]
                slant = 0.25 
                line_layer = line_layer.transform(
                    line_layer.size, Image.AFFINE,
                    (1, slant, -slant * baseline_y, 0, 1, 0),
                    resample=Image.BILINEAR
                )
                
            text_layer = Image.alpha_composite(text_layer, line_layer)
            curr_y += ld["height"] + line_spacing

        if text_rotation != 0:
            center_x = box_x + box_w / 2
            center_y = box_y + box_h / 2
            text_layer = text_layer.rotate(-text_rotation, resample=Image.BILINEAR, center=(center_x, center_y))

        img = Image.alpha_composite(img, text_layer)
        
        for ov in loaded_overlays:
            if ov["z"] >= 2:
                img.paste(ov["img"], (ov["x"], ov["y"]), mask=ov["img"])

        if base_image.mode == 'RGB':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3]) 
            img = bg
            
        return img