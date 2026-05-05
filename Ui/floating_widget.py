import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QPainterPath, QMouseEvent, QPen

class FloatingHUD(QWidget):
    """桌面悬浮指示器 — 显示当前装备的表情，支持悬停展开/拖拽移动/鼠标穿透/透明动画"""
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
        """动画期间强制窗口外壳贴合内部布局"""
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
        """如果用户没有拖拽过，确保尺寸变化时依然吸附在右下角"""
        self.adjustSize()
        if not self.custom_pos:
            screen = self.screen().geometry()
            self.move(screen.width() - self.width() - 40, screen.height() - self.height() - 80)

    def collapse_preview(self):
        """潜伏状态：使用动画收起图片，只保留文字药丸"""
        self.collapse_timer.stop()
        if self.is_hover_mode:
            self.expand_anim.stop()
            self.expand_anim.setStartValue(self.icon_label.height())
            self.expand_anim.setEndValue(0)
            self.expand_anim.start()
        else:
            self.reposition_to_anchor()

    def _on_anim_finished(self):
        """动画结束时的统一处理回调"""
        if self.icon_label.maximumHeight() == 0:
            self.icon_label.hide()
        self._sync_window_size()


    def expand_preview(self):
        """激活状态：使用动画平滑展开图片"""
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
        """鼠标移入：透明度高亮并自动展开图片"""
        if not self.cfg.get("hud_click_through", False):
            self.hover_opacity_anim.stop()
            self.hover_opacity_anim.setEndValue(1.0)
            self.hover_opacity_anim.start()
            
        if self.is_hover_mode and not self.cfg.get("hud_click_through", False):
            self.collapse_timer.stop()
            self.expand_preview()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标移出：恢复透明度并自动收起图片"""
        if not self.cfg.get("hud_click_through", False):
            self.hover_opacity_anim.stop()
            self.hover_opacity_anim.setEndValue(self.base_opacity)
            self.hover_opacity_anim.start()
            
        if self.is_hover_mode and not self.cfg.get("hud_click_through", False):
            self.collapse_preview()
        super().leaveEvent(event)

    def paintEvent(self, event):
        """绘制深色质感面板"""
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