@echo off
chcp 65001 >nul
echo ============================================
echo   DPI2Pad — 鼠标垫量化推荐引擎
echo   环境初始化
echo ============================================
echo.

cd /d "%~dp0backend"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.10+
    echo         下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Python 版本:
python --version

echo.
echo [2/3] 创建虚拟环境...
if not exist ".venv" (
    python -m venv .venv
    echo   虚拟环境已创建
) else (
    echo   虚拟环境已存在，跳过
)

echo.
echo [3/3] 安装依赖...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
echo   依赖安装完成

echo.
echo ============================================
echo   初始化完成！双击 start.bat 启动服务
echo ============================================
pause
