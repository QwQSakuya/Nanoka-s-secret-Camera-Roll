import os
import sys
import time
import shutil
import json
import logging
import html
import re
import keyboard
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                               QPushButton, QLineEdit, QGridLayout, QFrame, 
                               QScrollArea, QCheckBox, QSlider, QStackedWidget, 
                               QButtonGroup, QPlainTextEdit, QMainWindow, QMessageBox,
                               QSystemTrayIcon, QMenu, QStyle, QApplication, QDialog, QSizePolicy,
                               QComboBox, QColorDialog, QToolButton, QLayout)
from PySide6.QtCore import Qt, QPoint, QObject, Signal, Slot, Property, QPropertyAnimation, QEasingCurve, QSize, QByteArray, QUrl, QMimeData, QEvent, QTimer, QRect
from PySide6.QtGui import QFont, QCursor, QMouseEvent, QPixmap, QIcon, QColor, QPainter, QPainterPath, QDesktopServices, QImage, QPen, QMovie, QDrag, QLinearGradient, QImageReader
from PySide6.QtSvg import QSvgRenderer

from Ui.editor_window import EditorWindow
from Ui.floating_widget import FloatingHUD
from Ui.quick_search_popup import SavedEmoteQuickPopup

from Core.logger import logger
from Core.saved_emotes_mgr import SavedEmotesManager
from Core.emote_sender import copy_file_to_clipboard, paste_to_chat, IMAGE_EXTS, ALL_EXTS
from Core.clipboard_mgr import ClipboardManager
from Core.quick_search_engine import QuickSearchEngine

DIR_EMOTE_CONFIGS = "./EmoteConfigs"
DIR_CONFIGS = "./Configs"
DIR_LOGS = "./Logs"
DIR_FONTS = "./Fonts"
DIR_ASSETS_SVG = "./Assets/Svg"

for directory in [DIR_EMOTE_CONFIGS, DIR_CONFIGS, DIR_LOGS, DIR_FONTS, DIR_ASSETS_SVG]:
    os.makedirs(directory, exist_ok=True)

MAC_GLASS_STYLE = """
    QWidget { font-family: "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Microsoft YaHei", sans-serif; color: #e0e0e0; }
    QFrame#RootFrame { background-color: rgba(20, 20, 22, 230); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); }
    QFrame#Sidebar { background-color: rgba(30, 30, 32, 150); border-top-left-radius: 12px; border-bottom-left-radius: 12px; border-right: 1px solid rgba(255, 255, 255, 0.05); }
    
    QLabel#SectionTitle { color: #888888; font-size: 12px; font-weight: bold; padding-left: 8px; margin-top: 15px; margin-bottom: 2px; letter-spacing: 1px; background: transparent; }
    
    QPushButton.NavBtn { background-color: transparent; color: #a0a0a0; text-align: left; padding: 10px 12px; border-radius: 8px; font-size: 13px; font-weight: 500; border: none; }
    QPushButton.NavBtn:hover { background-color: rgba(255, 255, 255, 0.05); color: #ffffff; }
    QPushButton.NavBtn:checked { background-color: rgba(255, 255, 255, 0.1); color: #ffffff; font-weight: bold; }
    
    QLineEdit { background-color: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 10px 14px; color: #ffffff; }
    QLineEdit:focus { border: 1px solid rgba(255, 255, 255, 0.3); background-color: rgba(0, 0, 0, 0.5); }
    
    QPushButton.PrimaryBtn { background-color: #ffffff; color: #000000; border-radius: 8px; padding: 8px 16px; font-weight: bold; border: none; }
    QPushButton.PrimaryBtn:hover { background-color: #e0e0e0; }
    QPushButton.PrimaryBtn:pressed { background-color: #c0c0c0; }
    
    QPushButton.SecondaryBtn { background-color: rgba(255, 255, 255, 0.05); color: #e0e0e0; border-radius: 8px; padding: 8px 16px; border: 1px solid rgba(255, 255, 255, 0.1); }
    QPushButton.SecondaryBtn:hover { background-color: rgba(255, 255, 255, 0.1); color: #ffffff; }
    
    QScrollBar:vertical { background-color: transparent; width: 6px; margin: 0px; }
    QScrollBar::handle:vertical { background-color: rgba(255, 255, 255, 0.2); border-radius: 3px; min-height: 30px; }
    QScrollBar::handle:vertical:hover { background-color: rgba(255, 255, 255, 0.3); }
    
    QFrame#EmoteCard { background-color: rgba(40, 40, 40, 160); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); }
    QFrame#EmoteCard:hover { background-color: rgba(50, 50, 50, 180); border: 1px solid rgba(255, 255, 255, 0.1); }
    
    QPushButton#DelBtn { background-color: transparent; color: #888888; border-radius: 6px; padding: 6px 12px; font-size: 12px; font-weight: bold; }
    QPushButton#DelBtn:hover { background-color: rgba(255, 69, 58, 0.15); color: #ff453a; }
    QToolTip { color: #000000; background-color: rgba(240, 240, 240, 220); border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 4px 8px; font-size: 12px; }
"""

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

def get_external_resource_path(relative_path):
    """Get absolute path for external resources (supports both dev and frozen exe)."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(current_dir)
        
    return os.path.join(base_path, relative_path)

class SafeUIHandler(logging.Handler):
    """Thread-safe logging handler that bridges logging to UI signals."""
    def __init__(self, ui_signal):
        super().__init__()
        self.ui_signal = ui_signal
        self.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.ui_signal.emit(record.levelname, msg)
        except Exception:
            pass

class StreamToSignal(QObject):
    """Captures stray print() output and emits them as UI log signals."""
    new_log = Signal(str, str)
    
    def __init__(self, default_level="INFO"):
        super().__init__()
        self.default_level = default_level
        
    def write(self, text):
        text = text.strip()
        if not text:
            return
            
        match_full = re.match(r'^\[\d{2}:\d{2}:\d{2}\]\s*\[(.*?)\]\s*(.*)$', text)
        if match_full:
            self.new_log.emit(match_full.group(1).upper(), match_full.group(2))
        else:
            match_time_only = re.match(r'^\[\d{2}:\d{2}:\d{2}\]\s*(.*)$', text)
            if match_time_only:
                self.new_log.emit(self.default_level, match_time_only.group(1))
            else:
                self.new_log.emit(self.default_level, text)
                
    def flush(self):
        pass

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
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._thumb_pos = 22 if checked else 2
            self.update()

    def isChecked(self):
        return self._checked

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

class SettingsGroup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setStyleSheet("""
            SettingsGroup {
                background-color: rgba(35, 35, 35, 140);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)

