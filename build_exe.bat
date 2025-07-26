@echo off
echo Building SYN Video Cutter executable...
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    echo.
)

REM Create the executable
echo Creating executable...
pyinstaller --onefile --windowed --name "SYN_Video_Cutter" --icon=icon.ico cut_video.py

REM Check if build was successful
if exist "dist\SYN_Video_Cutter.exe" (
    echo.
    echo ✅ Build successful!
    echo Executable created: dist\SYN_Video_Cutter.exe
    echo.
    echo 📋 Important Notes:
    echo - Users need FFmpeg installed on their system
    echo - Executable size: ~15-20MB
    echo - Works on Windows 10+
    echo.
    pause
) else (
    echo.
    echo ❌ Build failed!
    echo Please check the output above for errors.
    echo.
    pause
)
