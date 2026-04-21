import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QPainterPath, QMouseEvent, QPen

class FloatingHUD(QWidget):
    """
    常驻桌面悬浮指示器 (智能药丸模式) - MyDockFinder 风格重制版
    支持透明度调节、鼠标穿透开关、以及智能悬停伸缩显示模式 (已添加平滑动画)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.cfg = {}
        self.is_hover_mode = False
        self.base_opacity = 1.0
        self.custom_pos = False # 记录用户是否自定义拖拽了位置
        
        # 去除 fixedSize，让窗口尺寸能够根据内容物（图片显示/隐藏）自动伸缩
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | 
                            Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.dragPos = QPoint()
        
        self.main_layout = QVBoxLayout(self)
        # 调整边距以贴合 MyDockFinder 风格面板的比例
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(10)
        
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # 调整字体样式，使其更柔和现代
        self.name_label = QLabel("已就绪", self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("-apple-system", 11, QFont.Medium))
        self.name_label.setStyleSheet("color: rgba(255, 255, 255, 0.9);") # 使用 90% 透明度的白色，避免过于刺眼
        
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.name_label)
        
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(250)
        
        # --- 新增：悬停时的透明度过渡动画 ---
        self.hover_opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.hover_opacity_anim.setDuration(200)
        self.hover_opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # --- 新增：图片展开/收起的平滑过渡动画 ---
        self.expand_anim = QPropertyAnimation(self.icon_label, b"maximumHeight")
        self.expand_anim.setDuration(300)
        self.expand_anim.setEasingCurve(QEasingCurve.OutQuart) # 苹果风弹性缓动
        self.expand_anim.valueChanged.connect(self._sync_window_size)

        # 新加这一行：永久绑定动画结束事件
        self.expand_anim.finished.connect(self._on_anim_finished)
        
        # 悬停模式下，高亮 2 秒后自动收起图片的定时器
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
            # 直接播放收起动画，清理掉 disconnect 代码
            self.expand_anim.stop()
            self.expand_anim.setStartValue(self.icon_label.height())
            self.expand_anim.setEndValue(0)
            self.expand_anim.start()
        else:
            self.reposition_to_anchor()

    def _on_anim_finished(self):
        """动画结束时的统一处理回调"""
        # 只有当高度真的缩小到0时，才隐藏控件节约性能
        if self.icon_label.maximumHeight() == 0:
            self.icon_label.hide()
        self._sync_window_size()


    def expand_preview(self):
        """激活状态：使用动画平滑展开图片"""
        self.icon_label.show()
        # 直接播放展开动画，清理掉 disconnect 代码
        self.expand_anim.stop()
        self.expand_anim.setStartValue(self.icon_label.height())
        self.expand_anim.setEndValue(60) # 配合下方 original scaled(80, 60) 的高度
        self.expand_anim.start()

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
        """完全重写绘制逻辑，模拟 MyDockFinder 的深色质感面板"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 留出 1px 的边缘空间用于绘制边框，防止边框被裁剪
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        # MyDockFinder 风格的圆角通常在 10-12 左右
        path.addRoundedRect(rect, 12, 12) 
        
        # 1. 绘制深色半透明背景 (接近截图中的底色)
        painter.fillPath(path, QColor(36, 36, 36, 230))
        
        # 2. 绘制细腻的浅色描边 (模拟 macOS 窗口的 1px 亮色边缘高光)
        pen = QPen(QColor(255, 255, 255, 25)) # 约 10% 的纯白
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

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
            # 配合深色面板，稍微降低空图标的亮度
            self.icon_label.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
            
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