class SettingsRow(QFrame):
    def __init__(self, title, desc, control_widget, is_last=False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(15)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; background: transparent;")
        text_layout.addWidget(title_lbl)
        
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 12px; color: #a0a0a0; background: transparent;")
            text_layout.addWidget(desc_lbl)
            
        layout.addLayout(text_layout)
        layout.addStretch()
        
        layout.addWidget(control_widget)
        
        if not is_last:
            self.setStyleSheet("SettingsRow { border-bottom: 1px solid rgba(255, 255, 255, 0.06); background: transparent; }")
        else:
            self.setStyleSheet("SettingsRow { border: none; background: transparent; }")

class SliderSettingsRow(QFrame):
    def __init__(self, title, desc, slider, val_label, is_last=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        
        top_layout = QHBoxLayout()
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
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
        
        if not is_last:
            self.setStyleSheet("SliderSettingsRow { border-bottom: 1px solid rgba(255, 255, 255, 0.06); background: transparent; }")
        else:
            self.setStyleSheet("SliderSettingsRow { border: none; background: transparent; }")

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
        c = QColorDialog.getColor(QColor(self.color_hex), self, "选择高亮颜色")
        if c.isValid():
            self.color_hex = c.name()
            self.update_style()
            self.color_changed.emit(self.color_hex)

    def update_style(self):
        self.setStyleSheet(f"background-color: {self.color_hex}; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px;")

class RuleRowWidget(QWidget):
    def __init__(self, rule_data=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["包裹模式", "前缀模式"])
        
        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("起 (如: 【)")
        
        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("止 (如: 】)")
        
        input_style = "background-color: rgba(0,0,0,0.3); color: #ffffff; border: 1px solid rgba(255,255,255,0.1); padding: 8px; border-radius: 6px; font-weight: bold;"
        self.type_combo.setStyleSheet(input_style)
        self.start_input.setStyleSheet(input_style)
        self.end_input.setStyleSheet(input_style)
        
        self.color_btn = ColorPickerBtn("#ffffff")
        
        self.del_btn = QPushButton("×")
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setStyleSheet("color: #ff453a; font-size: 18px; font-weight: bold; background: transparent; border: 1px solid rgba(255, 69, 58, 0.3); border-radius: 6px;")
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.clicked.connect(self.deleteLater)
        
        layout.addWidget(self.type_combo)
        layout.addWidget(self.start_input)
        layout.addWidget(self.end_input)
        layout.addWidget(self.color_btn)
        layout.addWidget(self.del_btn)
        
        self.type_combo.currentTextChanged.connect(self.on_type_change)
        
        if rule_data:
            idx = 1 if rule_data.get("type") == "prefix" else 0
            self.type_combo.setCurrentIndex(idx)
            self.start_input.setText(rule_data.get("start", ""))
            self.end_input.setText(rule_data.get("end", ""))
            self.color_btn.set_color(rule_data.get("color", "#ffffff"))
            self.on_type_change(self.type_combo.currentText())

    def on_type_change(self, text):
        if text == "前缀模式":
            self.end_input.clear()
            self.end_input.setEnabled(False)
            self.start_input.setPlaceholderText("前缀 (如: [伪证])")
        else:
            self.end_input.setEnabled(True)
            self.start_input.setPlaceholderText("起 (如: 【)")
            
    def get_data(self):
        return {
            "type": "prefix" if self.type_combo.currentIndex() == 1 else "enclose",
            "start": self.start_input.text().strip(),
            "end": self.end_input.text().strip() if self.type_combo.currentIndex() == 0 else "",
            "color": self.color_btn.color_hex
        }

class SyntaxHighlightDialog(QDialog):
    def __init__(self, initial_rules, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(540, 500)
        
        self.setStyleSheet("""
            QDialog { background: transparent; }
            QFrame#MainFrame { background-color: rgba(30, 30, 30, 230); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); }
            QLabel { color: #ffffff; font-family: "Microsoft YaHei"; background: transparent; }
            QLabel#Title { font-size: 18px; font-weight: bold; }
            QLabel#Desc { color: #a0a0a0; font-size: 13px; line-height: 1.5; }
            QPushButton.ModernBtn { border-radius: 8px; padding: 8px 20px; font-size: 13px; font-weight: bold; font-family: "Microsoft YaHei"; }
            QPushButton#SaveBtn { background-color: #ffffff; color: #000000; border: none; }
            QPushButton#SaveBtn:hover { background-color: #e0e0e0; }
            QPushButton#CancelBtn { background-color: rgba(255,255,255,0.05); color: #e0e0e0; border: 1px solid rgba(255,255,255,0.1); }
            QPushButton#CancelBtn:hover { background-color: rgba(255,255,255,0.1); color: #ffffff; }
            QPushButton#AddBtn { background-color: transparent; color: #ffffff; border: 1px dashed rgba(255,255,255,0.3); border-radius: 8px; padding: 12px; font-weight: bold; font-size: 14px; }
            QPushButton#AddBtn:hover { background-color: rgba(255, 255, 255, 0.1); border: 1px dashed #ffffff; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        frame = QFrame(self)
        frame.setObjectName("MainFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(30, 30, 30, 25)
        
        title = QLabel("关键词高亮与变色规则")
        title.setObjectName("Title")
        desc = QLabel("配置特殊的标点符号或前缀，自动改变生成的文字颜色。\n·包裹模式: 例如设置【】为紫色 -> 【反驳】自动变紫\n·前缀模式: 例如设置[伪证]为红色 -> [伪证]这是假的！")
        desc.setObjectName("Desc")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        self.scroll_content = QWidget()
        self.rules_layout = QVBoxLayout(self.scroll_content)
        self.rules_layout.setContentsMargins(0, 10, 10, 10)
        self.rules_layout.setSpacing(15)
        self.rules_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.scroll_content)
        
        if not initial_rules:
            self.add_rule({"type": "enclose", "start": "【", "end": "】", "color": "#ffffff"})
            self.add_rule({"type": "enclose", "start": "[", "end": "]", "color": "#ffffff"})
            self.add_rule({"type": "prefix", "start": "【伪证】", "end": "", "color": "#ff453a"})
            self.add_rule({"type": "prefix", "start": "[伪证]", "end": "", "color": "#ff453a"})
        else:
            for r in initial_rules:
                self.add_rule(r)
                
        add_btn = QPushButton("+ 添加新规则")
        add_btn.setObjectName("AddBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.add_rule())
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        save_btn = QPushButton("确定保存并生效")
        save_btn.setProperty("class", "ModernBtn")
        save_btn.setObjectName("SaveBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("class", "ModernBtn")
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        frame_layout.addWidget(title)
        frame_layout.addSpacing(5)
        frame_layout.addWidget(desc)
        frame_layout.addSpacing(15)
        frame_layout.addWidget(scroll)
        frame_layout.addWidget(add_btn)
        frame_layout.addSpacing(25)
        frame_layout.addLayout(btn_layout)
        
        layout.addWidget(frame)

    def add_rule(self, data=None):
        row = RuleRowWidget(data, self)
        self.rules_layout.addWidget(row)

    def get_rules(self):
        rules = []
        for i in range(self.rules_layout.count()):
            widget = self.rules_layout.itemAt(i).widget()
            if widget and isinstance(widget, RuleRowWidget):
                r = widget.get_data()
                if r["start"]: 
                    rules.append(r)
        return rules

class CloseConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 180)
        self.result_choice = 0 

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setObjectName("MainFrame")
        frame.setStyleSheet("""
            QFrame#MainFrame { background-color: rgba(25, 25, 28, 230); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); }
            QLabel#Title { color: #f4f4f5; font-size: 16px; font-weight: bold; font-family: "-apple-system", "Microsoft YaHei", sans-serif; background: transparent; }
            QLabel#Desc { color: #a1a1aa; font-size: 13px; font-family: "-apple-system", "Microsoft YaHei", sans-serif; background: transparent; }
            QPushButton.ModernBtn { border-radius: 8px; padding: 8px 16px; font-size: 13px; font-family: "-apple-system", "Microsoft YaHei", sans-serif; }
            QPushButton#TrayBtn { background-color: #ffffff; color: #000000; border: none; font-weight: bold; }
            QPushButton#TrayBtn:hover { background-color: #e0e0e0; }
            QPushButton#QuitBtn { background-color: transparent; color: #ff453a; border: 1px solid rgba(255, 69, 58, 0.4); }
            QPushButton#QuitBtn:hover { background-color: rgba(255, 69, 58, 0.15); }
            QPushButton#CancelBtn { background-color: rgba(255,255,255,0.05); color: #e0e0e0; border: 1px solid rgba(255,255,255,0.1); }
            QPushButton#CancelBtn:hover { background-color: rgba(255,255,255,0.1); color: #ffffff; }
        """)
        
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(30, 30, 30, 25)
        frame_layout.setSpacing(15)

        title = QLabel("退出确认")
        title.setObjectName("Title")
        
        desc = QLabel("关闭主界面后，您希望程序如何运行？")
        desc.setObjectName("Desc")

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_tray = QPushButton("缩小到托盘")
        btn_tray.setProperty("class", "ModernBtn")
        btn_tray.setObjectName("TrayBtn")
        btn_tray.setCursor(QCursor(Qt.PointingHandCursor))
        
        btn_quit = QPushButton("退出程序")
        btn_quit.setProperty("class", "ModernBtn")
        btn_quit.setObjectName("QuitBtn")
        btn_quit.setCursor(QCursor(Qt.PointingHandCursor))
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setProperty("class", "ModernBtn")
        btn_cancel.setObjectName("CancelBtn")
        btn_cancel.setCursor(QCursor(Qt.PointingHandCursor))

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_quit)
        btn_layout.addWidget(btn_tray)

        frame_layout.addWidget(title)
        frame_layout.addWidget(desc)
        frame_layout.addStretch()
        frame_layout.addLayout(btn_layout)

        layout.addWidget(frame)

        btn_tray.clicked.connect(self.choose_tray)
        btn_quit.clicked.connect(self.choose_quit)
        btn_cancel.clicked.connect(self.choose_cancel)

    def choose_tray(self):
        self.result_choice = 1
        self.accept()

    def choose_quit(self):
        self.result_choice = 2
        self.accept()

    def choose_cancel(self):
        self.result_choice = 0
        self.reject()


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

class EmoteCard(QFrame):
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    toggle_requested = Signal(str, bool)

    def __init__(self, config_data):
        super().__init__()
        self.setObjectName("EmoteCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title_text = config_data.get("name", "未命名表情")
        hotkey_text = config_data.get("hotkey", "未绑定")
        self.folder_path = config_data.get("_folder_path", "")
        img_name = config_data.get("base_image", "base.png")
        img_path = os.path.join(self.folder_path, img_name)
        is_enabled = config_data.get("is_enabled", True)
        
        self.img_label = QLabel()
        self.img_label.setFixedSize(150, 100)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background: transparent;")
        
        if os.path.exists(img_path):
            ext = os.path.splitext(img_path)[1].lower()
            if ext in ('.mp4', '.webm', '.avi', '.mov'):
                from Core.emote_sender import get_video_first_frame_pixmap
                pixmap = get_video_first_frame_pixmap(img_path, 150, 100)
            else:
                pixmap = QPixmap(img_path).scaled(150, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            if pixmap and not pixmap.isNull():
                self.img_label.setPixmap(pixmap)
                self.img_label.setStyleSheet("border-radius: 8px;")
            else:
                self.img_label.setText("无底图")
                self.img_label.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px; color: #888888;")
        else:
            self.img_label.setText("无底图")
            self.img_label.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px; color: #888888;")
            
        if not is_enabled: self.img_label.setGraphicsEffect(None) 
        
        title_label = QLabel(title_text)
        title_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff; background: transparent;" if is_enabled else "color: #71717a; background: transparent;")
        
        hotkey_label = QLabel(f"装填键: {hotkey_text}")
        hotkey_label.setStyleSheet("color: #a0a0a0; font-size: 11px; background: transparent;")
        
        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        
        switch_layout = QHBoxLayout()
        switch_layout.setSpacing(6)
        self.enable_switch = SwitchControl(checked=is_enabled)
        self.enable_switch.toggled.connect(lambda s: self.toggle_requested.emit(self.folder_path, s))
        
        enable_lbl = QLabel("启用")
        enable_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px; font-weight: bold; background: transparent;")
        
        switch_layout.addWidget(self.enable_switch)
        switch_layout.addWidget(enable_lbl)
        
        del_btn = QPushButton("删除")
        del_btn.setObjectName("DelBtn")
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.folder_path))
        
        edit_btn = QPushButton("编辑")
        edit_btn.setProperty("class", "SecondaryBtn")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.folder_path))
        
        bottom.addLayout(switch_layout)
        bottom.addStretch()
        bottom.addWidget(del_btn)
        bottom.addWidget(edit_btn)
        
        layout.addWidget(self.img_label, alignment=Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(title_label)
        layout.addWidget(hotkey_label)
        layout.addSpacing(8)
        layout.addLayout(bottom)


class GridFlowLayout:
    """轻量网格布局封装."""
    def __init__(self, container, spacing=14):
        self._container = container
        self._spacing = spacing
        self._layout = QGridLayout(container)
        self._layout.setContentsMargins(0, 10, 10, 20)
        self._layout.setSpacing(spacing)
        self._items = []
        self._orig_resize = container.resizeEvent
        container.resizeEvent = self._on_resize

    def _on_resize(self, event):
        if self._orig_resize:
            self._orig_resize(event)
        self._relayout()

    def addWidget(self, w):
        self._items.append(w)
        self._relayout()

    def clear_all(self):
        for w in self._items:
            w.hide()
            w.deleteLater()
        self._items.clear()
        self._relayout()

    def _relayout(self):
        while self._layout.count():
            self._layout.takeAt(0)
        container_width = self._container.width()
        if container_width < 100:
            container_width = 800
        col_w = SavedEmoteCard.CARD_W + self._spacing
        cols = max(1, (container_width - 20) // col_w)
        for i, w in enumerate(self._items):
            self._layout.addWidget(w, i // cols, i % cols)


class SavedEmoteCard(QFrame):
    CARD_W = 230
    BASE_H = 278

    def __init__(self, item_data, file_path, index, mgr):
        super().__init__()
        self.item_data = item_data
        self.file_path = file_path
        self._index = index
        self._mgr = mgr
        self.setObjectName("SavedEmoteCard")
        self._dynamic_h = self.BASE_H
        self.setFixedSize(self.CARD_W, self._dynamic_h)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(6)

        ext = os.path.splitext(file_path)[1].lower() if file_path else ""

        self._thumb = QLabel()
        self._thumb.setFixedSize(206, 130)
        self._thumb.setAlignment(Qt.AlignCenter)
        self._thumb.setStyleSheet("background: transparent;")
        self._gif_movie = None

        if file_path and os.path.exists(file_path):
            if ext in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'):
                reader = QImageReader(file_path)
                reader.setAutoTransform(True)
                orig = reader.size()
                if orig.isValid() and orig.width() > 0:
                    reader.setScaledSize(QSize(206, int(orig.height() * 206 / orig.width())))
                img = reader.read()
                if not img.isNull():
                    pix = QPixmap.fromImage(img)
                    if pix.height() > 130:
                        pix = pix.copy(0, (pix.height() - 130) // 2, 206, 130)
                    self._thumb.setPixmap(pix)
                else:
                    self._thumb.setText("🖼")
                    self._thumb.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px; color: #888888; font-size: 24px;")
                self._thumb.setStyleSheet("background-color: transparent; border-radius: 8px;")
            elif ext == '.gif':
                reader = QImageReader(file_path)
                orig = reader.size()
                self._gif_movie = QMovie(file_path)
                self._gif_movie.setCacheMode(QMovie.CacheAll)
                if orig.isValid() and orig.width() > 0:
                    ratio = 206 / orig.width()
                    self._gif_movie.setScaledSize(QSize(206, int(orig.height() * ratio)))
                else:
                    self._gif_movie.setScaledSize(QSize(206, 130))
                self._thumb.setMovie(self._gif_movie)
                self._gif_movie.jumpToFrame(0)  # 只显示首帧，不启动解码线程
            elif ext in ('.mp4', '.webm', '.avi', '.mov'):
                from Core.emote_sender import get_video_first_frame_pixmap
                pixmap = get_video_first_frame_pixmap(file_path, 206, 130)
                if pixmap and not pixmap.isNull():
                    self._thumb.setPixmap(pixmap)
                    self._thumb.setStyleSheet("background-color: transparent; border-radius: 8px;")
                else:
                    from Core.emote_sender import load_svg_pixmap
                    svg_pm = load_svg_pixmap("file-video-camera.svg", 48, 48)
                    if svg_pm:
                        self._thumb.setPixmap(svg_pm)
                        self._thumb.setStyleSheet("background-color: transparent; border-radius: 8px;")
                    else:
                        self._thumb.setText("🎬")
                        self._thumb.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px; color: rgba(255,255,255,0.4); font-size: 24px;")
            elif ext in ('.mp3', '.wav', '.ogg'):
                from Core.emote_sender import load_svg_pixmap
                svg_pm = load_svg_pixmap("audio-lines.svg", 48, 48)
                if svg_pm:
                    self._thumb.setPixmap(svg_pm)
                    self._thumb.setStyleSheet("background-color: transparent; border-radius: 8px;")
                else:
                    self._thumb.setText("🎵")
                    self._thumb.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px; color: rgba(255,255,255,0.4); font-size: 24px;")
        else:
            self._thumb.setText("?")
            self._thumb.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px; color: #888888; font-size: 24px;")

        display = item_data.get("display_name", "") or os.path.splitext(item_data.get("filename", "?"))[0]
        self._name_label = QLabel(self._trunc(display, 18))
        self._name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self._name_label.setStyleSheet("color: #ffffff; background: transparent;")

        folder = item_data.get("folder", "")
        self._path_label = QLabel(folder if folder else "SavedEmotes")
        self._path_label.setStyleSheet("color: #a0a0a0; font-size: 10px; background: transparent;")

        # ── Tag flow area ──
        self._tag_container = QWidget()
        self._tag_container.setStyleSheet("background: transparent;")
        self._tag_flow = FlowTagLayout(h_spacing=4, v_spacing=3)
        self._tag_container.setLayout(self._tag_flow)

        # ── Bottom buttons ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        rename_btn = QPushButton("重命名")
        rename_btn.setProperty("class", "SecondaryBtn")
        rename_btn.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_btn.clicked.connect(self._rename_card)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("DelBtn")
        del_btn.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self._delete_card)

        bottom.addStretch()
        bottom.addWidget(rename_btn)
        bottom.addWidget(del_btn)

        layout.addWidget(self._thumb, alignment=Qt.AlignCenter)
        layout.addWidget(self._name_label)
        layout.addWidget(self._path_label)
        layout.addWidget(self._tag_container)
        layout.addLayout(bottom)

        self._build_tags()

    def _trunc(self, s, n):
        return s[:n-1] + "…" if len(s) > n else s

    def _build_tags(self):
        self._tag_flow.clear()
        tags = self.item_data.get("tags", [])
        if not tags:
            add_btn = QPushButton("+")
            add_btn.setFixedSize(26, 22)
            add_btn.setStyleSheet("color: #a0a0a0; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 14px; font-weight: bold; border: none;")
            add_btn.setCursor(Qt.PointingHandCursor)
            add_btn.clicked.connect(self._add_tag)
            self._tag_flow.addWidget(add_btn)
            self._adjust_height()
            return

        if isinstance(tags[0], str):
            tags = [{"name": t, "color": "#66b2ff"} for t in tags]

        for ti, t in enumerate(tags):
            tag_name = t["name"] if isinstance(t, dict) else t
            tag_color = t.get("color", "#66b2ff") if isinstance(t, dict) else "#66b2ff"
            chip = TagChip(tag_name, tag_color, ti)
            idx = ti
            chip.clicked.connect(lambda i=idx: self._edit_single_tag(i))
            self._tag_flow.addWidget(chip)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(26, 22)
        add_btn.setStyleSheet("color: #a0a0a0; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 14px; font-weight: bold; border: none;")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_tag)
        self._tag_flow.addWidget(add_btn)

        self._adjust_height()

    def _adjust_height(self):
        self._tag_flow.invalidate()
        cw = self._tag_container.width()
        if cw < 40:
            cw = self.CARD_W - 24
        tag_h = self._tag_flow.heightForWidth(cw)
        self._dynamic_h = self.BASE_H + max(0, tag_h - 28)
        self.setFixedSize(self.CARD_W, self._dynamic_h)
        self._tag_container.setFixedHeight(tag_h)
        self._tag_flow.invalidate()
        self._tag_flow.activate()
        self.update()
        self.updateGeometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._adjust_height)

    def showEvent(self, e):
        super().showEvent(e)
        logger.debug(f"[TagCard] showEvent: item={self.item_data.get('id')}, card_w={self.width()}, visible={self.isVisible()}")
        QTimer.singleShot(0, self._adjust_height)

    def _add_tag(self):
        dlg = GlassNameDialog(self, "", "新建标签")
        if dlg.exec():
            name = dlg.result_name
            if name:
                tags = self.item_data.get("tags", []).copy()
                if tags and isinstance(tags[0], str):
                    tags = [{"name": t, "color": "#66b2ff"} for t in tags]
                tags.append({"name": name, "color": "#66b2ff"})
                self.item_data["tags"] = tags
                self._mgr.set_item_tags(self.item_data.get("id"), tags, folder_key=self.item_data.get("folder"))
                self._build_tags()

    def _edit_single_tag(self, idx):
        tags = self.item_data.get("tags", []).copy()
        if idx >= len(tags):
            return
        if isinstance(tags[idx], str):
            tags = [{"name": t, "color": "#66b2ff"} for t in tags]
        t = tags[idx]
        dlg = GlassTagDialog(self, t.get("name", ""), t.get("color", "#66b2ff"))
        if dlg.exec():
            if dlg.result_name:
                t["name"] = dlg.result_name
            t["color"] = dlg.result_color
            tags[idx] = t
            self.item_data["tags"] = tags
            self._mgr.set_item_tags(self.item_data.get("id"), tags, folder_key=self.item_data.get("folder"))
            self._build_tags()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and hasattr(self, '_drag_start'):
            delta = (e.position().toPoint() - self._drag_start).manhattanLength()
            if delta > 5:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(self.file_path)
                pix = self.grab()
                pix = pix.scaled(int(pix.width() * 0.8), int(pix.height() * 0.8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                drag.setPixmap(pix)
                drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))
                drag.setMimeData(mime)
                del self._drag_start
                drag.exec(Qt.MoveAction)
                return
        super().mouseMoveEvent(e)

    def _rename_card(self):
        current = self.item_data.get("display_name", "") or os.path.splitext(self.item_data.get("filename", ""))[0]
        dlg = GlassNameDialog(self, current, "重命名")
        if dlg.exec():
            new_name = dlg.result_name
            if new_name:
                self._mgr.rename_item(self.item_data.get("id"), new_name, folder_key=self.item_data.get("folder"))
                self._mgr._save_collection()
                self.item_data["display_name"] = new_name
                self._name_label.setText(self._trunc(new_name, 18))

    def _delete_card(self):
        from PySide6.QtWidgets import QMessageBox
        name = self.item_data.get("display_name") or self.item_data.get("filename", "")
        r = QMessageBox.question(self, "删除", f"确认删除「{name}」？\n文件将被永久删除。")
        if r == QMessageBox.Yes:
            self._mgr.delete_item(self.item_data.get("id"), folder_key=self.item_data.get("folder"))
            w = self
            while w:
                if hasattr(w, '_coll_refresh'):
                    w._coll_refresh()
                    break
                w = w.parent()

    def _cleanup_gif(self):
        """完全释放 GIF 资源"""
        if self._gif_movie:
            self._gif_movie.stop()
            self._gif_movie.setDevice(None)
            self._thumb.setMovie(None)
            self._gif_movie.deleteLater()
            self._gif_movie = None

    def stop_gif(self):
        if self._gif_movie:
            self._gif_movie.stop()

    def start_gif(self):
        if self._gif_movie:
            self._gif_movie.start()

    def enterEvent(self, e):
        """鼠标进入卡片时播放 GIF"""
        self.start_gif()
        super().enterEvent(e)

    def leaveEvent(self, e):
        """鼠标离开卡片时停止 GIF 并回到首帧"""
        if self._gif_movie:
            self._gif_movie.stop()
            self._gif_movie.jumpToFrame(0)
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.setPen(QPen(QColor(255, 255, 255, 10), 1))
        p.drawPath(path)


class FlowTagLayout(QLayout):
    """Proper QLayout-based flow layout for tags."""
    def __init__(self, parent=None, h_spacing=4, v_spacing=3):
        super().__init__(parent)
        self._hs = h_spacing
        self._vs = v_spacing
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)

    def addWidget(self, w):
        self._items.append(w)
        super().addWidget(w)

    def clear(self):
        while self._items:
            w = self._items.pop()
            self.removeWidget(w)
            w.deleteLater()

    def addItem(self, item):
        pass

    def count(self):
        return len(self._items)

    def itemAt(self, idx):
        return None

    def takeAt(self, idx):
        return None

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), dry=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect)

    def sizeHint(self):
        return QSize(100, 22)

    def minimumSize(self):
        return QSize(0, 6)

    def hasHeightForWidth(self):
        return True

    def _do_layout(self, rect, dry=False):
        x = rect.x()
        y = rect.y()
        row_h = 0
        for w in self._items:
            hint = w.sizeHint()
            min_sz = w.minimumSize()
            max_sz = w.maximumSize()
            item_w = hint.width()
            item_h = hint.height()
            if min_sz.width() > item_w:
                item_w = min_sz.width()
            if max_sz.width() < item_w and max_sz.width() > 0:
                item_w = max_sz.width()
            if min_sz.height() > item_h:
                item_h = min_sz.height()
            if max_sz.height() < item_h and max_sz.height() > 0:
                item_h = max_sz.height()
            sw = item_w + self._hs
            if x + sw > rect.right() and x > rect.x():
                x = rect.x()
                y += row_h + self._vs
                row_h = 0
            if not dry:
                w.setGeometry(QRect(x, y, item_w, item_h))
                if w.parentWidget() and w.parentWidget().isVisible():
                    w.show()
            x += sw
            if item_h > row_h:
                row_h = item_h
        total_h = y + row_h - rect.y()
        return max(total_h, 1)


class TagChip(QFrame):
    clicked = Signal()

    MAX_CHARS = 10

    def __init__(self, name, color, index):
        super().__init__()
        self.tag_name = name
        self.tag_color = color
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)
        self._index = index

        display = name if len(name) <= self.MAX_CHARS else name[:self.MAX_CHARS-1] + "…"
        lbl = QLabel(f"#{display}")
        lbl.setStyleSheet("color: #e0e0e0; font-size: 9px; font-weight: bold; background: transparent;")
        lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)
        layout.addWidget(lbl)
        layout.setSizeConstraint(QLayout.SetFixedSize)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, 0, 0)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)

        c = QColor(self.tag_color)
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        c.setAlpha(5)
        grad.setColorAt(0.0, c)
        c.setAlpha(128)
        grad.setColorAt(1.0, c)
        p.fillPath(path, grad)


class GlassDialogBase(QDialog):
    """毛玻璃弹窗基类 — 与主界面一致的颜色 + 可拖动."""

    BG_COLOR = QColor(20, 20, 22, 230)
    BORDER = QColor(255, 255, 255, 26)

    def __init__(self, parent, w=300, h=200):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(w, h)
        self._drag = False
        self._drag_pos = QPoint()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = True
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = False
        super().mouseReleaseEvent(e)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, 0, 0)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.fillPath(path, self.BG_COLOR)
        p.setPen(QPen(self.BORDER, 1))
        p.drawPath(path)


class GlassTagDialog(GlassDialogBase):
    def __init__(self, parent, tag_name, tag_color):
        super().__init__(parent, w=320, h=200)
        self.result_name = tag_name
        self.result_color = tag_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(self)
        frame.setObjectName("GlassDialog")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(20, 20, 20, 20)
        fl.setSpacing(12)

        name_label = QLabel("标签名")
        name_label.setStyleSheet("color: #a0a0a0; font-size: 11px; background: transparent;")
        self.name_edit = QLineEdit(tag_name)
        self.name_edit.setPlaceholderText("输入标签名...")
        self.name_edit.returnPressed.connect(self._apply)
        fl.addWidget(name_label)
        fl.addWidget(self.name_edit)

        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)
        color_label = QLabel("颜色")
        color_label.setStyleSheet("color: #a0a0a0; font-size: 11px; background: transparent;")
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(24, 24)
        self._color_preview.setStyleSheet(f"background-color: {tag_color}; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);")
        self._color_btn = QPushButton("选择颜色")
        self._color_btn.setProperty("class", "SecondaryBtn")
        self._color_btn.setStyleSheet("font-size: 10px; padding: 4px 10px;")
        self._color_btn.clicked.connect(self._pick_color)
        color_layout.addWidget(color_label)
        color_layout.addWidget(self._color_preview)
        color_layout.addStretch()
        color_layout.addWidget(self._color_btn)
        fl.addLayout(color_layout)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel = QPushButton("取消")
        cancel.setProperty("class", "SecondaryBtn")
        cancel.setStyleSheet("font-size: 10px; padding: 4px 14px;")
        cancel.clicked.connect(self.reject)
        ok_btn = QPushButton("确定")
        ok_btn.setProperty("class", "SecondaryBtn")
        ok_btn.setStyleSheet("font-size: 10px; padding: 4px 14px;")
        ok_btn.clicked.connect(self._apply)
        btn_row.addStretch()
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok_btn)
        fl.addLayout(btn_row)

        layout.addWidget(frame)

    def _pick_color(self):
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self.result_color), self)
        if color.isValid():
            self.result_color = color.name()
            self._color_preview.setStyleSheet(f"background-color: {self.result_color}; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);")

    def _apply(self):
        self.result_name = self.name_edit.text().strip()
        self.accept()


class GlassNameDialog(GlassDialogBase):
    def __init__(self, parent, current_name, title="重命名"):
        super().__init__(parent, w=320, h=140)
        self.result_name = current_name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(self)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(20, 20, 20, 20)
        fl.setSpacing(12)

        label = QLabel(title)
        label.setStyleSheet("color: #a0a0a0; font-size: 11px; background: transparent;")
        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("输入名称...")
        self.name_edit.selectAll()
        fl.addWidget(label)
        fl.addWidget(self.name_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel = QPushButton("取消")
        cancel.setProperty("class", "SecondaryBtn")
        cancel.setStyleSheet("font-size: 10px; padding: 4px 14px;")
        cancel.clicked.connect(self.reject)
        ok_btn = QPushButton("确定")
        ok_btn.setProperty("class", "SecondaryBtn")
        ok_btn.setStyleSheet("font-size: 10px; padding: 4px 14px;")
        ok_btn.clicked.connect(self._apply)
        btn_row.addStretch()
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok_btn)
        fl.addLayout(btn_row)

        layout.addWidget(frame)

    def _apply(self):
        self.result_name = self.name_edit.text().strip()
        self.accept()


class DragBackButton(QPushButton):
    folder_dropped = Signal(str, str)

    def __init__(self, text, parent_path):
        super().__init__(text)
        self.parent_path = parent_path
        self.setProperty("class", "NavBtn")
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        source = e.mimeData().text()
        if source:
            self.folder_dropped.emit(self.parent_path, source)


class DragFolderButton(QPushButton):
    """NavBtn 风格的文件夹按钮，接受拖放."""
    folder_dropped = Signal(str, str)

    def __init__(self, name, rel_path):
        super().__init__(f" {name}")
        self.rel_path = rel_path
        self.setProperty("class", "NavBtn")
        self.setCheckable(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        source = e.mimeData().text()
        if source:
            self.folder_dropped.emit(self.rel_path, source)


class MainWindow(QMainWindow):
    ui_log_signal = Signal(str, str) 

    def __init__(self, config_mgr=None, controller=None):
        super().__init__()
        self.config_mgr = config_mgr
        self.controller = controller
        self.active_editor = None 
        self.force_quit = False 
        
        self.saved_emotes_mgr = SavedEmotesManager()
        self.quick_search_engine = QuickSearchEngine(self.saved_emotes_mgr)
        self._quick_popup = None
        
        self.hud = FloatingHUD()
        
        self.setWindowTitle("Nanoka's Camera Roll")
        self.resize(1000, 720)
        self.setMinimumSize(850, 550)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.dragPos = QPoint() 

        self.root_frame = QFrame()
        self.root_frame.setObjectName("RootFrame")
        self.root_frame.setStyleSheet(MAC_GLASS_STYLE)
        self.setCentralWidget(self.root_frame)
        
        main_layout = QHBoxLayout(self.root_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 20)
        sidebar_layout.setSpacing(8)
        sidebar_layout.addWidget(WindowControls(self))
        
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        
        def add_section(title):
            lbl = QLabel(title)
            lbl.setObjectName("SectionTitle")
            sidebar_layout.addWidget(lbl)
            
        def load_stateful_svg_icon(icon_filename):
            icon = QIcon()
            icon_path = os.path.join(DIR_ASSETS_SVG, icon_filename)
            if not os.path.exists(icon_path):
                logger.warning(f"SVG icon not found: {icon_path}")
                return icon
                
            try:
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                    
                normal_svg = svg_content.replace('currentColor', '#a0a0a0').replace('stroke="#000"', 'stroke="#a0a0a0"').replace('stroke="#000000"', 'stroke="#a0a0a0"')
                active_svg = svg_content.replace('currentColor', '#ffffff').replace('stroke="#000"', 'stroke="#ffffff"').replace('stroke="#000000"', 'stroke="#ffffff"')
                
                render_size = QSize(24, 24)
                
                def svg_to_pixmap(svg_str):
                    renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
                    pixmap = QPixmap(render_size)
                    pixmap.fill(Qt.transparent)
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    renderer.render(painter)
                    painter.end()
                    return pixmap
                
                normal_pm = svg_to_pixmap(normal_svg)
                active_pm = svg_to_pixmap(active_svg)
                
                icon.addPixmap(normal_pm, QIcon.Normal, QIcon.Off)
                icon.addPixmap(active_pm, QIcon.Normal, QIcon.On)
                icon.addPixmap(active_pm, QIcon.Active, QIcon.Off)
                icon.addPixmap(active_pm, QIcon.Active, QIcon.On)
                
            except Exception as e:
                logger.error(f"[UI] SVG render failed: {e}, falling back to raw file")
                icon.addFile(icon_path)
                
            return icon
            
        def add_nav_btn(icon_filename, text, index):
            btn = QPushButton(f" {text}")
            btn.setProperty("class", "NavBtn")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            
            colored_icon = load_stateful_svg_icon(icon_filename)
            if not colored_icon.isNull():
                btn.setIcon(colored_icon)
                btn.setIconSize(QSize(18, 18))
                
            self.nav_group.addButton(btn, index)
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
            btn.clicked.connect(lambda _, idx=index: self.stacked_widget.setCurrentIndex(idx))

        nav_container = QWidget()
        nav_inner_layout = QVBoxLayout(nav_container)
        nav_inner_layout.setContentsMargins(15, 0, 15, 0)
        sidebar_layout.addWidget(nav_container)
        sidebar_layout = nav_inner_layout

        add_section("核心功能")
        add_nav_btn("diamond.svg", "主页", 0)
        add_nav_btn("image.svg", "生成表情管理", 1)
        add_nav_btn("database.svg", "奈叶香的相册", 4)
        
        add_section("系统与状态")
        add_nav_btn("square-terminal.svg", "运行日志", 2)
        
        add_section("偏好设置")
        add_nav_btn("settings-2.svg", "全局设置", 3)

        sidebar_layout.addStretch()
        self.nav_buttons[0].setChecked(True) 

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.create_home_page())
        
        self.emotes_page, self.emotes_grid_layout = self.create_emotes_page()
        self.stacked_widget.addWidget(self.emotes_page)
        
        self.stacked_widget.addWidget(self.create_logs_page())
        self.stacked_widget.addWidget(self.create_settings_page())

        self.collection_page = self.create_emotes_collection_page()
        self.stacked_widget.addWidget(self.collection_page)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stacked_widget)
        
        self.setup_system_tray()
        
        self.ui_log_signal.connect(self.append_ui_log)
        
        self.safe_ui_handler = SafeUIHandler(self.ui_log_signal)
        self.safe_ui_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self.safe_ui_handler)
        logging.getLogger("Sketchbook").addHandler(self.safe_ui_handler)
        
        self.stdout_redirector = StreamToSignal("INFO")
        self.stdout_redirector.new_log.connect(self.append_ui_log)
        sys.stdout = self.stdout_redirector
        
        self.stderr_redirector = StreamToSignal("ERROR")
        self.stderr_redirector.new_log.connect(self.append_ui_log)
        sys.stderr = self.stderr_redirector
        
        if self.config_mgr:
            self.hud.apply_config(self.config_mgr.global_settings)
            
        self.refresh_emotes_grid()

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        icon_path = get_external_resource_path(os.path.join("Assets", "Icon", "icon.ico"))
        
        self.tray_icon.setIcon(QIcon(icon_path))
        self.setWindowIcon(QIcon(icon_path))
        
        self.tray_icon.setToolTip("Sketchbook - 后台运行中")
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示主界面")
        show_action.triggered.connect(self.showNormal)
        
        quit_action = tray_menu.addAction("完全退出程序")
        quit_action.triggered.connect(self.full_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()


    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def full_quit(self):
        self.force_quit = True
        if self.controller:
            self.controller.stop_listening()
        self.hud.close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.force_quit:
            event.accept()
            return

        dialog = CloseConfirmDialog(self)
        dialog.exec()

        if dialog.result_choice == 1:
            self.hide()
            self.tray_icon.showMessage("Sketchbook", "已隐藏至系统托盘，监听引擎持续运行中。", QSystemTrayIcon.Information, 2000)
            event.ignore()
        elif dialog.result_choice == 2:
            self.full_quit()
            event.accept()
        else:
            event.ignore()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            child = self.childAt(event.position().toPoint())
            while child:
                if isinstance(child, SavedEmoteCard):
                    return
                child = child.parent()
            self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()

    def trigger_hud(self, emote_name, img_path):
        logger.debug(f"HUD trigger: {emote_name}")
        self.hud.show_emote(emote_name, img_path)

    def _on_quick_search_hotkey(self):
        logger.debug("[快速搜索] >>> 热键触发入口 <<<")
        self.saved_emotes_mgr.reload()
        cfg = self.config_mgr.global_settings if self.config_mgr else {}
        delay = cfg.get('quick_search_delay_ms', 150) / 1000.0
        try:
        # 模拟 Ctrl+C 同时保持用户 Ctrl 状态
            ctrl_was_held = keyboard.is_pressed('ctrl')
            if not ctrl_was_held:
                keyboard.press('ctrl')
            keyboard.press_and_release('c')
            if not ctrl_was_held:
                keyboard.release('ctrl')

            if delay > 0:
                time.sleep(delay)
            QApplication.processEvents()

            selected_text = ""
            try:
                raw = QApplication.clipboard().text()
                logger.debug(f"[快速搜索] 剪贴板文字: type={type(raw).__name__}, val={repr(raw)[:80] if raw else 'None'}")
                if raw and isinstance(raw, str):
                    if '\n' in raw or '\r' in raw:
                        logger.debug("[快速搜索] 剪贴板含换行符，非单行搜索格式，跳过")
                        return
                    selected_text = raw.strip()
            except Exception as e:
                logger.debug(f"[快速搜索] 读取剪贴板失败: {e}")

            if not selected_text:
                logger.debug("[快速搜索] 无选中文字，不弹窗 (仅 /* 等特殊格式会触发)")
                return

            logger.debug(f"[快速搜索] 选中文字: {repr(selected_text)[:60]}")
            parsed = self.quick_search_engine.parse_pattern(selected_text)
            if parsed is None:
                logger.debug("[快速搜索] 非特殊格式，不弹窗")
                return
            items = parsed["items"]
            fp = parsed.get("folder", "")
            logger.debug(f"[快速搜索] 解析结果: {len(items)} 项, folder={repr(fp)}")
            self._show_quick_popup(items, parsed.get("title", selected_text), folder_path=fp)
        except Exception:
            logger.exception("[快速搜索] 热键处理异常")
        finally:
            ClipboardManager.robust_clear()
    def _filter_items_by_text(self, items, text):
        """简单文字过滤 + 计分排序。"""
        return self.quick_search_engine.filter_items_by_text(items, text)

    def _destroy_old_popup(self):
        if self._quick_popup is not None:
            try:
                self._quick_popup.emote_selected.disconnect()
                self._quick_popup.folder_clicked.disconnect()
            except Exception:
                pass
            try:
                self._quick_popup.hide()
                self._quick_popup.deleteLater()
                QApplication.processEvents()
            except Exception:
                pass
            self._quick_popup = None

    def _list_subfolders_at(self, rel_path):
        """列出指定物理目录下的子文件夹."""
        return self.quick_search_engine.list_subfolders_at(rel_path)

    def _show_empty_quick_popup(self, hint):
        logger.debug(f"[快速搜索] _show_empty_quick_popup: {hint}")
        self._destroy_old_popup()
        self._quick_popup = SavedEmoteQuickPopup(self)
        self._quick_popup.emote_selected.connect(self._on_quick_emote_selected)
        self._quick_popup.folder_clicked.connect(self._on_quick_folder_clicked)
        self._quick_popup.set_title(f"未找到匹配 ({hint})")
        empty_row = QLabel("没有匹配的表情包")
        empty_row.setStyleSheet("color: #888888; font-size: 12px; background: transparent; padding: 20px;")
        empty_row.setAlignment(Qt.AlignCenter)
        self._quick_popup._content_layout.addWidget(empty_row)
        self._quick_popup.set_folders([], "")
        self._quick_popup.show_at_cursor()

    def _show_quick_popup(self, items, title_hint, folder_path=""):
        logger.debug(f"[快速搜索] _show_quick_popup: {title_hint}, {len(items)} 项, path={repr(folder_path)}")
        self._destroy_old_popup()
        self._quick_popup = SavedEmoteQuickPopup(self)
        self._quick_popup.emote_selected.connect(self._on_quick_emote_selected)
        self._quick_popup.folder_clicked.connect(self._on_quick_folder_clicked)
        self._quick_popup.set_title(f"表情检索 · {title_hint} ({len(items)}项)")
        subfolders = self._list_subfolders_at(folder_path)
        self._quick_popup.set_folders(subfolders, folder_path)
        items_sorted = sorted(items, key=lambda x: x.get("_score", 0), reverse=True)
        if items_sorted:
            for item in items_sorted:
                file_path = self.saved_emotes_mgr.get_item_path(item)
                self._quick_popup.add_item(item, file_path, self.saved_emotes_mgr)
        else:
            hint = QLabel("此目录无媒体文件" if subfolders else "没有匹配的表情包")
            hint.setStyleSheet("color: #888888; font-size: 12px; background: transparent; padding: 20px;")
            hint.setAlignment(Qt.AlignCenter)
            self._quick_popup._content_layout.addWidget(hint)
        self._quick_popup.show_at_cursor(len(items))

    def _on_quick_folder_clicked(self, rel_path):
        """侧栏文件夹被点击 → 用 QTimer 推迟重建，避免 deleteLater 竞态."""
        # 先记下要导航到的路径，等信号处理完毕后再执行
        QTimer.singleShot(0, lambda: self._do_navigate(rel_path))

    def _do_navigate(self, rel_path):
        """实际执行导航：销毁旧弹窗 → 扫描新路径 → 新建弹窗."""
        if self._quick_popup is None:
            return

        old_pos = self._quick_popup.pos()

        if rel_path == "__back__":
            old_path = self._quick_popup._current_path
            parent = os.path.dirname(old_path) if old_path else ""
            logger.info(f"[快速搜索] 返回上级文件夹: {parent or '根目录'}")
            items = self.saved_emotes_mgr.scan_physical_folder(parent)
            title = os.path.basename(parent) if parent else "SavedEmotes"
            self._show_quick_popup(items, title, folder_path=parent)
        else:
            logger.info(f"[快速搜索] 导航到子文件夹: {rel_path}")
            dirname = os.path.basename(rel_path)
            items = self.saved_emotes_mgr.scan_physical_folder(rel_path)
            self._show_quick_popup(items, dirname, folder_path=rel_path)

        if self._quick_popup is not None:
            self._quick_popup.move(old_pos)

    def _on_quick_emote_selected(self, file_path):
        logger.debug(f"[快速搜索] _on_quick_emote_selected: {file_path}")
        if not file_path or not os.path.exists(file_path):
            logger.debug(f"[快速搜索] 文件路径无效: {file_path}")
            return
        logger.info(f"[快速搜索] 用户选择了: {os.path.basename(file_path)}")
        cfg = self.config_mgr.global_settings if self.config_mgr else {}
        delay = cfg.get('delay_ms', 50)
        paste_to_chat(delay_ms=delay)
        logger.debug(f"[快速搜索] 粘贴指令已发送 (delay={delay}ms)")

    # ─── 表情包收集页面 ──────────────────────────────────────────

    def create_emotes_collection_page(self):
        self._coll_current = ""
        self._coll_cards = []
        self._coll_drag_source = None

        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 左侧文件夹面板 ──
        coll_sidebar = QFrame()
        coll_sidebar.setObjectName("Sidebar")
        coll_sidebar.setFixedWidth(160)
        coll_sidebar_layout = QVBoxLayout(coll_sidebar)
        coll_sidebar_layout.setContentsMargins(10, 20, 10, 20)
        coll_sidebar_layout.setSpacing(6)

        sd_title = QLabel("文件夹")
        sd_title.setObjectName("SectionTitle")
        sd_title.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold; padding-left: 8px; background: transparent;")
        coll_sidebar_layout.addWidget(sd_title)

        self._coll_back_btn = DragBackButton("← 返回上级", "__back__")
        self._coll_back_btn.folder_dropped.connect(self._coll_handle_drop)
        self._coll_back_btn.clicked.connect(lambda: self._coll_navigate("__back__"))
        coll_sidebar_layout.addWidget(self._coll_back_btn)

        self._coll_sidebar_list = QVBoxLayout()
        self._coll_sidebar_list.setSpacing(2)
        coll_sidebar_layout.addLayout(self._coll_sidebar_list)
        coll_sidebar_layout.addStretch()

        new_folder_btn = QPushButton("+ 新增文件夹")
        new_folder_btn.setProperty("class", "PrimaryBtn")
        new_folder_btn.setFixedHeight(34)
        new_folder_btn.setCursor(Qt.PointingHandCursor)
        new_folder_btn.clicked.connect(self._coll_new_folder)
        coll_sidebar_layout.addWidget(new_folder_btn)

        # ── 右侧主区域 ──
        right = QFrame()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(20, 30, 20, 20)
        right_l.setSpacing(12)

        top_row = QHBoxLayout()
        self._coll_bread = QLabel("SavedEmotes")
        self._coll_bread.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 16px; font-weight: bold; background: transparent;")
        self._coll_bread.setToolTip("SavedEmotes")
        top_row.addWidget(self._coll_bread)
        top_row.addStretch()
        self._coll_search = QLineEdit()
        self._coll_search.setPlaceholderText("搜索名称/tag=标签...")
        self._coll_search.setFixedWidth(260)
        self._coll_search.textChanged.connect(self._coll_refresh)
        top_row.addWidget(self._coll_search)

        # 搜索范围切换按钮：默认搜索全部，按下切换为搜索当前文件夹
        self._coll_search_all = True  # 默认搜索全部
        self._coll_search_scope_btn = QPushButton("全部")
        self._coll_search_scope_btn.setToolTip("点击切换为搜索当前文件夹")
        self._coll_search_scope_btn.setProperty("class", "SecondaryBtn")
        self._coll_search_scope_btn.setFixedWidth(70)
        self._coll_search_scope_btn.clicked.connect(self._toggle_coll_search_scope)
        top_row.addWidget(self._coll_search_scope_btn)

        folder_btn = QPushButton("打开目录")
        folder_btn.setProperty("class", "SecondaryBtn")
        folder_btn.clicked.connect(lambda: self._coll_open_dir())
        top_row.addWidget(folder_btn)
        right_l.addLayout(top_row)

        # 网格滚动区
        self._coll_scroll = QScrollArea()
        self._coll_scroll.setWidgetResizable(True)
        self._coll_scroll.setFrameShape(QFrame.NoFrame)
        self._coll_scroll.setStyleSheet("background: transparent;")
        self._coll_grid_container = QWidget()
        self._coll_grid_container.setStyleSheet("background: transparent;")
        self._coll_grid = GridFlowLayout(self._coll_grid_container, spacing=14)
        self._coll_scroll.setWidget(self._coll_grid_container)
        right_l.addWidget(self._coll_scroll)

        # 拖拽导入区
        drop_label = QLabel("将文件拖拽到此处导入")
        drop_label.setAlignment(Qt.AlignCenter)
        drop_label.setFixedHeight(44)
        drop_label.setStyleSheet("color: rgba(255,255,255,0.45); font-size: 13px; background: transparent; border: 2px dashed rgba(255,255,255,0.28); border-radius: 10px;")
        drop_label.setAcceptDrops(True)
        drop_label.dragEnterEvent = lambda e: e.acceptProposedAction() if e.mimeData().hasUrls() else None
        drop_label.dropEvent = self._coll_handle_drag_import
        right_l.addWidget(drop_label)

        outer.addWidget(coll_sidebar)
        outer.addWidget(right)

        self._coll_refresh()
        return page

    def _coll_open_dir(self):
        abs_path = os.path.join(self.saved_emotes_mgr.saved_emotes_dir, self._coll_current) if self._coll_current else self.saved_emotes_mgr.saved_emotes_dir
        if os.path.isdir(abs_path):
            os.startfile(abs_path)

    def _coll_handle_drag_import(self, event):
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            if fp:
                self.saved_emotes_mgr.import_file(fp, folder_key=self._coll_current)
        self._coll_refresh()

    def _toggle_coll_search_scope(self):
        """切换搜索范围：全部 / 当前文件夹。"""
        self._coll_search_all = not self._coll_search_all
        if self._coll_search_all:
            self._coll_search_scope_btn.setText("全部")
            self._coll_search_scope_btn.setToolTip("点击切换为搜索当前文件夹")
        else:
            self._coll_search_scope_btn.setText("当前")
            self._coll_search_scope_btn.setToolTip("点击切换为搜索全部")
        self._coll_refresh()

    def _coll_refresh(self):
        self.saved_emotes_mgr.reload()
        rel = self._coll_current
        items = self.saved_emotes_mgr.scan_physical_folder(rel)

        search = self._coll_search.text().strip()
        if search:
            # 根据搜索范围选择 folder_key：全部=None，当前文件夹=rel
            scope_key = None if self._coll_search_all else rel
            if 'tag=' in search.lower():
                items = self.saved_emotes_mgr.search_items(search, scope_key)
            else:
                if self._coll_search_all:
                    items = self.saved_emotes_mgr.get_items_in_folder(None)
                items = self._filter_items_by_text(items, search)

        # 先停止所有现有卡片的 GIF，防止后台线程残留导致卡顿
        for c in self._coll_cards:
            c.stop_gif()
        self._coll_grid.clear_all()
        self._coll_cards.clear()

        if rel:
            self._coll_bread.setText(f"… / {rel}")
            self._coll_bread.setToolTip(f"SavedEmotes / {rel}")
            self._coll_back_btn.show()
        else:
            self._coll_bread.setText("SavedEmotes")
            self._coll_bread.setToolTip("SavedEmotes")
            self._coll_back_btn.hide()

        self._coll_refresh_sidebar(rel)

        for i, it in enumerate(items):
            fp = self.saved_emotes_mgr.get_item_path(it)
            card = SavedEmoteCard(it, fp, i, self.saved_emotes_mgr)
            self._coll_grid.addWidget(card)
            self._coll_cards.append(card)

        self._coll_grid._relayout()

    def _coll_refresh_sidebar(self, rel):
        while self._coll_sidebar_list.count():
            w = self._coll_sidebar_list.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        QApplication.processEvents()

        subfolders = self._list_subfolders_at(rel)
        for name, child_rel in subfolders:
            item = DragFolderButton(name, child_rel)
            item.folder_dropped.connect(self._coll_handle_drop)
            item.clicked.connect(lambda checked, p=child_rel: self._coll_navigate(p))
            self._coll_sidebar_list.addWidget(item)

    def _coll_handle_drop(self, rel_target, source_file):
        """从卡片拖拽到文件夹/返回上级 → 移动文件."""
        if rel_target == "__back__":
            parent = os.path.dirname(self._coll_current) if self._coll_current else ""
            target = parent if parent else ""
        else:
            target = rel_target
        target_name = os.path.basename(target) if target else "SavedEmotes"
        for card in self._coll_cards:
            if card.file_path == source_file:
                item_id = card.item_data.get("id")
                if item_id:
                    self.saved_emotes_mgr.move_item(item_id, target)
                    logger.info(f"[收集] 移动文件到: {target_name}")
                    self._coll_refresh()
                break

    def _coll_navigate(self, rel):
        if rel == "__back__":
            parent = os.path.dirname(self._coll_current) if self._coll_current else ""
            self._coll_current = parent if parent else ""
        else:
            self._coll_current = rel
        self._coll_search.clear()
        self._coll_refresh()

    def _coll_new_folder(self):
        dlg = GlassNameDialog(self, "", "新建文件夹")
        if dlg.exec() and dlg.result_name:
            self.saved_emotes_mgr.create_folder(dlg.result_name)
            self._coll_refresh()

    def _coll_import_files(self):
        from PySide6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            self, "导入表情包文件", "",
            "媒体文件 (*.png *.jpg *.jpeg *.gif *.mp4 *.webp *.webm *.mp3 *.wav *.bmp *.tiff *.ogg *.avi *.mov)"
        )
        if files:
            for fp in files:
                self.saved_emotes_mgr.import_file(fp, folder_key=self._coll_current)
            self._coll_refresh()

    def create_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 50, 40, 40)
        
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        
        title = QLabel("欢迎来到 nnk的偷拍摄影集")
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ffffff; letter-spacing: 1px; background: transparent;")
        
        desc = QLabel("我去这是什么东西。\n我也不知道啊。")
        desc.setStyleSheet("color: #a0a0a0; font-size: 14px; line-height: 1.6; background: transparent;")
        desc.setAlignment(Qt.AlignCenter)
        
        github_link_layout = QHBoxLayout()
        github_link_layout.addStretch()
        
        github_btn = QPushButton("特别鸣谢：Anan's Sketchbook Chat Box")
        github_btn.setCursor(Qt.PointingHandCursor)
        github_btn.setStyleSheet("""
            QPushButton {
                color: #888888;
                background-color: transparent;
                font-size: 12px;
                text-decoration: underline;
                border: none;
                padding: 5px 10px;
                margin-right: 5px;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                color: #66b2ff;
            }
        """)
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/MarkCup-Official/Anan-s-Sketchbook-Chat-Box"))
        )
        github_link_layout.addWidget(github_btn)

        self.start_btn = QPushButton("载入后台监听系统")
        self.start_btn.setProperty("class", "PrimaryBtn")
        self.start_btn.setFixedSize(200, 44)
        self.start_btn.setCursor(QCursor(Qt.PointingHandCursor))

        def toggle_system():
            if not self.controller or not self.config_mgr: return
            if not self.controller.is_running:
                global_cfg = self.config_mgr.load_global_settings()
                self.controller.start_listening(
                    self.config_mgr.load_all_emotes(), 
                    global_cfg, 
                    self.trigger_hud,
                    self._on_quick_search_hotkey
                )
                self.start_btn.setText("关闭后台系统")
                self.start_btn.setStyleSheet("background-color: #34c759; color: #ffffff;")
            else:
                self.controller.stop_listening()
                self.start_btn.setText("载入后台监听系统")
                self.start_btn.setStyleSheet("")
                self.hud.fade_out()

        self.start_btn.clicked.connect(toggle_system)
        
        test_hud_btn = QPushButton("测试呼出指示器")
        test_hud_btn.setProperty("class", "SecondaryBtn")
        test_hud_btn.setFixedSize(200, 40)
        test_hud_btn.clicked.connect(lambda: self.trigger_hud("测试装填", ""))
        
        center_layout.addStretch()
        center_layout.addWidget(title)
        center_layout.addSpacing(15)
        center_layout.addWidget(desc)
        center_layout.addSpacing(35)
        center_layout.addStretch()
        
        layout.addWidget(center_widget)
        layout.addStretch()
        layout.addLayout(github_link_layout)
        
        return page

    def create_emotes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 40, 20, 0)
        
        top_bar = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索表情名称或快捷键...")
        self.search_box.setFixedWidth(260)
        self.search_box.textChanged.connect(self.refresh_emotes_grid)
        
        add_btn = QPushButton("新增表情")
        add_btn.setProperty("class", "PrimaryBtn")
        add_btn.clicked.connect(self.create_new_emote)
        
        folder_btn = QPushButton("打开目录")
        folder_btn.setProperty("class", "SecondaryBtn")
        folder_btn.clicked.connect(lambda: os.startfile(os.path.abspath(DIR_EMOTE_CONFIGS)))
        
        top_bar.addWidget(self.search_box)
        top_bar.addStretch()
        top_bar.addWidget(add_btn)
        top_bar.addWidget(folder_btn)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background-color: transparent;")
        
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background-color: transparent;")
        self.emotes_grid_layout = QGridLayout(grid_widget)
        self.emotes_grid_layout.setContentsMargins(0, 20, 10, 30)
        self.emotes_grid_layout.setSpacing(20)
        
        scroll_area.setWidget(grid_widget)
        
        layout.addLayout(top_bar)
        layout.addSpacing(10)
        layout.addWidget(scroll_area)
        return page, self.emotes_grid_layout

    def refresh_emotes_grid(self):
        while self.emotes_grid_layout.count():
            item = self.emotes_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if not self.config_mgr: return
        
        search_text = self.search_box.text().lower()
        emotes = self.config_mgr.load_all_emotes()
        
        display_idx = 0
        for emote_cfg in emotes:
            if search_text:
                name = emote_cfg.get("name", "").lower()
                hk = emote_cfg.get("hotkey", "").lower()
                if search_text not in name and search_text not in hk:
                    continue
            
            card = EmoteCard(emote_cfg)
            card.edit_requested.connect(self.open_editor)
            card.delete_requested.connect(self.delete_emote) 
            card.toggle_requested.connect(self.toggle_emote_state)
            
            self.emotes_grid_layout.addWidget(card, display_idx // 3, display_idx % 3)
            display_idx += 1
            
        self.emotes_grid_layout.setRowStretch(self.emotes_grid_layout.rowCount(), 1)

    def create_new_emote(self):
        ts = int(time.time())
        new_folder_path = os.path.join(DIR_EMOTE_CONFIGS, f"emote_{ts}")
        os.makedirs(new_folder_path, exist_ok=True)
        default_config = {"name": f"新建表情_{ts}", "hotkey": "", "is_enabled": True}
        with open(os.path.join(new_folder_path, "config.json"), "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        self.open_editor(new_folder_path)

    def open_editor(self, folder_path):
        if self.active_editor:
            self.active_editor.close()
        self.active_editor = EditorWindow(folder_path)
        self.active_editor.saved_signal.connect(self.on_data_changed)
        self.active_editor.deleted_signal.connect(self.on_data_changed)
        self.active_editor.show()

    def delete_emote(self, folder_path):
        reply = QMessageBox.question(self, "危险操作", "确定要永久删除该表情吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                shutil.rmtree(folder_path)
                self.on_data_changed()
                logger.info(f"成功删除表情包: {folder_path}")
            except Exception as e:
                logger.error(f"删除表情包失败: {e}")
                QMessageBox.critical(self, "删除失败", str(e))

    def toggle_emote_state(self, folder_path, is_enabled):
        config_path = os.path.join(folder_path, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            cfg["is_enabled"] = is_enabled
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            self.on_data_changed() 

    @Slot()
    def on_data_changed(self):
        self.refresh_emotes_grid()
        if self.controller and self.controller.is_running:
            self.controller.start_listening(
                self.config_mgr.load_all_emotes(),
                self.config_mgr.load_global_settings(),
                self.trigger_hud,
                self._on_quick_search_hotkey
            )

    @Slot(str, str)
    def append_ui_log(self, level, msg):
        """日志消息输出到 UI 面板"""
        color_map = {
            "DEBUG": "#888888",
            "INFO": "#e0e0e0",
            "WARNING": "#ffd60a",
            "ERROR": "#ff453a",
            "CRITICAL": "#ff453a"
        }
        color = color_map.get(level, "#ffffff")
        
        if "成功" in msg or "完毕" in msg or "就绪" in msg:
            color = "#32d74b"
            
        safe_msg = html.escape(msg)
        html_msg = f"<span style='color:{color};'>{safe_msg}</span>"
        
        if hasattr(self, 'log_box'):
            self.log_box.appendHtml(html_msg)
            scrollbar = self.log_box.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("运行日志")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title.setStyleSheet("color: #ffffff; background: transparent;")
        
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("QPlainTextEdit { background-color: rgba(0, 0, 0, 0.3); border-radius: 12px; padding: 15px; color: #a0a0a0; font-family: Consolas, monospace; font-size: 13px; border: 1px solid rgba(255, 255, 255, 0.05); }")
        
        layout.addWidget(title)
        layout.addSpacing(15)
        layout.addWidget(self.log_box)
        
        return page

    def create_settings_page(self):
        page = QWidget()
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        main_scroll.setStyleSheet("background: transparent;")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 60)
        layout.setSpacing(35)

        header = QLabel("系统偏好设置")
        header.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        header.setStyleSheet("color: #ffffff; background: transparent;")
        layout.addWidget(header)

        global_cfg = self.config_mgr.global_settings if self.config_mgr else {}

        def auto_save_settings():
            if self.config_mgr:
                new_cfg = self.config_mgr.global_settings.copy()
                
                proc_list = global_cfg.get("target_processes", ["discord.exe", "wechat.exe", "qq.exe"])
                if hasattr(self, 'proc_input'):
                    proc_text = self.proc_input.text().strip()
                    if proc_text:
                        proc_list = [p.strip().lower() for p in proc_text.replace('，', ',').split(',') if p.strip()]
                    else:
                        proc_list = []

                new_cfg.update({
                    "global_trigger_key": self.hk_input.text().strip(),
                    "block_keys": self.block_switch.isChecked(),
                    "delay_ms": self.delay_slider.value(),
                    "quick_search_delay_ms": self.qs_delay_slider.value(),
                    "show_hud": self.hud_switch.isChecked(),
                    "hud_mode": "hover" if self.hud_mode_combo.currentText() == "悬停显示" else "always",
                    "hud_opacity": self.opa_slider.value(),
                    "hud_click_through": self.click_switch.isChecked(),
                    "target_processes": proc_list,
                })
                self.config_mgr.save_global_settings(new_cfg)
                self.hud.apply_config(new_cfg)
                self.on_data_changed()
                logger.info("偏好设置已自动热更新！")

        lbl1 = QLabel("核心工作流")
        lbl1.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold; margin-left: 5px; background: transparent;")
        layout.addWidget(lbl1)
        
        group1 = SettingsGroup()
        
        self.hk_input = QLineEdit(global_cfg.get("global_trigger_key", "alt+enter"))
        self.hk_input.setFixedWidth(140)
        self.hk_input.textChanged.connect(auto_save_settings)
        r1 = SettingsRow("全局输出/发送热键", "在装填表情打字后，按下此键自动转换并发送", self.hk_input)
        
        self.block_switch = SwitchControl(checked=global_cfg.get("block_keys", True))
        self.block_switch.toggled.connect(auto_save_settings)
        r2 = SettingsRow("拦截原生系统输入", "避免快捷键与其它软件冲突 (建议开启)", self.block_switch)
        
        delay_val_lbl = QLabel(f"{global_cfg.get('delay_ms', 150)} ms")
        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(50, 500)
        self.delay_slider.setValue(global_cfg.get('delay_ms', 150))
        self.delay_slider.valueChanged.connect(lambda v: [delay_val_lbl.setText(f"{v} ms"), auto_save_settings()])
        r3 = SliderSettingsRow("模拟按键剪切/粘贴延迟", "遇到吞字或者没粘上的情况请适当调高", self.delay_slider, delay_val_lbl)

        qs_delay_val_lbl = QLabel(f"{global_cfg.get('quick_search_delay_ms', 150)} ms")
        self.qs_delay_slider = QSlider(Qt.Horizontal)
        self.qs_delay_slider.setRange(0, 500)
        self.qs_delay_slider.setValue(global_cfg.get('quick_search_delay_ms', 150))
        self.qs_delay_slider.valueChanged.connect(lambda v: [qs_delay_val_lbl.setText(f"{v} ms"), auto_save_settings()])
        r3b = SliderSettingsRow("全选/复制侦测延迟", "Ctrl+A 触发的读取剪贴板延迟，调高可避免漏读", self.qs_delay_slider, qs_delay_val_lbl, is_last=True)
        
        group1.layout.addWidget(r1)
        group1.layout.addWidget(r2)
        group1.layout.addWidget(r3)
        group1.layout.addWidget(r3b)
        layout.addWidget(group1)

        lbl2 = QLabel("桌面悬浮指示器 (HUD)")
        lbl2.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold; margin-left: 5px; background: transparent;")
        layout.addWidget(lbl2)
        
        group2 = SettingsGroup()
        
        self.hud_switch = SwitchControl(checked=global_cfg.get("show_hud", True))
        self.hud_switch.toggled.connect(auto_save_settings)
        r4 = SettingsRow("开启悬浮指示器", "在屏幕上浮现一个指示器，显示当前已装填的表情名称", self.hud_switch)
        
        self.hud_mode_combo = QComboBox()
        self.hud_mode_combo.addItems(["常驻显示", "悬停显示"])
        self.hud_mode_combo.setCurrentText("悬停显示" if global_cfg.get("hud_mode", "always")=="hover" else "常驻显示")
        self.hud_mode_combo.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 10px; color: white;")
        self.hud_mode_combo.currentTextChanged.connect(auto_save_settings)
        r5 = SettingsRow("预览图显示模式", "常驻显示预览图，或仅在鼠标悬停及装填瞬间时展开显示", self.hud_mode_combo)
        
        opa_val_lbl = QLabel(f"{global_cfg.get('hud_opacity', 100)} %")
        self.opa_slider = QSlider(Qt.Horizontal)
        self.opa_slider.setRange(10, 100)
        self.opa_slider.setValue(global_cfg.get('hud_opacity', 100))
        self.opa_slider.valueChanged.connect(lambda v: [opa_val_lbl.setText(f"{v} %"), auto_save_settings()])
        r6 = SliderSettingsRow("主状态透明度", "控制提示窗完全展开时的可见程度", self.opa_slider, opa_val_lbl)
        
        self.click_switch = SwitchControl(checked=global_cfg.get("hud_click_through", False))
        self.click_switch.toggled.connect(auto_save_settings)
        r7 = SettingsRow("开启鼠标穿透 (点击穿透)", "开启后无法再用鼠标拖拽指示器位置，且屏蔽悬停感应", self.click_switch, is_last=True)

        group2.layout.addWidget(r4)
        group2.layout.addWidget(r5)
        group2.layout.addWidget(r6)
        group2.layout.addWidget(r7)
        layout.addWidget(group2)

        group3 = SettingsGroup()
        
        edit_syntax_btn = QPushButton("管理规则...")
        edit_syntax_btn.setStyleSheet("background-color: rgba(255,255,255,0.05); color: #ffffff; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        edit_syntax_btn.setCursor(Qt.PointingHandCursor)
        
        def open_syntax_dialog():
            current_rules = self.config_mgr.global_settings.get("syntax_rules", [])
            dialog = SyntaxHighlightDialog(current_rules, self)
            if dialog.exec() == QDialog.Accepted:
                new_rules = dialog.get_rules()
                self.config_mgr.global_settings["syntax_rules"] = new_rules
                self.config_mgr.save_global_settings(self.config_mgr.global_settings)
                self.on_data_changed()
                logger.info("高亮规则已保存并即时生效！")
                
        lbl4 = QLabel("进程白名单防误触")
        lbl4.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold; margin-left: 5px; background: transparent;")
        layout.addWidget(lbl4)
        
        group4 = SettingsGroup()
        
        current_procs = global_cfg.get("target_processes", ["discord.exe", "wechat.exe", "qq.exe"])
        proc_str = ", ".join(current_procs)
        
        self.proc_input = QLineEdit(proc_str)
        self.proc_input.setFixedWidth(280)
        self.proc_input.setPlaceholderText("留空则允许在所有软件中发射")
        self.proc_input.textChanged.connect(auto_save_settings)
        
        r9 = SettingsRow("允许发送的软件进程", "用逗号分隔多个进程名 (如 discord.exe, qq.exe)。留空代表不限制", self.proc_input, is_last=True)
        
        group4.layout.addWidget(r9)
        layout.addWidget(group4)
        
        layout.addStretch()

        main_scroll.setWidget(container)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0,0,0,0)
        page_layout.addWidget(main_scroll)
        return page