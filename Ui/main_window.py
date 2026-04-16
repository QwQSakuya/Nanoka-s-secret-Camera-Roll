import os
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                               QPushButton, QLineEdit, QGridLayout, QFrame, 
                               QScrollArea, QCheckBox, QSlider, QStackedWidget, 
                               QButtonGroup, QPlainTextEdit, QMainWindow)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QCursor, QMouseEvent

# 目录常量 (相对于主程序运行目录 main.py)
DIR_EMOTE_CONFIGS = "./EmoteConfigs"
DIR_CONFIGS = "./Configs"
DIR_LOGS = "./Logs"
DIR_FONTS = "./Fonts"

for directory in [DIR_EMOTE_CONFIGS, DIR_CONFIGS, DIR_LOGS, DIR_FONTS]:
    os.makedirs(directory, exist_ok=True)

# Apple 极简半透明玻璃风格 QSS
MAC_GLASS_STYLE = """
    /* 全局无边框主窗口 */
    QWidget { 
        font-family: "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Microsoft YaHei", sans-serif; 
        color: #d1d1d1;
    }
    
    /* 根容器：实现半透明深色玻璃与圆角 */
    QFrame#RootFrame {
        background-color: rgba(30, 30, 30, 220); 
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1); 
    }
    
    /* 侧边栏容器 */
    QFrame#Sidebar {
        background-color: rgba(20, 20, 20, 100);
        border-top-left-radius: 12px;
        border-bottom-left-radius: 12px;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* 分组标题 */
    QLabel#SectionTitle {
        color: #7a7a7a;
        font-size: 11px;
        font-weight: bold;
        padding-left: 5px;
        margin-top: 10px;
    }
    
    /* 侧边栏导航按钮 */
    QPushButton.NavBtn {
        background-color: transparent;
        color: #a0a0a0;
        text-align: left;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 13px;
        border: none;
    }
    QPushButton.NavBtn:hover {
        background-color: rgba(255, 255, 255, 0.05);
        color: #e0e0e0;
    }
    QPushButton.NavBtn:checked {
        background-color: rgba(255, 255, 255, 0.12); 
        color: #ffffff;
        font-weight: bold;
    }
    
    /* 通用输入框 */
    QLineEdit {
        background-color: rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        padding: 8px 12px;
        color: #ffffff;
    }
    QLineEdit:focus {
        border: 1px solid rgba(242, 60, 60, 0.5); 
        background-color: rgba(0, 0, 0, 0.3);
    }
    
    /* 红色主按钮 */
    QPushButton.PrimaryBtn {
        background-color: #e04040;
        color: white;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
        border: none;
    }
    QPushButton.PrimaryBtn:hover { background-color: #f24c4c; }
    QPushButton.PrimaryBtn:pressed { background-color: #c73636; }
    
    /* 次级透明按钮 */
    QPushButton.SecondaryBtn {
        background-color: rgba(255, 255, 255, 0.05);
        color: #d1d1d1;
        border-radius: 6px;
        padding: 8px 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    QPushButton.SecondaryBtn:hover { background-color: rgba(255, 255, 255, 0.1); }
    
    /* 滚动条 */
    QScrollBar:vertical {
        background-color: transparent;
        width: 6px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: rgba(255, 255, 255, 0.2);
        border-radius: 3px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover { background-color: rgba(255, 255, 255, 0.3); }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; border: none; }
    
    /* 表情卡片 */
    QFrame#EmoteCard {
        background-color: rgba(255, 255, 255, 0.03);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    QFrame#EmoteCard:hover {
        background-color: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
"""

