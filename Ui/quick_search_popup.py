"""快捷检索弹窗 — 左侧文件夹侧栏 + 右侧表情网格"""
import os
import logging

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QLabel,
                                QPushButton, QFrame, QScrollArea, QApplication, QWidget)
from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve, QEvent, QByteArray
from PySide6.QtGui import (QFont, QCursor, QPixmap, QImageReader, QPainter, QPainterPath,
                            QColor, QPen, QMovie)
from PySide6.QtSvg import QSvgRenderer

from Core.emote_sender import (copy_file_to_clipboard, get_video_first_frame_pixmap,
                                get_external_resource_path)

logger = logging.getLogger(__name__)


class SavedEmoteQuickPopup(QDialog):
    """快捷检索弹窗 — 左侧文件夹侧栏 + 右侧表情网格"""
    emote_selected = Signal(str)
    folder_clicked = Signal(str)  # 点击侧栏文件夹 → relative_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(480, 420)
        self.setWindowOpacity(0.0)
        self._current_path = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)

        # ── 左侧侧栏 ──
        self._sidebar_frame = QFrame(self)
        self._sidebar_frame.setObjectName("QuickSidebar")
        self._sidebar_frame.setFixedWidth(110)
        self._sidebar_frame.setStyleSheet("")
        sidebar_layout = QVBoxLayout(self._sidebar_frame)
        sidebar_layout.setContentsMargins(6, 8, 6, 8)
        sidebar_layout.setSpacing(4)

        self._sidebar_title = QLabel("文件夹")
        self._sidebar_title.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        self._sidebar_title.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")

        self._sidebar_scroll = QScrollArea()
        self._sidebar_scroll.setWidgetResizable(True)
        self._sidebar_scroll.setFrameShape(QFrame.NoFrame)
        self._sidebar_scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 3px; background: transparent; } QScrollBar::handle:vertical { background: rgba(255,255,255,0.1); border-radius: 1px; }")
        self._sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sidebar_content = QWidget()
        self._sidebar_content.setStyleSheet("background: transparent;")
        self._sidebar_layout = QVBoxLayout(self._sidebar_content)
        self._sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self._sidebar_layout.setSpacing(3)
        self._sidebar_layout.setAlignment(Qt.AlignTop)
        self._sidebar_scroll.setWidget(self._sidebar_content)

        sidebar_layout.addWidget(self._sidebar_title)
        sidebar_layout.addWidget(self._sidebar_scroll)

        # ── 右侧主体 ──
        self._main_frame = QFrame(self)
        self._main_frame.setObjectName("QuickMain")
        self._main_frame.setStyleSheet("")
        main_layout = QVBoxLayout(self._main_frame)
        main_layout.setContentsMargins(8, 8, 8, 6)
        main_layout.setSpacing(6)

        self._title_label = QLabel("表情检索")
        self._title_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self._title_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent;")

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 4px; background: transparent; } QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); border-radius: 2px; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        self._content_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._content)

        self._close_btn = QPushButton("关闭")
        self._close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.05);
                color: #888888;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.1);
                color: #ffffff;
            }
        """)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.close)

        main_layout.addWidget(self._title_label)
        main_layout.addWidget(self._scroll)
        main_layout.addWidget(self._close_btn)

        layout.addWidget(self._sidebar_frame)
        layout.addWidget(self._main_frame)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._sidebar_frame.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, QColor(28, 28, 32, 240))
        pen = QPen(QColor(255, 255, 255, 20))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def set_title(self, text):
        self._title_label.setText(text)

    def clear_items(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        QApplication.processEvents()

    def set_folders(self, subfolders, current_path):
        """填充左侧侧栏子文件夹列表 (subfolders: [(name, rel_path), ...])"""
        while self._sidebar_layout.count():
            item = self._sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        QApplication.processEvents()

        self._current_path = current_path

        # 返回上级按钮 (不在根目录时显示)
        if current_path:
            back_btn = QPushButton("← 返回上级")
            back_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.05);
                    color: rgba(255,255,255,0.55);
                    border-radius: 6px;
                    padding: 4px 6px;
                    font-size: 10px;
                    text-align: left;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,0.12);
                    color: rgba(255,255,255,0.9);
                }
            """)
            back_btn.setCursor(Qt.PointingHandCursor)
            back_btn.clicked.connect(lambda: self.folder_clicked.emit("__back__"))
            self._sidebar_layout.addWidget(back_btn)

            separator = QLabel("—")
            separator.setStyleSheet("color: rgba(255,255,255,0.1); font-size: 9px; background: transparent;")
            separator.setAlignment(Qt.AlignCenter)
            self._sidebar_layout.addWidget(separator)

        if not subfolders and not current_path:
            self._sidebar_frame.hide()
            return

        self._sidebar_frame.show()
        for folder_name, rel_path in subfolders:
            btn = QPushButton(f" {folder_name}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.03);
                    color: rgba(255,255,255,0.65);
                    border-radius: 6px;
                    padding: 5px 8px;
                    font-size: 11px;
                    text-align: left;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,0.08);
                    color: rgba(255,255,255,0.95);
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=rel_path: self.folder_clicked.emit(p))
            self._sidebar_layout.addWidget(btn)
        self._sidebar_layout.addStretch()

    def _truncate_text(self, text, max_chars=14):
        if len(text) > max_chars:
            return text[:max_chars] + "…"
        return text

    def add_item(self, item_data, file_path, mgr):
        row = QFrame()
        row.setObjectName("QuickItem")
        row.setStyleSheet("")
        row.setCursor(Qt.PointingHandCursor)
        row.setFixedHeight(78)

        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 8, 10, 8)
        rl.setSpacing(10)

        thumb = QLabel()
        thumb.setFixedSize(56, 42)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("background: transparent; border-radius: 6px;")

        FALLBACK_STYLE = "background-color: rgba(0,0,0,0.3); border-radius: 6px;"
        THUMB_W, THUMB_H = 56, 42

        def _set_svg_thumb(svg_file: str):
            svg_path = get_external_resource_path(f"Assets/Svg/{svg_file}")
            if os.path.exists(svg_path):
                try:
                    with open(svg_path, 'r', encoding='utf-8') as f:
                        svg_data = f.read()
                    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
                    if renderer.isValid():
                        pm = QPixmap(THUMB_W, THUMB_H)
                        pm.fill(Qt.transparent)
                        painter = QPainter(pm)
                        renderer.render(painter)
                        painter.end()
                        thumb.setPixmap(pm)
                        thumb.setStyleSheet("background: transparent; border-radius: 6px;")
                        return True
                except Exception:
                    pass
            return False

        if file_path and os.path.exists(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg'):
                pixmap = QPixmap(file_path).scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                thumb.setPixmap(pixmap)
            elif ext == '.gif':
                reader = QImageReader(file_path)
                orig = reader.size()
                movie = QMovie(file_path)
                if orig.isValid() and orig.width() > 0:
                    ratio = THUMB_W / orig.width()
                    movie.setScaledSize(QSize(THUMB_W, int(orig.height() * ratio)))
                else:
                    movie.setScaledSize(QSize(THUMB_W, THUMB_H))
                thumb.setMovie(movie)
                movie.start()
            elif ext in ('.mp4', '.webm', '.avi', '.mov'):
                frame = get_video_first_frame_pixmap(file_path, THUMB_W, THUMB_H)
                if frame is not None:
                    thumb.setPixmap(frame)
                elif not _set_svg_thumb("file-video-camera.svg"):
                    thumb.setText("🎬")
                    thumb.setStyleSheet(FALLBACK_STYLE + " color: rgba(255,255,255,0.5); font-size: 16px;")
            elif ext in ('.mp3', '.wav', '.ogg'):
                if not _set_svg_thumb("audio-lines.svg"):
                    thumb.setText("🎵")
                    thumb.setStyleSheet(FALLBACK_STYLE + " color: rgba(255,255,255,0.5); font-size: 16px;")
        else:
            thumb.setText("❓")
            thumb.setStyleSheet(FALLBACK_STYLE + " color: rgba(255,255,255,0.5); font-size: 16px;")

        info = QVBoxLayout()
        info.setSpacing(1)

        filename = item_data.get("filename", "") or ""
        display_name = item_data.get("display_name", "") or os.path.splitext(filename)[0] or "未命名"
        name_label = QLabel(self._truncate_text(display_name, 14))
        name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        name_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent;")

        tags = item_data.get("tags", [])
        if tags:
            tag_text = "  ".join(f"#{self._truncate_text(t, 8)}" for t in tags[:4])
            if len(tags) > 4:
                tag_text += f"  +{len(tags) - 4}"
        else:
            tag_text = "无标签"
        tag_label = QLabel(tag_text)
        tag_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px; background: transparent;")

        folder = item_data.get("folder", "")
        if folder:
            path_text = f"{folder}/"
        else:
            path_text = "SavedEmotes/"
        path_label = QLabel(path_text)
        path_label.setStyleSheet("color: rgba(255, 255, 255, 0.25); font-size: 9px; background: transparent;")

        info.addWidget(name_label)
        info.addWidget(tag_label)
        info.addWidget(path_label)

        rl.addWidget(thumb)
        rl.addLayout(info)
        rl.addStretch()

        row.paintEvent = lambda e, r=row: self._paint_item_bg(e, r)
        row.mousePressEvent = lambda e, fp=file_path: self._on_item_clicked(fp)
        self._content_layout.addWidget(row)

    def _paint_item_bg(self, event, row):
        painter = QPainter(row)
        painter.setRenderHint(QPainter.Antialiasing)
        hover = row.underMouse()
        rect = row.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        if hover:
            painter.fillPath(path, QColor(56, 56, 64, 200))
        else:
            painter.fillPath(path, QColor(38, 38, 44, 180))

    def _on_item_clicked(self, file_path):
        logger.debug(f"[快速搜索弹窗] _on_item_clicked: {file_path}")
        if copy_file_to_clipboard(file_path):
            self.emote_selected.emit(file_path)
            self.close()

    def show_at_cursor(self, item_count=0):
        self._reposition(item_count)
        self.setWindowOpacity(0.0)
        self.show()
        QApplication.instance().installEventFilter(self)
        self._fade_anim.stop()
        try:
            self._fade_anim.finished.disconnect()
        except RuntimeError:
            pass
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _reposition(self, item_count=0):
        """根据当前光标位置调整弹窗坐标"""
        cursor_pos = QCursor.pos()
        x = cursor_pos.x() + 15
        y = cursor_pos.y() - 30
        screen = QApplication.primaryScreen().availableGeometry()
        if x + self.width() > screen.right():
            x = screen.right() - self.width() - 10
        if y + self.height() > screen.bottom():
            y = screen.bottom() - self.height() - 10
        if y < screen.top():
            y = screen.top() + 10
        self.move(x, y)
        if item_count > 0:
            self._scroll.verticalScrollBar().setValue(0)

    def closeEvent(self, event):
        self._fade_anim.stop()
        try:
            self._fade_anim.finished.disconnect()
        except RuntimeError:
            pass
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        event.accept()
        self.deleteLater()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = QCursor.pos()
            if not self.geometry().contains(pos):
                self.close()
                return True
        return super().eventFilter(obj, event)