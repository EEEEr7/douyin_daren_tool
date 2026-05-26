@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [XTeink] 正在生成白底图标...
python assets\build_icon.py
if errorlevel 1 goto :fail

echo [XTeink] 正在打包 exe（首次较慢）...
pip install pyinstaller pillow -q
pyinstaller --noconfirm --clean XTeink.spec
if errorlevel 1 goto :fail

copy /Y "dist\XTeink 抖音达人微信采集.exe" "XTeink 抖音达人微信采集.exe" >nul
if exist "XTeink.exe" del /F /Q "XTeink.exe" >nul 2>&1
echo [XTeink] 已生成: %~dp0XTeink 抖音达人微信采集.exe

python create_desktop_shortcut.py
if errorlevel 1 goto :fail

echo.
echo 完成。可双击 exe 或桌面快捷方式启动。
pause
exit /b 0

:fail
echo.
echo 打包失败，请检查 Python 环境与依赖。
pause
exit /b 1