class WindowControls(QWidget):
    """苹果 macOS 风格的红黄绿窗口控制按钮"""
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 0, 15)
        layout.setSpacing(8)
        
        self.close_btn = self._create_btn("#ff5f56", "#e0443e", self.window.close)
        self.min_btn = self._create_btn("#ffbd2e", "#dea123", self.window.showMinimized)
        self.max_btn = self._create_btn("#27c93f", "#1aab29", self.toggle_maximize)
        
        layout.addWidget(self.close_btn)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addStretch()

    def _create_btn(self, color, hover_color, action):
        btn = QPushButton()
        btn.setFixedSize(12, 12)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {color}; border-radius: 6px; border: none; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """)
        btn.clicked.connect(action)
        return btn

    def toggle_maximize(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

class EmoteCard(QFrame):
    """极简半透明卡片"""
    def __init__(self, title):
        super().__init__()
        self.setObjectName("EmoteCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.img_label = QLabel("📷 预览")
        self.img_label.setFixedSize(140, 90)
        self.img_label.setStyleSheet("background-color: rgba(0,0,0,0.2); border-radius: 6px; color: #666;")
        self.img_label.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title_label.setStyleSheet("color: #eaeaea;")
        
        hotkey_label = QLabel("快捷键: Alt + 1")
        hotkey_label.setStyleSheet("color: #888; font-size: 11px;")
        
        edit_btn = QPushButton("编辑")
        edit_btn.setProperty("class", "SecondaryBtn")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        
        layout.addWidget(self.img_label, alignment=Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(title_label)
        layout.addWidget(hotkey_label)
        layout.addSpacing(5)
        layout.addWidget(edit_btn)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anan's Sketchbook Chat Box")
        self.resize(950, 650)
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

        # 左侧边栏
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 20)
        sidebar_layout.setSpacing(5)
        
        sidebar_layout.addWidget(WindowControls(self))
        
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        
        def add_section(title):
            lbl = QLabel(title)
            lbl.setObjectName("SectionTitle")
            sidebar_layout.addWidget(lbl)
            
        def add_nav_btn(icon, text, index):
            btn = QPushButton(f"  {icon}   {text}")
            btn.setProperty("class", "NavBtn")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            self.nav_group.addButton(btn, index)
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
            btn.clicked.connect(lambda _, idx=index: self.stacked_widget.setCurrentIndex(idx))

        nav_container = QWidget()
        nav_inner_layout = QVBoxLayout(nav_container)
        nav_inner_layout.setContentsMargins(15, 0, 15, 0)
        nav_inner_layout.setSpacing(4)
        sidebar_layout.addWidget(nav_container)
        sidebar_layout = nav_inner_layout

        add_section("主菜单")
        add_nav_btn("🔴", "主页", 0)
        add_nav_btn("🎴", "表情配置", 1)
        add_section("系统记录")
        add_nav_btn("📝", "运行日志", 2)
        add_section("设置与其它")
        add_nav_btn("⚙️", "全局设置", 3)
        
        sidebar_layout.addStretch()
        self.nav_buttons[0].setChecked(True) 

        # 右侧内容区
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.create_home_page())
        self.stacked_widget.addWidget(self.create_emotes_page())
        self.stacked_widget.addWidget(self.create_logs_page())
        self.stacked_widget.addWidget(self.create_settings_page())

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stacked_widget)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # 修复弃用警告，使用 globalPosition().toPoint()
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            # 修复弃用警告，使用 globalPosition().toPoint()
            self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()

    def create_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 50, 40, 40)
        
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        
        title = QLabel("欢迎来到 Sketchbook 草图本")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        
        desc = QLabel("主打极简、透明与现代体验的工具箱。")
        desc.setStyleSheet("color: #888;")
        desc.setAlignment(Qt.AlignCenter)
        
        start_btn = QPushButton("开始使用配置")
        start_btn.setProperty("class", "PrimaryBtn")
        start_btn.setFixedSize(160, 40)
        start_btn.setCursor(QCursor(Qt.PointingHandCursor))
        start_btn.clicked.connect(lambda: self.nav_buttons[1].click())
        
        center_layout.addStretch()
        center_layout.addWidget(title)
        center_layout.addSpacing(10)
        center_layout.addWidget(desc)
        center_layout.addSpacing(20)
        center_layout.addWidget(start_btn, alignment=Qt.AlignCenter)
        center_layout.addStretch()
        
        layout.addWidget(center_container)
        return page

    def create_emotes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 40, 20, 0)
        
        top_bar = QHBoxLayout()
        search_box = QLineEdit()
        search_box.setPlaceholderText("🔍 搜索配置...")
        search_box.setFixedWidth(250)
        
        add_btn = QPushButton("新增")
        add_btn.setProperty("class", "PrimaryBtn")
        
        folder_btn = QPushButton("目录")
        folder_btn.setProperty("class", "SecondaryBtn")
        folder_btn.clicked.connect(lambda: os.startfile(os.path.abspath(DIR_EMOTE_CONFIGS)))
        
        top_bar.addWidget(search_box)
        top_bar.addStretch()
        top_bar.addWidget(folder_btn)
        top_bar.addWidget(add_btn)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background-color: transparent;")
        
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background-color: transparent;")
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 20, 10, 30)
        grid_layout.setSpacing(20)
        
        for i in range(7):
            grid_layout.addWidget(EmoteCard(f"预设表情 {i+1}"), i // 3, i % 3)
            
        grid_layout.setRowStretch(grid_layout.rowCount(), 1)
        scroll_area.setWidget(grid_widget)
        
        layout.addLayout(top_bar)
        layout.addWidget(scroll_area)
        return page

    def create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("运行日志")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 10px;
                padding: 15px;
                color: #d1d1d1;
                font-family: Consolas, monospace;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        
        self.log_box.appendHtml("<span style='color:#7a7a7a'>[10:00:00]</span> <span style='color:#27c93f'>[INFO]</span> 引擎初始化完成")
        self.log_box.appendHtml("<span style='color:#7a7a7a'>[10:00:02]</span> <span style='color:#27c93f'>[INFO]</span> 加载毛玻璃无边框 UI 风格")
        self.log_box.appendHtml("<span style='color:#7a7a7a'>[10:05:11]</span> <span style='color:#ffbd2e'>[WAIT]</span> 等待键盘钩子注入...")
        self.log_box.appendHtml("<span style='color:#7a7a7a'>[10:05:12]</span> <span style='color:#27c93f'>[INFO]</span> 剪贴板内核模块就绪。")
        
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(self.log_box)
        return page

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("全局设置")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        
        panel = QFrame()
        panel.setStyleSheet("background-color: rgba(255,255,255,0.03); border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(25, 25, 25, 25)
        panel_layout.setSpacing(20)
        
        block_cb = QCheckBox("启用底层按键阻断 (拦截 Enter 键)")
        block_cb.setStyleSheet("color: #d1d1d1; spacing: 10px;")
        
        delay_layout = QVBoxLayout()
        delay_label = QLabel("读写延迟: 150ms")
        delay_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 1000)
        slider.setValue(150)
        slider.setStyleSheet("""
            QSlider::groove:horizontal { border-radius: 2px; height: 4px; background: rgba(0,0,0,0.3); }
            QSlider::handle:horizontal { background: #e04040; width: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        
        delay_layout.addWidget(delay_label)
        delay_layout.addWidget(slider)
        
        save_btn = QPushButton("保存配置")
        save_btn.setProperty("class", "PrimaryBtn")
        save_btn.setFixedSize(120, 36)
        
        panel_layout.addWidget(block_cb)
        panel_layout.addSpacing(10)
        panel_layout.addLayout(delay_layout)
        panel_layout.addStretch()
        panel_layout.addWidget(save_btn, alignment=Qt.AlignRight)
        
        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(panel)
        layout.addStretch()
        return page