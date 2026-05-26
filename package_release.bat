@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [XTeink] 生成图标...
python assets\build_icon.py
if errorlevel 1 goto :fail

echo [XTeink] 打包 exe...
pip install pyinstaller pillow -q
pyinstaller --noconfirm --clean XTeink.spec
if errorlevel 1 goto :fail
copy /Y "dist\XTeink 抖音达人微信采集.exe" "XTeink 抖音达人微信采集.exe" >nul

echo [XTeink] 制作发给同事的发布包（含浏览器，体积较大）...
python package_release.py
if errorlevel 1 goto :fail

echo.
echo 完成。请将 release\XTeink_达人微信采集_v1.2.0.zip 发给同事。
pause
exit /b 0

:fail
echo 打包失败。
pause
exit /b 1
