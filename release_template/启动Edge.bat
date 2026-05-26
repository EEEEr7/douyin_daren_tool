@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "EDGE="
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if exist "%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe" set "EDGE=%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"

if "%EDGE%"=="" (
  echo [XTeink] 未找到 Microsoft Edge，请先安装 Edge。
  pause
  exit /b 1
)

start "" "%EDGE%" --remote-debugging-port=9222 "https://buyin.jinritemai.com/dashboard/servicehall/daren-square"
exit /b 0
