@echo off
chcp 65001 >nul
title 💎 DiskCleaner Pro - Starting...

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python not found. Please install Python 3.8+
    echo 📥 Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✨ Checking dependencies...

REM Check core dependencies
python -c "import send2trash, requests" >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing core dependencies...
    pip install send2trash requests -i https://pypi.tuna.tsinghua.edu.cn/simple
)

REM Check CustomTkinter
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo 🎨 Installing modern UI framework...
    pip install customtkinter -i https://pypi.tuna.tsinghua.edu.cn/simple
)

REM Check AI service dependencies
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo 🤖 Installing AI service dependencies...
    pip install fastapi uvicorn openai google-generativeai -i https://pypi.tuna.tsinghua.edu.cn/simple
)

REM Auto-start AI service if configured
if exist "ai_config.json" (
    python -c "import json; cfg=json.load(open('ai_config.json')); exit(0 if cfg.get('api_key') else 1)" >nul 2>&1
    if not errorlevel 1 (
        echo 🚀 Starting AI service in background...
        start /B python ai_proxy.py >nul 2>&1
        timeout /t 2 /nobreak >nul
    )
)

REM Launch main application
echo.
echo 🚀 Launching DiskCleaner Pro...
echo.
python gui_main.py

REM Cleanup background processes on exit
taskkill /F /FI "WindowTitle eq AI*" >nul 2>&1
