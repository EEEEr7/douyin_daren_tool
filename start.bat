@echo off
chcp 65001 >nul
title XTeink · 达人微信号采集 v1.1.0
cd /d "%~dp0"
if exist "XTeink 抖音达人微信采集.exe" (
  start "" "%~dp0XTeink 抖音达人微信采集.exe"
) else (
  pythonw gui.py
)
