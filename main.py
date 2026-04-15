import flet as ft
import os

# 定义基础目录常量
DIR_EMOTE_CONFIGS = "./EmoteConfigs"
DIR_CONFIGS = "./Configs"
DIR_LOGS = "./Logs"
DIR_FONTS = "./Fonts"

# 确保必要的目录存在
for directory in [DIR_EMOTE_CONFIGS, DIR_CONFIGS, DIR_LOGS, DIR_FONTS]:
    os.makedirs(directory, exist_ok=True)

def main(page: ft.Page):
    # 页面基础设置
    page.title = "Anan's Sketchbook Chat Box"
    page.theme_mode = ft.ThemeMode.DARK # 现代暗黑风格
    page.window_width = 900
    page.window_height = 650
    page.window_min_width = 800
    page.window_min_height = 500
    page.padding = 0

    # 自定义字体（如果有的话，可以加载本地字体）
    # page.fonts = {"MiHeavy": "./Fonts/MiHeavy.ttf"}
    # page.theme = ft.Theme(font_family="MiHeavy")

    # --- 页面内容组件定义 ---

    # 1. 主页/介绍页
    view_home = ft.Container(
        content=ft.Column([
            ft.Text("欢迎使用 Anan's Sketchbook Chat Box", size=30, weight=ft.FontWeight.BOLD),
            ft.Text("主打简约、可视化、现代风格的聊天辅助工具。", size=16, color=ft.colors.WHITE70),
            ft.Divider(),
            ft.Text("在这里你可以介绍工具的用法、版本信息等...", color=ft.colors.WHITE54)
        ], alignment=ft.MainAxisAlignment.START),
        padding=30,
        expand=True
    )

    # 2. 表情列表页 (Emotes)
    view_emotes = ft.Container(
        content=ft.Column([
            # 顶部操作栏
            ft.Row([
                ft.TextField(hint_text="搜索表情...", prefix_icon=ft.icons.SEARCH, expand=True, border_radius=20, height=45),
                ft.IconButton(icon=ft.icons.ADD, tooltip="新增表情配置", icon_color=ft.colors.PRIMARY, icon_size=30),
                ft.IconButton(icon=ft.icons.FOLDER_OPEN, tooltip="打开配置文件夹", icon_color=ft.colors.WHITE70, 
                              on_click=lambda _: os.startfile(os.path.abspath(DIR_EMOTE_CONFIGS))),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            # 表情卡片网格区域 (占位模拟)
            ft.GridView(
                expand=True,
                runs_count=3,
                max_extent=250,
                child_aspect_ratio=1.0,
                spacing=15,
                run_spacing=15,
                controls=[
                    # 模拟一个表情卡片
                    ft.Card(
                        content=ft.Container(
                            padding=15,
                            content=ft.Column([
                                ft.Image(src="https://picsum.photos/150/150", width=100, height=100, fit=ft.ImageFit.CONTAIN, border_radius=10),
                                ft.Text("测试表情 1", weight=ft.FontWeight.BOLD),
                                ft.Row([
                                    ft.Text("快捷键: Alt+1", size=12, color=ft.colors.WHITE54),
                                    ft.Switch(value=True, scale=0.7)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.TextButton("进入编辑 ->", icon=ft.icons.EDIT, on_click=lambda _: print("进入编辑"))
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                        )
                    ) for _ in range(5) # 生成 5 个假卡片
                ]
            )
        ]),
        padding=20,
        expand=True
    )

    # 3. 日志页 (Logs)
    view_logs = ft.Container(
        content=ft.Column([
            ft.Text("系统日志", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.ListView([
                    ft.Text("[2026-04-15 10:00:00] [INFO] 程序启动成功...", color=ft.colors.WHITE70),
                    ft.Text("[2026-04-15 10:05:22] [DEBUG] 监听到快捷键触发组合...", color=ft.colors.WHITE70),
                ], expand=True),
                bgcolor=ft.colors.SURFACE_VARIANT,
                border_radius=10,
                padding=10,
                expand=True
            )
        ]),
        padding=20,
        expand=True
    )

    # 4. 设置页 (Settings)
    view_settings = ft.Container(
        content=ft.Column([
            ft.Text("全局设置", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.ListView([
                ft.ListTile(title=ft.Text("热键设置"), subtitle=ft.Text("配置触发生成的按键组合")),
                ft.Row([ft.Text("剪切/粘贴延迟 (ms):"), ft.Slider(min=0, max=1000, value=100, label="{value} ms", expand=True)]),
                ft.ListTile(title=ft.Text("阻断按键进程"), subtitle=ft.Text("防止原按键被目标程序识别"), trailing=ft.Switch(value=True)),
                ft.ListTile(title=ft.Text("按键动作配置"), subtitle=ft.Text("修改全选、剪切、粘贴、发送的对应按键 (当前: ctrl+a, ctrl+x, ctrl+v, enter)")),
                ft.Divider(),
                ft.ElevatedButton("保存并热重载配置", icon=ft.icons.SAVE),
            ], expand=True)
        ]),
        padding=20,
        expand=True
    )

    # --- 导航逻辑 ---
    content_area = ft.Container(expand=True, content=view_home)

    def change_route(e):
        index = e.control.selected_index
        if index == 0:
            content_area.content = view_home
        elif index == 1:
            content_area.content = view_emotes
        elif index == 2:
            content_area.content = view_logs
        elif index == 3:
            content_area.content = view_settings
        content_area.update()

    # 侧边导航栏
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=400,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.icons.HOME_OUTLINED, selected_icon=ft.icons.HOME, label="主页"),
            ft.NavigationRailDestination(icon=ft.icons.EMOJI_EMOTIONS_OUTLINED, selected_icon=ft.icons.EMOJI_EMOTIONS, label="表情管理"),
            ft.NavigationRailDestination(icon=ft.icons.LIST_ALT_OUTLINED, selected_icon=ft.icons.LIST_ALT, label="运行日志"),
            ft.NavigationRailDestination(icon=ft.icons.SETTINGS_OUTLINED, selected_icon=ft.icons.SETTINGS, label="全局设置"),
        ],
        on_change=change_route,
    )

    # 主布局
    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                content_area
            ],
            expand=True,
        )
    )

if __name__ == "__main__":
    # 运行 Flet 应用
    ft.app(target=main)