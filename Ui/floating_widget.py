import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QPainterPath, QMouseEvent, QPen

class FloatingHUD(QWidget):
    """桌面悬浮指示器 — 当前装备表情的悬停展开/拖拽/透明动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.cfg = {}
        self.is_hover_mode = False
        self.base_opacity = 1.0
        self.custom_pos = False
        
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | 
                            Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.dragPos = QPoint()
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(10)
        
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        self.name_label = QLabel("已就绪", self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("-apple-system", 11, QFont.Medium))
        self.name_label.setStyleSheet("color: rgba(255, 255, 255, 0.9);")
        
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.name_label)
        
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(250)
        
        self.hover_opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.hover_opacity_anim.setDuration(200)
        self.hover_opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.expand_anim = QPropertyAnimation(self.icon_label, b"maximumHeight")
        self.expand_anim.setDuration(300)
        self.expand_anim.setEasingCurve(QEasingCurve.OutQuart)
        self.expand_anim.valueChanged.connect(self._sync_window_size)
        self.expand_anim.finished.connect(self._on_anim_finished)
        
        self.collapse_timer = QTimer(self)
        self.collapse_timer.timeout.connect(self.collapse_preview)
        
        self.setWindowOpacity(0.0)
        self.hide()

    def _sync_window_size(self):
        """动画期间同步窗口外壳尺寸"""
        self.adjustSize()
        self.reposition_to_anchor()

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
        """未手动拖拽时保持右下角锚定"""
        self.adjustSize()
        if not self.custom_pos:
            screen = self.screen().geometry()
            self.move(screen.width() - self.width() - 40, screen.height() - self.height() - 80)

    def collapse_preview(self):
        """收起预览 — 仅保留文字标签"""
        self.collapse_timer.stop()
        if self.is_hover_mode:
            self.expand_anim.stop()
            self.expand_anim.setStartValue(self.icon_label.height())
            self.expand_anim.setEndValue(0)
            self.expand_anim.start()
        else:
            self.reposition_to_anchor()

    def _on_anim_finished(self):
        """动画结束后处理布局"""
        if self.icon_label.maximumHeight() == 0:
            self.icon_label.hide()
        self._sync_window_size()

    def expand_preview(self):
        """展开预览 — 显示缩略图"""
        self.icon_label.show()
        self.expand_anim.stop()
        self.expand_anim.setStartValue(self.icon_label.height())
        self.expand_anim.setEndValue(60)
        self.expand_anim.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.custom_pos = True
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()

    def enterEvent(self, event):
        """鼠标移入 — 高亮并展开预览"""
        if not self.cfg.get("hud_click_through", False):
            self.hover_opacity_anim.stop()
            self.hover_opacity_anim.setEndValue(1.0)
            self.hover_opacity_anim.start()
            
        if self.is_hover_mode and not self.cfg.get("hud_click_through", False):
            self.collapse_timer.stop()
            self.expand_preview()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标移出 — 恢复透明并收起预览"""
        if not self.cfg.get("hud_click_through", False):
            self.hover_opacity_anim.stop()
            self.hover_opacity_anim.setEndValue(self.base_opacity)
            self.hover_opacity_anim.start()
            
        if self.is_hover_mode and not self.cfg.get("hud_click_through", False):
            self.collapse_preview()
        super().leaveEvent(event)

    def paintEvent(self, event):
        """深色圆角面板绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12) 
        
        painter.fillPath(path, QColor(36, 36, 36, 230))
        
        pen = QPen(QColor(255, 255, 255, 25))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def show_emote(self, emote_name, img_path=""):
        if not self.cfg.get("show_hud", True):
            self.hide()
            return

        if not isinstance(emote_name, str):
            emote_name = str(emote_name) if emote_name is not None else "未知"

        self.name_label.setText(emote_name[:6] + ("..." if len(emote_name) > 6 else ""))
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path).scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.setText("🎨")
            self.icon_label.setFont(QFont("-apple-system", 32))
            self.icon_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
            
        self.show()
        self.expand_preview()
        
        self.anim.stop()
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(self.base_opacity)
        self.anim.start()
        
        if self.is_hover_mode:
            self.collapse_timer.start(2000)

    def fade_out(self):
        self.collapse_timer.stop()
        self.anim.stop()
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.InCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start()