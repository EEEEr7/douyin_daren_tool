@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "EXE=%~dp0XTeink 抖音达人微信采集.exe"
set "LINK=%USERPROFILE%\Desktop\XTeink · 达人微信号采集.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LINK%');" ^
  "$s.TargetPath='%EXE%';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%EXE%,0';" ^
  "$s.Description='XTeink 达人微信号采集';" ^
  "$s.Save()"

echo 桌面快捷方式已创建。
pause
