@echo off
chcp 65001 >nul
title C盘清理工具 - AI 代理服务

echo ============================================
echo   C盘清理工具 AI 代理服务
echo ============================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖是否安装
echo 正在检查依赖...
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo 首次运行，正在安装依赖包...
    pip install fastapi uvicorn openai google-generativeai -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

REM 检查配置文件
if not exist "ai_config.json" (
    echo 未找到配置文件，将创建默认配置...
)

REM 启动服务
echo.
echo 正在启动 AI 代理服务...
echo 服务地址: http://localhost:10089
echo.
python ./ai_proxy.py

pause
