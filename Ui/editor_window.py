import os
import sys
import json
import shutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QLineEdit, QSlider, QColorDialog, 
                               QFrame, QApplication, QComboBox, QFileDialog, 
                               QMessageBox, QScrollArea, QSpinBox, QGridLayout, QSizePolicy)
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QTimer, Property, QPropertyAnimation, QEasingCurve, QByteArray, QSize
from PySide6.QtGui import QPixmap, QColor, QFont, QIcon, QMouseEvent, QPainter, QPainterPath
from PySide6.QtSvg import QSvgRenderer
from PIL import ImageQt, Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Core.image_generator import ImageGenerator
from Core.logger import logger

DIR_ASSETS_SVG = "./Assets/Svg"

# 统一黑灰夜间模式极简风格
NIGHT_GLASS_STYLE = """
    QWidget { font-family: "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Microsoft YaHei", sans-serif; color: #e0e0e0; }
    QFrame#RootFrame { background-color: rgba(20, 20, 22, 240); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); }
    QFrame#PreviewArea { background-color: rgba(30, 30, 32, 150); border-top-left-radius: 12px; border-bottom-left-radius: 12px; border-right: 1px solid rgba(255, 255, 255, 0.05); }
    
    QLabel#SectionTitle { color: #888888; font-size: 12px; font-weight: bold; padding-left: 5px; margin-top: 15px; margin-bottom: 2px; letter-spacing: 1px; background: transparent; }
    
    QLineEdit, QComboBox, QSpinBox { 
        background-color: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.1); 
        border-radius: 6px; padding: 6px 10px; color: #ffffff; font-weight: bold;
    }
    QLineEdit:focus, QSpinBox:focus { border: 1px solid rgba(255, 255, 255, 0.3); background-color: rgba(0, 0, 0, 0.5); }
    QComboBox::drop-down { border: none; }
    
    QSpinBox::up-button, QSpinBox::down-button { width: 0px; height: 0px; border: none; } /* 隐藏原生上下箭头，保持极简 */
    
    QPushButton.PrimaryBtn { background-color: #ffffff; color: #ffffff; border-radius: 8px; padding: 8px 16px; font-weight: bold; border: none; }
    QPushButton.PrimaryBtn:hover { background-color: #e0e0e0; }
    QPushButton.PrimaryBtn:pressed { background-color: #c0c0c0; }
    
    QPushButton.SecondaryBtn { background-color: rgba(255, 255, 255, 0.05); color: #e0e0e0; border-radius: 8px; padding: 6px 12px; border: 1px solid rgba(255, 255, 255, 0.1); font-weight: bold; font-size: 12px;}
    QPushButton.SecondaryBtn:hover { background-color: rgba(255, 255, 255, 0.1); color: #ffffff; }
    
    QPushButton.IconBtn { background-color: rgba(255, 255, 255, 0.05); color: #e0e0e0; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.1); font-weight: bold; }
    QPushButton.IconBtn:hover { background-color: rgba(255, 255, 255, 0.15); color: #ffffff; }
    
    QPushButton.DangerBtn { background-color: transparent; color: #ff453a; border-radius: 8px; padding: 8px 16px; border: 1px solid rgba(255, 69, 58, 0.4); font-weight: bold; }
    QPushButton.DangerBtn:hover { background-color: rgba(255, 69, 58, 0.15); }
    
    QScrollBar:vertical, QScrollBar:horizontal { background-color: transparent; width: 6px; height: 6px; margin: 0px; }
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background-color: rgba(255, 255, 255, 0.2); border-radius: 3px; }
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background-color: rgba(255, 255, 255, 0.3); }
"""

# ================= 定制化 UI 组件 =================

def create_svg_icon_label(icon_filename, size=24, color="#ffffff"):
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background: transparent;")
    icon_path = os.path.join(DIR_ASSETS_SVG, icon_filename)
    if os.path.exists(icon_path):
        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            svg_content = svg_content.replace('currentColor', color).replace('stroke="#000"', f'stroke="{color}"').replace('stroke="#000000"', f'stroke="{color}"')
            renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            lbl.setPixmap(pixmap)
        except Exception as e:
            logger.error(f"SVG 渲染失败: {e}")
    return lbl

