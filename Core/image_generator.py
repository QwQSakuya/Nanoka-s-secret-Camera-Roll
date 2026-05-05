import os
import re
from PIL import Image, ImageDraw, ImageFont
from Core.logger import logger

class ImageGenerator:
    """图像合成生成器 — 支持多图层、文字排版、语法高亮染色、内联图片"""

    def __init__(self, fonts_dir="./Fonts"):
        self.fonts_dir = fonts_dir
        self.default_font_name = "msyh.ttc"

    def _parse_color(self, color):
        """将 [R,G,B] 或 "#hex" 统一转换为 PIL 支持的元组"""
        if isinstance(color, str) and color.startswith("#"):
            h = color.lstrip('#')
            if len(h) == 3:
                h = ''.join([c * 2 for c in h])
            if len(h) == 8:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        if isinstance(color, list):
            return tuple(color)
        return color

    def _get_line_char_colors(self, text, default_color, rules, current_prefix_color=None):
        if rules is None:
            rules = []

        base_color = self._parse_color(default_color)

        starting_color = current_prefix_color if current_prefix_color else base_color
        char_colors = [starting_color] * len(text)

        rules_count = len(rules)
        logger.debug(
            f"[变色渲染] 文本: '{text}' | 初始色: {starting_color} | 规则数: {rules_count}"
        )

        if rules_count == 0:
            return char_colors, current_prefix_color

        if not text:
            return char_colors, current_prefix_color

        colored_mask = [False] * len(text)
        new_prefix_color = current_prefix_color

        sorted_rules = sorted(rules, key=lambda x: x.get("type") == "enclose")

        for rule in sorted_rules:
            r_type = rule.get("type")
            start_tag = rule.get("start", "")
            end_tag = rule.get("end", "")

            if not start_tag:
                continue

            try:
                raw_color = rule.get("color", "#ffffff")
                rule_color = self._parse_color(raw_color)
            except Exception:
                logger.exception(f"[变色渲染] 颜色解析失败: {rule.get('color', '?')}")
                continue

            if r_type == "enclose" and end_tag:
                safe_start = re.escape(start_tag)
                safe_end = re.escape(end_tag)
                pattern = f"{safe_start}.*?{safe_end}"

                matches = list(re.finditer(pattern, text))
                if matches:
                    logger.debug(
                        f"[变色渲染] 匹配: '{start_tag}...{end_tag}' -> 命中 {len(matches)} 处"
                    )

                for m in matches:
                    s_idx, e_idx = m.start(), m.end()
                    for k in range(s_idx, e_idx):
                        if not colored_mask[k]:
                            char_colors[k] = rule_color
                            colored_mask[k] = True

            elif r_type == "prefix":
                pos = text.find(start_tag)
                if pos != -1:
                    logger.debug(f"[变色渲染] 命中 Prefix: '{start_tag}' 位置 {pos}")
                    for k in range(pos, len(text)):
                        if not colored_mask[k]:
                            char_colors[k] = rule_color
                            colored_mask[k] = True
                    new_prefix_color = rule_color

        return char_colors, new_prefix_color

    def _find_protected_enclose_spans(self, paragraph, syntax_rules, threshold):
        """预扫描段落中的 enclose 包裹段，返回需要保护（不换行切断）的区间列表。
        仅当包裹段内文字（不含括号）字数 ≤ threshold 时才保护。
        返回 [(start, end), ...] 区间列表，区间已合并重叠部分。"""
        if not syntax_rules or threshold <= 0:
            return []

        spans = []
        for rule in syntax_rules:
            if rule.get("type") != "enclose":
                continue
            start_tag = rule.get("start", "")
            end_tag = rule.get("end", "")
            if not start_tag or not end_tag:
                continue

            safe_start = re.escape(start_tag)
            safe_end = re.escape(end_tag)
            pattern = f"{safe_start}.*?{safe_end}"

            for m in re.finditer(pattern, paragraph):
                content = m.group()[len(start_tag):-len(end_tag)] if end_tag else m.group()[len(start_tag):]
                if len(content) <= threshold:
                    spans.append((m.start(), m.end()))

        if not spans:
            return []

        spans.sort(key=lambda x: x[0])
        merged = [spans[0]]
        for s, e in spans[1:]:
            last_s, last_e = merged[-1]
            if s < last_e:
                merged[-1] = (last_s, max(last_e, e))
            else:
                merged.append((s, e))
        return merged

    def _get_font(self, font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
        """尝试获取字体"""
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

        text_color = self._parse_color(config.get("text_color", [255, 255, 255]))
        stroke_color = self._parse_color(config.get("stroke_color", [0, 0, 0]))
        underline_color = self._parse_color(config.get("underline_color", config.get("text_color", [255, 255, 255])))
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
        auto_wrap_threshold = config.get("auto_wrap_threshold", 6)
        syntax_rules = config.get("syntax_rules", [])
        offset_x, offset_y = config.get("offset_x", 0), config.get("offset_y", 0)
        
        orig_box_x = box_x
        orig_box_y = box_y
        orig_box_w = box_w
        orig_box_h = box_h
        inline_img_data = config.get("inline_image")
        inline_img_resized = None
        target_w = 0
        spacing = 15
        
        if inline_img_data:
            try:    
                if inline_img_data.mode != 'RGBA':
                    inline_img_data = inline_img_data.convert('RGBA')
                
                target_h = int(box_h * 0.8) if box_h else 100
                ratio = target_h / inline_img_data.height
                target_w = int(inline_img_data.width * ratio)
                
                inline_img_resized = inline_img_data.resize((target_w, target_h), Image.LANCZOS)
                
                box_w = box_w - target_w - spacing  
                
            except Exception as e:
                logger.error(f"内联图片处理失败: {e}")
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

        # ====== 加载多个覆盖图层 (Overlays) ======
        overlays_cfg = config.get("overlays", [])
        
        # 兼容老版单图层
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
                    logger.warning(f"覆盖图层加载失败: {e}")


        # 创建用于测量和绘制的基础对象
        draw = ImageDraw.Draw(img)

        # 3. 初始字号计算
        font_size = config.get("font_size", 0) or int(box_h * 0.15)
        auto_shrink = config.get("auto_shrink", False)
        
        total_h = 0
        max_line_w = 0
        line_datas = [] 
        
        # 4. 核心排版引擎: 常驻物理换行与缩小自适应
        while font_size > 8:
            font = self._get_font(font_name, font_size)
            
            # 计算样式造成的横向体积膨胀
            italic_offset = int(font_size * 0.25) if is_italic else 0

            # 提取字体高度 (使用大写字母 H 规范高度)
            ref_bbox = draw.textbbox((0, 0), "H", font=font, stroke_width=stroke_width)
            line_height = ref_bbox[3] - ref_bbox[1]

            line_datas = [] 
            
            # 逐段落、逐字像素扫描换行
            for paragraph in text.split('\n'):
                if not paragraph:
                    line_datas.append({"text": "", "width": 0, "height": line_height, "char_widths": []})
                    continue
                
                # 预扫描：找出本段落中需要保护不被切断的 enclose 包裹段
                protected_spans = self._find_protected_enclose_spans(
                    paragraph, syntax_rules, auto_wrap_threshold
                )
                    
                current_line_text = ""
                current_line_w = 0
                current_char_widths = []
                para_pos = 0
                
                for char in paragraph:
                    # 物理边界测量 (考虑了中英文宽度差)
                    c_bbox = draw.textbbox((0, 0), char, font=font, stroke_width=stroke_width)
                    ink_w = c_bbox[2] - c_bbox[0]
                    try:
                        typographic_w = draw.textlength(char, font=font)
                    except AttributeError:
                        typographic_w = font.getlength(char) if hasattr(font, 'getlength') else font.getsize(char)[0]
                    
                    cw = max(typographic_w, ink_w)
                    
                    # 判断是否需要换行
                    if max_chars > 0:
                        # A模式：强制限制单行字数 (历史产物，无UI入口)
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
                        # B模式：自动像素级边界换行 (预留 20px 安全边距)
                        if current_line_w + cw + italic_offset > (box_w - 20) and current_line_text:
                            # 检查当前位置是否在受保护的 enclose 包裹段内
                            in_protected = any(
                                start <= para_pos < end for start, end in protected_spans
                            )
                            if in_protected:
                                # 短括号段受保护，不在此处换行，允许溢出
                                current_line_text += char
                                current_line_w += cw + letter_spacing
                                current_char_widths.append(cw)
                            else:
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

                    para_pos += 1
                            
                # 把段落剩余的文字归入最后一行
                if current_line_text:
                    line_datas.append({
                        "text": current_line_text, 
                        "width": current_line_w - letter_spacing, 
                        "height": line_height,
                        "char_widths": current_char_widths
                    })
            
            # 计算这轮排版所需的总高度和最大宽度
            total_h = len(line_datas) * line_height + (len(line_datas) - 1) * line_spacing if line_datas else 0
            max_line_w = max([ld["width"] for ld in line_datas]) + italic_offset if line_datas else 0

            # 防溢出保底：文字超出边界时触发整体字号缩小
            if (max_line_w > box_w - 10 or total_h > box_h - 10) and font_size > 10:
                font_size -= 2
                continue
                
            break # 完美装入，跳出循环

        # 排版完成后，将图文作为一个整体进行居中偏移
        if inline_img_resized:
            # 此时 max_line_w 是引擎算出的实际文字宽度
            # 组合体的总宽度 = 图片宽度 + 间距 + 实际文字宽度
            combo_w = target_w + spacing + max_line_w
            
            # 根据 config 原本的对齐方式，计算整个组合体的起始 X 坐标！
            if align == "center":
                combo_x = orig_box_x + (orig_box_w - combo_w) / 2
            elif align == "right":
                combo_x = orig_box_x + orig_box_w - combo_w - 10
            else: # left
                combo_x = orig_box_x + 10
                
            # 1. 压入内联图片图层
            ix = int(combo_x)
            iy = int(box_y + (box_h - target_h) / 2)
            
            loaded_overlays.append({
                "img": inline_img_resized,
                "x": ix,
                "y": iy,
                "z": config.get("inline_z", 2)
            })
            
            # 2. 核心修正：把文字的起点推到图片右边，并锁死文字宽度，防止跑偏
            box_x = combo_x + target_w + spacing
            box_w = max_line_w 

        # 将所有图层按 Z 层级从小到大排序
        loaded_overlays.sort(key=lambda x: x.get("z", 2))

        # --- 图层绘制阶段 ---
        # Z <= 0 垫底层 (在底图上方, 文本框下方)
        for ov in loaded_overlays:
            if ov["z"] <= 0:
                img.paste(ov["img"], (ov["x"], ov["y"]), mask=ov["img"])

        # 5. 绘制背景外框 (Box Layer)
        if config.get("show_box"):
            overlay_box = Image.new('RGBA', img.size, (0,0,0,0))
            od = ImageDraw.Draw(overlay_box)
            bc = self._parse_color(config.get("box_color", [0,0,0,128]))
            bbc = self._parse_color(config.get("box_border_color", [255,255,255,255]))
            bbw = config.get("box_border_width", 0)
            
            fill_color = bc if len(bc) == 4 else bc + (255,)
            outline_color = bbc if len(bbc) == 4 else bbc + (255,)
            
            od.rectangle([orig_box_x, orig_box_y, orig_box_x + orig_box_w, orig_box_y + orig_box_h], 
                         fill=fill_color, outline=outline_color, width=bbw)
            img = Image.alpha_composite(img, overlay_box)

        # Z == 1 中间层 (在外框上方, 文字下方)
        for ov in loaded_overlays:
            if ov["z"] == 1:
                img.paste(ov["img"], (ov["x"], ov["y"]), mask=ov["img"])

        # 6. 正式绘制高级文字图层 (Text Layer)
        text_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        
        curr_y = 0
        if valign == "middle": curr_y = box_y + (box_h - total_h) / 2
        elif valign == "bottom": curr_y = box_y + box_h - total_h - 10
        else: curr_y = box_y + 10 # top
        
        curr_y += offset_y

        # 全局状态：用于跨行的前缀染色记忆
        active_prefix_color = None
        syntax_rules = config.get("syntax_rules", [])

        for ld in line_datas:
            # 每行的独立图层，方便进行倾斜变形（斜体）
            line_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            line_draw = ImageDraw.Draw(line_layer)
            
            if align == "center": curr_x = box_x + (box_w - ld["width"]) / 2
            elif align == "right": curr_x = box_x + box_w - ld["width"] - 10
            else: curr_x = box_x + 10 # left
            
            curr_x += offset_x
            temp_x = curr_x
            
            # 获取本行颜色清单，并同步更新跨行染色状态
            line_colors, active_prefix_color = self._get_line_char_colors(
                ld["text"], text_color, syntax_rules, active_prefix_color
            )

            for i, char in enumerate(ld["text"]):
                # 绘制文字
                line_draw.text(
                    (temp_x, curr_y), 
                    char, 
                    font=font, 
                    fill=line_colors[i], 
                    stroke_width=stroke_width, 
                    stroke_fill=stroke_color
                )
                
                # 绘制下划线
                if is_underline:
                    ul_y = curr_y + ld["height"] + max(1, font_size // 15)
                    ul_width = max(1, font_size // 15)
                    line_draw.line([(temp_x, ul_y), (temp_x + ld["char_widths"][i], ul_y)], 
                                   fill=underline_color, width=ul_width)
                
                temp_x += ld["char_widths"][i] + letter_spacing

            # 伪斜体变形
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

        # 文字整体旋转
        if text_rotation != 0:
            center_x = box_x + box_w / 2
            center_y = box_y + box_h / 2
            text_layer = text_layer.rotate(-text_rotation, resample=Image.BILINEAR, center=(center_x, center_y))

        # 将文字图层盖在主画布上
        img = Image.alpha_composite(img, text_layer)
        
        # 7. Z >= 2 顶层图层 (盖在所有东西，包括文字上方)
        for ov in loaded_overlays:
            if ov["z"] >= 2:
                img.paste(ov["img"], (ov["x"], ov["y"]), mask=ov["img"])
                
        # 8. 安全兼容处理：如果底图非透明，确保导出为无黑块的正常图片
        if getattr(base_image, "mode", "RGBA") == 'RGB':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            # 以 img 的 alpha 通道作为 mask 粘贴到纯白底图上
            if 'A' in img.getbands():
                bg.paste(img, mask=img.split()[3]) 
            else:
                bg.paste(img)
            img = bg

        return img