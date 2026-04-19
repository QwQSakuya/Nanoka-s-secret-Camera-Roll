import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QPainterPath, QMouseEvent

class FloatingHUD(QWidget):
    """
    常驻桌面悬浮指示器 (智能药丸模式)
    支持透明度调节、鼠标穿透开关、以及智能悬停伸缩显示模式
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.cfg = {}
        self.is_hover_mode = False
        self.base_opacity = 1.0
        self.custom_pos = False # 记录用户是否自定义拖拽了位置
        
        # 去除 fixedSize，让窗口尺寸能够根据内容物（图片显示/隐藏）自动伸缩！
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | 
                            Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.dragPos = QPoint()
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 12, 15, 12)
        self.main_layout.setSpacing(8)
        
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        self.name_label = QLabel("已就绪", self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("-apple-system", 11, QFont.Bold))
        self.name_label.setStyleSheet("color: white;")
        
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.name_label)
        
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(250)
        
        # 悬停模式下，高亮 2 秒后自动收起图片的定时器
        self.collapse_timer = QTimer(self)
        self.collapse_timer.timeout.connect(self.collapse_preview)
        
        self.setWindowOpacity(0.0)
        self.hide()

    def apply_config(self, cfg: dict):
        self.cfg = cfg
        self.is_hover_mode = cfg.get("hud_mode", "always") == "hover"
        self.base_opacity = cfg.get("hud_opacity", 100) / 100.0
        
        if not cfg.get("show_hud", True):
            self.hide()
            return
            
        old_flags = self.windowFlags()
        new_flags = Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        if cfg.get("hud_click_through", False):
            new_flags |= Qt.WindowTransparentForInput
            
        if old_flags != new_flags:
            was_visible = self.isVisible()
            self.setWindowFlags(new_flags)
            if was_visible:
                self.show()
                
        if self.isVisible():
            self.setWindowOpacity(self.base_opacity)
            if self.is_hover_mode:
                self.collapse_preview()
            else:
                self.expand_preview()

    def reposition_to_anchor(self):
        """如果用户没有拖拽过，确保尺寸变化时依然吸附在右下角"""
        self.adjustSize()
        if not self.custom_pos:
            screen = self.screen().geometry()
            self.move(screen.width() - self.width() - 40, screen.height() - self.height() - 80)

    def collapse_preview(self):
        """潜伏状态：隐藏图片，只保留文字药丸"""
        self.collapse_timer.stop()
        if self.is_hover_mode:
            self.icon_label.hide()
        self.reposition_to_anchor()

    def expand_preview(self):
        """激活状态：展示图片"""
        self.icon_label.show()
        self.reposition_to_anchor()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.custom_pos = True # 一旦手动拖拽，解除右下角自动吸附
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()

    def enterEvent(self, event):
        """鼠标移入：自动展开图片"""
        if self.is_hover_mode and not self.cfg.get("hud_click_through", False):
            self.collapse_timer.stop()
            self.expand_preview()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标移出：自动收起图片"""
        if self.is_hover_mode and not self.cfg.get("hud_click_through", False):
            self.collapse_preview()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        painter.fillPath(path, QColor(20, 20, 20, 210))

    def show_emote(self, emote_name, img_path=""):
        if not self.cfg.get("show_hud", True):
            self.hide()
            return
            
        self.name_label.setText(emote_name[:6] + ("..." if len(emote_name)>6 else ""))
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path).scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.setText("🎨")
            self.icon_label.setFont(QFont("-apple-system", 32))
            self.icon_label.setStyleSheet("color: #a0a0a0;")
            
        self.show()
        # 装填表情时，强制展开图片让用户看清
        self.expand_preview()
        
        self.anim.stop()
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(self.base_opacity)
        self.anim.start()
        
        if self.is_hover_mode:
            self.collapse_timer.start(2000) # 2秒后自动收起

    def fade_out(self):
        self.collapse_timer.stop()
        self.anim.stop()
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.InCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start()