class WindowControls(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 0, 15)
        layout.setSpacing(10)
        self.close_btn = self._create_btn("#ff453a", "#ff6b62", self.window.close)
        self.min_btn = self._create_btn("#ffd60a", "#ffdf33", self.window.showMinimized)
        self.max_btn = self._create_btn("#32d74b", "#5ce670", self.toggle_maximize)
        layout.addWidget(self.close_btn)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addStretch()

    def _create_btn(self, color, hover_color, action):
        btn = QPushButton()
        btn.setFixedSize(14, 14)
        btn.setStyleSheet(f"QPushButton {{ background-color: {color}; border-radius: 7px; border: none; }} QPushButton:hover {{ background-color: {hover_color}; }}")
        btn.clicked.connect(action)
        return btn

    def toggle_maximize(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()

class SwitchControl(QWidget):
    toggled = Signal(bool)
    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = checked
        self._thumb_pos = 2 if not checked else 22
        self.anim = QPropertyAnimation(self, b"thumb_pos")
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(float)
    def thumb_pos(self): return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._thumb_pos = 22 if checked else 2
            self.update()

    def isChecked(self): return self._checked

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.anim.setStartValue(self._thumb_pos)
            self.anim.setEndValue(22 if self._checked else 2)
            self.anim.start()
            self.toggled.emit(self._checked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor("#34c759") if self._checked else QColor(80, 80, 80, 180)
        p.setBrush(bg_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(self._thumb_pos, 2, 20, 20)

class ColorPickerBtn(QPushButton):
    color_changed = Signal(str)
    def __init__(self, color_hex="#ffffff", parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.pick_color)
        self.update_style()

    def set_color(self, hex_str):
        self.color_hex = hex_str
        self.update_style()

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.color_hex), self, "选择颜色")
        if c.isValid():
            self.color_hex = c.name()
            self.update_style()
            self.color_changed.emit(self.color_hex)

    def update_style(self):
        self.setStyleSheet(f"background-color: {self.color_hex}; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px;")

class SettingsGroup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setStyleSheet("SettingsGroup { background-color: rgba(35, 35, 35, 140); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.08); }")

class SettingsRow(QFrame):
    def __init__(self, title, desc, control_widget, is_last=False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; background: transparent;")
        text_layout.addWidget(title_lbl)
        
        self.desc_lbl = None
        if desc:
            self.desc_lbl = QLabel(desc)
            self.desc_lbl.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
            text_layout.addWidget(self.desc_lbl)
            
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(control_widget)
        
        if not is_last: self.setStyleSheet("SettingsRow { border-bottom: 1px solid rgba(255, 255, 255, 0.06); background: transparent; }")
        else: self.setStyleSheet("SettingsRow { border: none; background: transparent; }")

class SliderSettingsRow(QFrame):
    def __init__(self, title, desc, slider, val_label, is_last=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)
        top_layout = QHBoxLayout()
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; background: transparent;")
        text_layout.addWidget(title_lbl)
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
            text_layout.addWidget(desc_lbl)
        top_layout.addLayout(text_layout)
        top_layout.addStretch()
        if val_label:
            val_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; background: transparent;")
            top_layout.addWidget(val_label)
        layout.addLayout(top_layout)
        
        slider.setStyleSheet("""
            QSlider { background: transparent; }
            QSlider::groove:horizontal { height: 6px; background: rgba(0, 0, 0, 0.3); border-radius: 3px; }
            QSlider::handle:horizontal { background: #ffffff; width: 18px; margin: -6px 0; border-radius: 9px; border: 2px solid rgba(40,40,40,200); }
            QSlider::handle:horizontal:hover { background: #e0e0e0; }
        """)
        layout.addWidget(slider)
        if not is_last: self.setStyleSheet("SliderSettingsRow { border-bottom: 1px solid rgba(255, 255, 255, 0.06); background: transparent; }")
        else: self.setStyleSheet("SliderSettingsRow { border: none; background: transparent; }")

def create_spin_box(val, vmin, vmax, callback, special_text=None):
    sb = QSpinBox()
    sb.setRange(vmin, vmax)
    if special_text:
        sb.setSpecialValueText(special_text)
    sb.setValue(int(val))
    sb.setMinimumWidth(60)
    sb.setMaximumWidth(75)
    sb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    sb.valueChanged.connect(callback)
    return sb

# ================= 核心编辑器主窗口 =================

class EditorWindow(QWidget):
    saved_signal = Signal()
    deleted_signal = Signal()

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.generator = ImageGenerator()
        self.config = self.load_config()
        self.dragPos = QPoint()
        
        self.setWindowTitle(f"表情编辑器 - {self.config.get('name', '未命名')}")
        self.resize(1150, 800)
        self.setMinimumSize(950, 600)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.root_frame = QFrame(self)
        self.root_frame.setObjectName("RootFrame")
        self.root_frame.setStyleSheet(NIGHT_GLASS_STYLE)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.root_frame)
        
        self.init_ui()
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render_preview)
        
        self.trigger_render()

    # ================= 完美修复：重新接管无边框窗口拖拽事件 =================
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()
    # =====================================================================

    def load_config(self):
        path = os.path.join(self.folder_path, "config.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data["_folder_path"] = self.folder_path
                
                if "overlay_image" in data and "overlays" not in data:
                    if data["overlay_image"]:
                        data["overlays"] = [{
                            "image": data["overlay_image"],
                            "x": data.get("overlay_x", 0),
                            "y": data.get("overlay_y", 0),
                            "w": data.get("overlay_w", 0),
                            "h": data.get("overlay_h", 0),
                            "z": data.get("overlay_z", 2),
                            "rotation": 0
                        }]
                    for old_key in ["overlay_image", "overlay_x", "overlay_y", "overlay_w", "overlay_h", "overlay_z"]:
                        data.pop(old_key, None)

                return data
        return {"name": "新表情", "hotkey": "", "is_enabled": True, "_folder_path": self.folder_path}

    def init_ui(self):
        layout = QHBoxLayout(self.root_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        preview_panel = QFrame()
        preview_panel.setObjectName("PreviewArea")
        preview_panel.setFixedWidth(550)
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 25)
        
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 20, 0)
        window_controls = WindowControls(self)
        title_layout.addWidget(window_controls)
        title_layout.addSpacing(10)
        
        title_layout.addWidget(create_svg_icon_label("database.svg", 18, "#ffffff"))
        
        title_label = QLabel("表情数据流渲染器")
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; background: transparent;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: rgba(10, 10, 12, 200); border-radius: 12px; border: 1px solid rgba(255,255,255,0.03); margin: 0 25px;")
        
        preview_layout.addLayout(title_layout)
        preview_layout.addSpacing(15)
        preview_layout.addWidget(self.preview_label, 1)

        control_scroll = QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setFrameShape(QFrame.NoFrame)
        control_scroll.setStyleSheet("background: transparent;")
        
        control_content = QWidget()
        self.layout_controls = QVBoxLayout(control_content)
        self.layout_controls.setContentsMargins(20, 20, 20, 30)
        self.layout_controls.setSpacing(25)
        
        header = QLabel("核心参数配置")
        header.setFont(QFont("Microsoft YaHei", 22, QFont.Bold))
        header.setStyleSheet("color: #ffffff; background: transparent; letter-spacing: 1px;")
        self.layout_controls.addWidget(header)

        self._build_group_basic()
        self._build_group_text_layout()
        self._build_group_text_style()
        self._build_group_box()
        self._build_group_overlays()

        btn_layout = QHBoxLayout()
        self.del_btn = QPushButton("销毁此表情")
        self.del_btn.setProperty("class", "DangerBtn")
        self.del_btn.clicked.connect(self.delete_emote)
        
        self.save_btn = QPushButton("保存全部更改")
        self.save_btn.setProperty("class", "PrimaryBtn")
        self.save_btn.setFixedSize(160, 44)
        self.save_btn.clicked.connect(self.save_and_close)
        
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        
        self.layout_controls.addSpacing(20)
        self.layout_controls.addLayout(btn_layout)
        self.layout_controls.addStretch()

        control_scroll.setWidget(control_content)
        layout.addWidget(preview_panel)
        layout.addWidget(control_scroll)

    def _build_group_basic(self):
        lbl = QLabel("基础状态与底图")
        lbl.setObjectName("SectionTitle")
        self.layout_controls.addWidget(lbl)
        
        g = SettingsGroup()
        self.name_input = QLineEdit(self.config.get("name", ""))
        self.name_input.setMinimumWidth(100)
        self.name_input.setMaximumWidth(160)
        self.name_input.textChanged.connect(lambda t: self.update_cfg("name", t))
        
        self.hk_input = QLineEdit(self.config.get("hotkey", ""))
        self.hk_input.setMinimumWidth(100)
        self.hk_input.setMaximumWidth(160)
        self.hk_input.textChanged.connect(lambda t: self.update_cfg("hotkey", t))
        
        self.enable_switch = SwitchControl(checked=self.config.get("is_enabled", True))
        self.enable_switch.toggled.connect(lambda s: self.update_cfg("is_enabled", s))
        
        bg_btn = QPushButton("替换底图...")
        bg_btn.setProperty("class", "SecondaryBtn")
        bg_btn.clicked.connect(self.change_base_image)
        
        current_base = self.config.get("base_image", "")
        base_path = os.path.join(self.folder_path, current_base) if current_base else ""
        if current_base and os.path.exists(base_path):
            current_base_text = current_base
        else:
            current_base_text = "无 / 文件丢失"
            
        self.base_img_row = SettingsRow("当前底图 (Base)", f"当前: {current_base_text}", bg_btn)
        
        g.layout.addWidget(SettingsRow("表情包名称", "识别与记忆", self.name_input))
        g.layout.addWidget(SettingsRow("独立装填键", "快捷键绑定", self.hk_input))
        g.layout.addWidget(self.base_img_row)
        g.layout.addWidget(SettingsRow("启用此表情", "是否响应快捷键装填", self.enable_switch, is_last=True))
        self.layout_controls.addWidget(g)

    def _build_group_text_layout(self):
        lbl = QLabel("文本容器与排版")
        lbl.setObjectName("SectionTitle")
        self.layout_controls.addWidget(lbl)
        
        g = SettingsGroup()
        self.content_input = QLineEdit(self.config.get("test_text", "预览文字"))
        self.content_input.setMinimumWidth(120)
        self.content_input.setMaximumWidth(180)
        self.content_input.textChanged.connect(lambda t: [self.update_cfg("test_text", t), self.trigger_render()])
        
        align_cb = QComboBox()
        align_cb.addItems(["center", "left", "right"])
        align_cb.setCurrentText(self.config.get("text_align", "center"))
        align_cb.currentTextChanged.connect(lambda t: self.update_cfg("text_align", t))
        
        valign_cb = QComboBox()
        valign_cb.addItems(["bottom", "middle", "top"])
        valign_cb.setCurrentText(self.config.get("valign", "bottom"))
        valign_cb.currentTextChanged.connect(lambda t: self.update_cfg("valign", t))
        
        coord_widget = QWidget()
        cl = QGridLayout(coord_widget)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(5)
        
        bx = create_spin_box(self.config.get("box_x", 0), -1000, 2000, lambda v: self.update_cfg("box_x", v))
        by = create_spin_box(self.config.get("box_y", 0), -1000, 2000, lambda v: self.update_cfg("box_y", v))
        bw = create_spin_box(self.config.get("box_w", 0), 0, 3000, lambda v: self.update_cfg("box_w", v), "满宽")
        bh = create_spin_box(self.config.get("box_h", 0), 0, 3000, lambda v: self.update_cfg("box_h", v), "满高")
        
        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#a0a0a0; font-size:12px; background:transparent;")
            return l
            
        cl.addWidget(_lbl("X:"), 0, 0); cl.addWidget(bx, 0, 1)
        cl.addWidget(_lbl("Y:"), 0, 2); cl.addWidget(by, 0, 3)
        cl.addWidget(_lbl("宽:"), 1, 0); cl.addWidget(bw, 1, 1)
        cl.addWidget(_lbl("高:"), 1, 2); cl.addWidget(bh, 1, 3)
        
        g.layout.addWidget(SettingsRow("测试预览文本", "输入文字查看排版效果", self.content_input))
        g.layout.addWidget(SettingsRow("水平/垂直对齐", "文本在容器内的吸附方向", align_cb))
        g.layout.addWidget(SettingsRow("", "", valign_cb))
        g.layout.addWidget(SettingsRow("文本容器边界 (Box)", "设定文字允许绘制的区域坐标", coord_widget, is_last=True))
        self.layout_controls.addWidget(g)

    def _build_group_text_style(self):
        lbl = QLabel("字体样式渲染")
        lbl.setObjectName("SectionTitle")
        self.layout_controls.addWidget(lbl)
        
        g = SettingsGroup()
        
        def rgb_to_hex(rgb):
            if isinstance(rgb, str): return rgb
            if isinstance(rgb, list) and len(rgb) >= 3: return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            return "#ffffff"
            
        tc = ColorPickerBtn(rgb_to_hex(self.config.get("text_color", [255,255,255])))
        tc.color_changed.connect(lambda c: self.update_cfg("text_color", c))
        
        sc = ColorPickerBtn(rgb_to_hex(self.config.get("stroke_color", [0,0,0])))
        sc.color_changed.connect(lambda c: self.update_cfg("stroke_color", c))
        
        color_w = QWidget()
        cl = QHBoxLayout(color_w)
        cl.setContentsMargins(0,0,0,0)
        cl.addWidget(QLabel("主体色:"))
        cl.addWidget(tc)
        cl.addSpacing(15)
        cl.addWidget(QLabel("描边色:"))
        cl.addWidget(sc)
        
        g.layout.addWidget(SettingsRow("字体基础色彩", "可被语法高亮规则覆盖", color_w))
        
        def mk_slider_row(title, key, rng, def_val):
            lbl = QLabel(f"{self.config.get(key, def_val)}")
            sl = QSlider(Qt.Horizontal)
            sl.setRange(*rng)
            sl.setValue(self.config.get(key, def_val))
            sl.valueChanged.connect(lambda v: [lbl.setText(str(v)), self.update_cfg(key, v)])
            return SliderSettingsRow(title, "", sl, lbl)
            
        f_lbl = QLabel(f"{self.config.get('font_size', 0)}")
        f_sl = QSlider(Qt.Horizontal)
        f_sl.setRange(0, 200)
        f_sl.setValue(self.config.get('font_size', 0))
        f_sl.valueChanged.connect(lambda v: [f_lbl.setText("自适应" if v==0 else str(v)), self.update_cfg("font_size", v)])
        if self.config.get('font_size', 0) == 0: f_lbl.setText("自适应")
        
        g.layout.addWidget(SliderSettingsRow("固定字号 (0为弹性)", "文字大小限制", f_sl, f_lbl))
        g.layout.addWidget(mk_slider_row("描边厚度 (px)", "stroke_width", (0, 20), 3))
        g.layout.addWidget(mk_slider_row("字间距", "letter_spacing", (-10, 50), 0))
        g.layout.addWidget(mk_slider_row("行间距", "line_spacing", (-20, 100), 4))
        
        rot_lbl = QLabel(f"{self.config.get('text_rotation', 0)}°")
        rot_sl = QSlider(Qt.Horizontal)
        rot_sl.setRange(-180, 180)
        rot_sl.setValue(self.config.get('text_rotation', 0))
        rot_sl.valueChanged.connect(lambda v: [rot_lbl.setText(f"{v}°"), self.update_cfg("text_rotation", v)])
        g.layout.addWidget(SliderSettingsRow("整体旋转角度", "文字整体倾斜", rot_sl, rot_lbl))
        
        it_sw = SwitchControl(checked=self.config.get("is_italic", False))
        it_sw.toggled.connect(lambda s: self.update_cfg("is_italic", s))
        
        un_sw = SwitchControl(checked=self.config.get("is_underline", False))
        un_sw.toggled.connect(lambda s: self.update_cfg("is_underline", s))
        
        sw_w = QWidget()
        sw_l = QHBoxLayout(sw_w)
        sw_l.setContentsMargins(0,0,0,0)
        sw_l.addWidget(QLabel("斜体"))
        sw_l.addWidget(it_sw)
        sw_l.addSpacing(20)
        sw_l.addWidget(QLabel("下划线"))
        sw_l.addWidget(un_sw)
        
        g.layout.addWidget(SettingsRow("附加特效", "斜体计算会有略微偏移", sw_w, is_last=True))
        self.layout_controls.addWidget(g)

    def _build_group_box(self):
        lbl = QLabel("文本容器背景调试")
        lbl.setObjectName("SectionTitle")
        self.layout_controls.addWidget(lbl)
        
        g = SettingsGroup()
        box_sw = SwitchControl(checked=self.config.get("show_box", False))
        box_sw.toggled.connect(lambda s: self.update_cfg("show_box", s))
        g.layout.addWidget(SettingsRow("渲染文本边界框", "用于调试或作为实心背景垫", box_sw, is_last=True))
        
        self.layout_controls.addWidget(g)

    def _build_group_overlays(self):
        lbl = QLabel("独立渲染图层 (Overlays)")
        lbl.setObjectName("SectionTitle")
        self.layout_controls.addWidget(lbl)
        
        self.group_ov = SettingsGroup()
        self.ov_layout = QVBoxLayout()
        self.ov_layout.setContentsMargins(15, 15, 15, 15)
        self.ov_layout.setSpacing(15)
        self.group_ov.layout.addLayout(self.ov_layout)
        
        self.refresh_layer_list()
        
        add_btn = QPushButton("+ 导入新元件图层")
        add_btn.setStyleSheet("background-color: transparent; color: #ffffff; border-top: 1px solid rgba(255,255,255,0.06); padding: 12px; font-weight: bold; font-size: 13px;")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.add_overlay_file)
        self.group_ov.layout.addWidget(add_btn)
        
        self.layout_controls.addWidget(self.group_ov)

    # ---------------- 业务逻辑与图层管理 ----------------

    def change_base_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选取新底图", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            file_name = os.path.basename(file_path)
            target_path = os.path.join(self.folder_path, file_name)
            
            try:
                shutil.copy(file_path, target_path)
            except shutil.SameFileError:
                pass
            except Exception as e:
                logger.warning(f"底图拷贝失败: {e}")
                
            self.config["base_image"] = file_name
            if hasattr(self, 'base_img_row') and hasattr(self.base_img_row, 'desc_lbl'):
                self.base_img_row.desc_lbl.setText(f"当前: {file_name}")
            self.trigger_render()

    def update_cfg(self, key, value):
        self.config[key] = value
        self.trigger_render()

    def trigger_render(self):
        self.render_timer.start(50) 

    def update_overlay(self, idx, key, val, target_label=None):
        if "overlays" in self.config and idx < len(self.config["overlays"]):
            self.config["overlays"][idx][key] = val
            if key == "z" and target_label:
                target_label.setText(f"图层优先度: {val}")
            self.trigger_render()

    def move_overlay_up(self, index):
        if "overlays" in self.config and index > 0:
            self.config["overlays"][index], self.config["overlays"][index-1] = self.config["overlays"][index-1], self.config["overlays"][index]
            self.refresh_layer_list()
            self.trigger_render()

    def move_overlay_down(self, index):
        if "overlays" in self.config and index < len(self.config["overlays"]) - 1:
            self.config["overlays"][index], self.config["overlays"][index+1] = self.config["overlays"][index+1], self.config["overlays"][index]
            self.refresh_layer_list()
            self.trigger_render()

    def refresh_layer_list(self):
        while self.ov_layout.count():
            item = self.ov_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        overlays = self.config.get("overlays", [])
        if not overlays:
            no_lbl = QLabel("暂无独立图层")
            no_lbl.setStyleSheet("color: #71717a; font-style: italic;")
            self.ov_layout.addWidget(no_lbl)
            return

        for idx, ov in enumerate(overlays):
            card = QFrame()
            card.setStyleSheet("background: rgba(0,0,0,0.25); border-radius: 8px; border: 1px solid rgba(255,255,255,0.04); padding: 5px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 10, 10, 10)
            cl.setSpacing(10)
            
            top = QHBoxLayout()
            name_lbl = QLabel(f"📄 {ov.get('image', '未知元件')}")
            name_lbl.setStyleSheet("font-weight: bold; color: #e0e0e0; background: transparent; border: none;")
            
            z_lbl = QLabel(f"图层优先度: {ov.get('z', 2)}")
            z_lbl.setStyleSheet("font-size: 12px; color: #a0a0a0; border: none; background: transparent;")
            
            up_btn = QPushButton("↑")
            up_btn.setProperty("class", "IconBtn")
            up_btn.setFixedSize(24, 24)
            up_btn.clicked.connect(lambda _, i=idx: self.move_overlay_up(i))
            
            down_btn = QPushButton("↓")
            down_btn.setProperty("class", "IconBtn")
            down_btn.setFixedSize(24, 24)
            down_btn.clicked.connect(lambda _, i=idx: self.move_overlay_down(i))
            
            del_btn = QPushButton("移除")
            del_btn.setProperty("class", "DangerBtn")
            del_btn.setFixedSize(50, 24)
            del_btn.setStyleSheet("padding: 0; font-size: 11px;")
            del_btn.clicked.connect(lambda _, i=idx: self.remove_overlay(i))
            
            top.addWidget(name_lbl)
            top.addStretch()
            top.addWidget(z_lbl)
            top.addSpacing(10)
            top.addWidget(up_btn)
            top.addWidget(down_btn)
            top.addWidget(del_btn)
            cl.addLayout(top)
            
            grid = QGridLayout()
            grid.setContentsMargins(0,0,0,0)
            grid.setSpacing(6)
            
            def add_spin(row, col, label, key, rng=(-2000, 3000), special_text=None):
                lbl = QLabel(label)
                lbl.setStyleSheet("color:#a0a0a0; font-size:12px; background: transparent;")
                grid.addWidget(lbl, row, col*2)
                sb = create_spin_box(ov.get(key, 0), *rng, 
                                     lambda v, k=key, i=idx, zl=z_lbl: self.update_overlay(i, k, v, zl if k=='z' else None), 
                                     special_text)
                grid.addWidget(sb, row, col*2+1)

            add_spin(0, 0, "X:", "x")
            add_spin(0, 1, "Y:", "y")
            add_spin(0, 2, "优先度:", "z", (-10, 10))
            
            add_spin(1, 0, "宽:", "w", (0, 3000), "自适应")
            add_spin(1, 1, "高:", "h", (0, 3000), "自适应")
            add_spin(1, 2, "旋转:", "rotation", (-180, 180))
            
            cl.addLayout(grid)
            self.ov_layout.addWidget(card)

    def add_overlay_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选取图层元件图片", "", "Images (*.png *.jpg *.webp)")
        if file_path:
            file_name = os.path.basename(file_path)
            target_path = os.path.join(self.folder_path, file_name)
            
            try:
                shutil.copy(file_path, target_path)
            except shutil.SameFileError:
                pass
            except Exception as e:
                logger.error(f"图层拷贝失败: {e}")
            
            new_ov = {"image": file_name, "x": 0, "y": 0, "w": 0, "h": 0, "z": 2, "rotation": 0}
            if "overlays" not in self.config: self.config["overlays"] = []
            self.config["overlays"].append(new_ov)
            
            self.refresh_layer_list()
            self.trigger_render()

    def remove_overlay(self, index):
        if "overlays" in self.config and index < len(self.config["overlays"]):
            self.config["overlays"].pop(index)
            self.refresh_layer_list()
            self.trigger_render()

    def render_preview(self):
        try:
            base_img_name = self.config.get("base_image", "base.png")
            base_path = os.path.join(self.folder_path, base_img_name)
            if os.path.exists(base_path):
                base_pil = Image.open(base_path)
            else:
                base_pil = Image.new('RGB', (400, 300), (30, 30, 32))
                
            preview_text = self.config.get("test_text", "预览文字")
            
            temp_cfg = self.config.copy()
            for k in ["box_w", "box_h", "font_size"]:
                if temp_cfg.get(k) == "": temp_cfg[k] = 0
                
            result_pil = self.generator.generate(base_pil, preview_text, temp_cfg)
            
            if result_pil.mode == "RGB":
                r, g, b = result_pil.split()
                result_pil = Image.merge("RGB", (r, g, b))
            
            qimg = ImageQt.ImageQt(result_pil)
            pixmap = QPixmap.fromImage(qimg)
            
            scaled_pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"预览渲染出错: {e}")

    def save_and_close(self):
        save_data = self.config.copy()
        if "_folder_path" in save_data: del save_data["_folder_path"]
        if "test_text" in save_data: del save_data["test_text"]
        
        path = os.path.join(self.folder_path, "config.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
            
        logger.info(f"表情配置 [{self.config.get('name')}] 已成功保存。")
        self.saved_signal.emit()
        self.close()

    def delete_emote(self):
        reply = QMessageBox.question(self, "确认销毁", "此操作不可逆！\n将连同底图和元件彻底删除该表情，确定吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                shutil.rmtree(self.folder_path)
                logger.info(f"表情目录 [{self.folder_path}] 已彻底销毁。")
                self.deleted_signal.emit()
                self.close()
            except Exception as e:
                logger.error(f"销毁失败: {e}")
                QMessageBox.critical(self, "销毁失败", f"无法删除文件夹:\n{e}")