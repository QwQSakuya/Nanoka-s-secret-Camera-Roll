import os
import sys
import time
import shutil
import json
import logging
import html
import re
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                               QPushButton, QLineEdit, QGridLayout, QFrame, 
                               QScrollArea, QCheckBox, QSlider, QStackedWidget, 
                               QButtonGroup, QPlainTextEdit, QMainWindow, QMessageBox,
                               QSystemTrayIcon, QMenu, QStyle, QApplication, QDialog, QSizePolicy,
                               QComboBox, QColorDialog)
from PySide6.QtCore import Qt, QPoint, QObject, Signal, Slot, Property, QPropertyAnimation, QEasingCurve, QSize, QByteArray,QUrl
from PySide6.QtGui import QFont, QCursor, QMouseEvent, QPixmap, QIcon, QColor, QPainter, QPainterPath, QDesktopServices
from PySide6.QtSvg import QSvgRenderer

from Ui.editor_window import EditorWindow
from Ui.floating_widget import FloatingHUD

from Core.logger import logger

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
            pixmap = QPixmap(img_path).scaled(150, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.img_label.setPixmap(pixmap)
            self.img_label.setStyleSheet("border-radius: 8px;")
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

class MainWindow(QMainWindow):
    ui_log_signal = Signal(str, str) 

    def __init__(self, config_mgr=None, controller=None):
        super().__init__()
        self.config_mgr = config_mgr
        self.controller = controller
        self.active_editor = None 
        self.force_quit = False 
        
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
        add_nav_btn("diamond.svg", "主页探索", 0)
        add_nav_btn("image.svg", "表情管理", 1 )
        
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
            self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()

    def trigger_hud(self, emote_name, img_path):
        logger.debug(f"HUD trigger: {emote_name}")
        self.hud.show_emote(emote_name, img_path)

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
                    self.trigger_hud
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
                self.trigger_hud
            )

    @Slot(str, str)
    def append_ui_log(self, level, msg):
        """Append a log message from backend to the UI."""
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
        r3 = SliderSettingsRow("模拟按键剪切/粘贴延迟", "遇到吞字或者没粘上的情况请适当调高", self.delay_slider, delay_val_lbl, is_last=True)
        
        group1.layout.addWidget(r1)
        group1.layout.addWidget(r2)
        group1.layout.addWidget(r3)
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