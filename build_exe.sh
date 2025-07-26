#!/bin/bash

echo "Building SYN Video Cutter executable..."
echo

# Check if PyInstaller is installed
python3 -c "import PyInstaller" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
    echo
fi

# Create the executable
echo "Creating executable..."
pyinstaller --onefile --windowed --name "SYN_Video_Cutter" cut_video.py

# Check if build was successful
if [ -f "dist/SYN_Video_Cutter" ]; then
    echo
    echo "✅ Build successful!"
    echo "Executable created: dist/SYN_Video_Cutter"
    echo
    echo "📋 Important Notes:"
    echo "- Users need FFmpeg installed on their system"
    echo "- Executable size: ~15-20MB"
    echo "- Works on macOS 10.14+ and major Linux distributions"
    echo
else
    echo
    echo "❌ Build failed!"
    echo "Please check the output above for errors."
    echo
fi

read -p "Press any key to continue..."
