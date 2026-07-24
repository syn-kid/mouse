@echo off
chcp 65001 >nul
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 虚拟环境未初始化，请先运行 setup.bat
    pause
    exit /b 1
)

echo.
echo   DPI2Pad 服务启动中...
echo   浏览器打开 http://127.0.0.1:8000
echo   按 Ctrl+C 停止服务
echo.

.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
