import os
import re
from PIL import Image, ImageDraw, ImageFont
from Core.logger import logger

class ImageGenerator:
    """
    图像合成生成器 (完整旗舰版)
    已优化：完美支持十六进制颜色字符串与 RGB 列表混合输入
    已优化：保留全部底层旋转、图层嵌套、物理级防溢出引擎
    已优化：支持内联图片挤压排版与高级正则表达式变色引擎
    """
    def __init__(self, fonts_dir="./Fonts"):
        self.fonts_dir = fonts_dir
        self.default_font_name = "msyh.ttc" 

    def _parse_color(self, color):
        """核心改进：将 [R,G,B] 或 "#hex" 统一转换为 PIL 支持的元组"""
        if isinstance(color, str) and color.startswith("#"):
            h = color.lstrip('#')
            # 处理 #FFF 和 #FFFFFF 两种情况
            if len(h) == 3:
                h = ''.join([c*2 for c in h])
            # 处理带透明度 #RRGGBBAA
            if len(h) == 8:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4, 6))
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        if isinstance(color, list):
            return tuple(color)
        return color

    def _get_line_char_colors(self, text, default_color, rules, current_prefix_color=None):
        """
        计算一行文字中每个字符的颜色数组，支持跨行的前缀状态记忆。
        已修复：正则表达式转义问题、规则优先级冲突、空规则校验。
        """
        import re
        from Core.logger import logger # 确保引入日志模块
        
        # 确保 rules 始终是一个列表，防止 NoneType 导致 rules_count 为 0
        if rules is None:
            rules = []
            
        base_color = self._parse_color(default_color)
        
        # 1. 跨行记忆状态初始化
        starting_color = current_prefix_color if current_prefix_color else base_color
        char_colors = [starting_color] * len(text)
        
        # 打印详细初始状态，帮助定位配置丢失问题
        rules_count = len(rules)
        logger.debug(f"[变色渲染] 处理文本: '{text}' | 初始状态色: {starting_color} | 规则总数: {rules_count}")
        
        if rules_count == 0:
            # 如果这里是 0，说明调用该函数的地方传递的 rules 参数为空
            return char_colors, current_prefix_color

        if not text:
            return char_colors, current_prefix_color

        # 2. 染色遮罩
        colored_mask = [False] * len(text)
        new_prefix_color = current_prefix_color

        # 3. 优先级排序
        # 按照类型排序：先处理 prefix (精确前缀)，再处理 enclose (泛化包裹)
        sorted_rules = sorted(rules, key=lambda x: x.get("type") == "enclose")

        for rule in sorted_rules:
            r_type = rule.get("type")
            start_tag = rule.get("start", "")
            end_tag = rule.get("end", "")
            
            if not start_tag:
                continue
                
            try:
                # 尝试解析颜色，如果失败则跳过
                raw_color = rule.get("color", "#ffffff")
                rule_color = self._parse_color(raw_color)
            except Exception as e:
                logger.error(f"[变色渲染] 颜色解析失败: {raw_color} - {e}")
                continue

            # 处理包裹模式 (e.g. [test] or 【内容】)
            if r_type == "enclose" and end_tag:
                # re.escape 是关键，它能将 '[' 转义为 '\['，避免正则语法冲突
                safe_start = re.escape(start_tag)
                safe_end = re.escape(end_tag)
                pattern = f"{safe_start}.*?{safe_end}"
                
                matches = list(re.finditer(pattern, text))
                if matches:
                    logger.debug(f"[变色渲染] 匹配成功: '{start_tag}...{end_tag}' -> 命中 {len(matches)} 处")
                
                for m in matches:
                    s_idx, e_idx = m.start(), m.end()
                    for k in range(s_idx, e_idx):
                        if not colored_mask[k]:
                            char_colors[k] = rule_color
                            colored_mask[k] = True
                    logger.debug(f"  └─ 染色成功: 索引[{s_idx}:{e_idx}] -> 颜色: {rule_color}")

            # 处理前缀模式 (e.g. [伪证] 之后全部变色)
            elif r_type == "prefix":
                pos = text.find(start_tag)
                if pos != -1:
                    logger.debug(f"[变色渲染] 命中 Prefix 规则 '{start_tag}': 起始位置 {pos}")
                    for k in range(pos, len(text)):
                        if not colored_mask[k]:
                            char_colors[k] = rule_color
                            colored_mask[k] = True
                    new_prefix_color = rule_color
                    logger.debug(f"  └─ 状态记忆更新: 下一行将继承颜色 {new_prefix_color}")
        
        return char_colors, new_prefix_color
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

        # 1. 基础排版参数 (全面接入解析器)
        text_color = self._parse_color(config.get("text_color", [255, 255, 255]))
        stroke_color = self._parse_color(config.get("stroke_color", [0, 0, 0]))
        underline_color = self._parse_color(config.get("underline_color", config.get("text_color", [255, 255, 255])))
        stroke_width = config.get("stroke_width", 3)
        font_name = config.get("font_name", "msyh.ttc")
        align = config.get("text_align", "center")
        valign = config.get("valign", "bottom")
        
        # 间距与样式参数
        letter_spacing = config.get("letter_spacing", 0)  
        line_spacing = config.get("line_spacing", 4)      
        is_italic = config.get("is_italic", False)
        is_underline = config.get("is_underline", False)
        text_rotation = config.get("text_rotation", 0)

        # 2. 画布与底图参数
        orig_w, orig_h = base_image.size
        # 如果不设置 canvas_w/h，默认画布大小等于原始底图大小
        canvas_w = config.get("canvas_w", 0) or orig_w
        canvas_h = config.get("canvas_h", 0) or orig_h
        
        base_x = config.get("base_x", 0)
        base_y = config.get("base_y", 0)
        base_w = config.get("base_w", 0) or orig_w
        base_h = config.get("base_h", 0) or orig_h
        base_rotation = config.get("base_rotation", 0)

        # 文字外框坐标与宽高 (相对于主画布)
        box_x, box_y = config.get("box_x", 0), config.get("box_y", 0)
        box_w = config.get("box_w", 0) or canvas_w
        box_h = config.get("box_h", 0) or canvas_h
        max_chars = config.get("max_chars", 0)
        offset_x, offset_y = config.get("offset_x", 0), config.get("offset_y", 0)
        
        # ====================================================
        # 【修改一：仅计算内联图片尺寸，预先挤压文字的最大允许宽度】
        # ====================================================
        orig_box_x = box_x
        orig_box_w = box_w
        inline_img_data = config.get("inline_image")
        inline_img_resized = None
        target_w = 0
        spacing = 15 # 图文间距
        
        if inline_img_data:
            try:
                if inline_img_data.mode != 'RGBA':
                    inline_img_data = inline_img_data.convert('RGBA')
                
                target_h = int(box_h * 0.8) if box_h else 100
                ratio = target_h / inline_img_data.height
                target_w = int(inline_img_data.width * ratio)
                
                inline_img_resized = inline_img_data.resize((target_w, target_h), Image.LANCZOS)
                
                # 这一步很关键：只缩小文字引擎的排版边界，但不修改起始坐标 box_x
                box_w = box_w - target_w - spacing  
                
            except Exception as e:
                logger.error(f"内联图片处理失败: {e}")
        # ===================================================

        # --- 图层系统建立 ---
        # 建立完全透明的 RGBA 主画布
        img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        
        # ====== 绘制底图 (Base Layer) ======
        if base_image.mode != 'RGBA':
            base_image = base_image.convert('RGBA')
        base_resized = base_image.resize((base_w, base_h), Image.LANCZOS)
        
        if base_rotation != 0:
            # 开启 expand=True 保证旋转后四角不会被切掉，同时做中心点坐标补偿
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
            
            # 【全新换行逻辑】：逐段落、逐字像素扫描
            for paragraph in text.split('\n'):
                if not paragraph:
                    line_datas.append({"text": "", "width": 0, "height": line_height, "char_widths": []})
                    continue
                    
                current_line_text = ""
                current_line_w = 0
                current_char_widths = []
                
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
                        # A模式：强制限制单行字数
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

            # 【常驻防溢出保底】：当所有排版手段都用尽，文字高度仍然超出边界，才触发整体字号缩小
            if (max_line_w > box_w - 10 or total_h > box_h - 10) and font_size > 10:
                font_size -= 2
                continue
                
            break # 完美装入，跳出循环

        # ====================================================
        # 【修改二：排版完成后，将图文作为一个整体进行居中偏移】
        # ====================================================
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

        # 【核心修复】：将所有图层(内联图片 + 普通悬浮层) 按照 Z 层级从小到大排序
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
            
            # ⭐ 获取本行颜色清单，并同步更新跨行染色状态
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