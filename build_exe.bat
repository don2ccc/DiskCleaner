@echo off
chcp 65001 >nul
title Building DiskCleaner.exe

echo ============================================
echo   Building DiskCleaner.exe with PyInstaller
echo ============================================
echo.

REM Check PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing PyInstaller...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo 🔨 Building executable...
echo This may take 2-5 minutes...
echo.

REM Clean old builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build with spec file
pyinstaller DiskCleaner.spec

echo.
echo ============================================
if exist "dist\DiskCleaner.exe" (
    echo ✅ Build successful!
    echo.
    echo 📁 Output: dist\DiskCleaner.exe
    echo 💾 Size: 
    for %%A in (dist\DiskCleaner.exe) do echo    %%~zA bytes (%%~zA / 1048576 MB^)
    echo.
    echo You can now distribute dist\DiskCleaner.exe
) else (
    echo ❌ Build failed!
    echo Check the error messages above.
)
echo ============================================
echo.
pause
