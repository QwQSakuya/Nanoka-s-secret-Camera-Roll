@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ═══════════════════════════════════════════════════════════
::  Nanoka's Secret Camera Roll — 一键环境安装脚本
::  双击运行即可自动安装所有 Python 依赖库
:: ═══════════════════════════════════════════════════════════

title Nanoka's Camera Roll - 环境安装

:: ─── 1. 检测 Python ───────────────────────────────────────
echo   [1/3] 检测 Python 环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [✗] 未找到 Python！请先安装 Python 3.9+
    echo       下载地址: https://www.python.org/downloads/
    echo       安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   [✓] 已找到 Python %PYVER%

:: ─── 2. 询问虚拟环境 ─────────────────────────────────────
echo.
echo   [2/3] 是否创建虚拟环境 .venv？
echo         (推荐: 不干扰系统全局 Python 包)
set /p VENV_CHOICE="         创建虚拟环境？[Y/n] "
if /i "%VENV_CHOICE%"=="" set VENV_CHOICE=Y
if /i "%VENV_CHOICE:~0,1%"=="Y" (
    echo   [⋯] 正在创建虚拟环境...
    python -m venv .venv 2>nul
    if exist ".venv\Scripts\activate.bat" (
        call .venv\Scripts\activate.bat
        echo   [✓] 虚拟环境已创建并激活
    ) else (
        echo   [!] 虚拟环境创建失败，将使用全局 Python
    )
) else (
    echo   [⋯] 跳过虚拟环境，使用全局 Python 安装
)

:: ─── 3. 升级 pip ────────────────────────────────────────
echo.
echo   [⋯] 升级 pip 到最新版...
python -m pip install --upgrade pip --quiet 2>nul

:: ─── 4. 安装依赖 ────────────────────────────────────────
echo.
echo   [3/3] 安装项目依赖...
echo   ─────────────────────────────────────────────────
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo.
    echo   [!] 清华镜像安装失败，尝试默认源...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo   [✗] 依赖安装失败！
        echo   请检查网络连接后重试，或手动执行:
        echo   pip install -r requirements.txt
        pause
        exit /b 1
    )
)

:: ─── 5. 完成 ─────────────────────────────────────────────
echo.
echo   [✓] 所有依赖安装完成
echo.
echo   ─────────── 快速开始 ───────────
echo   运行程序:   python main.py
echo   打包 exe:   build.cmd
echo   ──────────────────────────────────
echo.
echo   提示: 如果使用了 .venv，下次打开终端后请先执行:
echo         .venv\Scripts\activate
echo.

pause