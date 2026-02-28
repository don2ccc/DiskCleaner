@echo off
chcp 65001 >nul
title Restart AI Service

echo ============================================
echo   Restart AI Service
echo ============================================
echo.

echo Stopping old service...
powershell -Command "Get-NetTCPConnection -LocalPort 10089 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

timeout /t 2 /nobreak >nul

echo.
echo Starting new service...
start "" python ai_proxy.py

echo.
echo ✅ Service restarted!
echo.
timeout /t 3 /nobreak
exit
