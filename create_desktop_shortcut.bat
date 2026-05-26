@echo off
chcp 65001 >nul
cd /d "%~dp0"
python create_desktop_shortcut.py
if errorlevel 1 (
  echo.
  echo 创建桌面快捷方式失败。
  pause
  exit /b 1
)
echo.
echo 请到桌面查看「XTeink · 达人微信号采集」。
pause
