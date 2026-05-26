@echo off
chcp 65001 >nul
title XTeink · 定时采集 v1.1.0
cd /d "%~dp0"

set hour=%time:~0,2%
set /a hour=1%hour% %% 100

if %hour% LSS 11 (
  set SESSION=morning
) else if %hour% LSS 17 (
  set SESSION=noon
) else (
  set SESSION=evening
)

echo XTeink · 达人微信号采集
echo 当前时段: %SESSION%
python gui.py
pause
