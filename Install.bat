@echo off
cd /d "%~dp0"
if not exist "%~dp0files\install.ps1" (
  powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Unpack the whole archive first (right click - Extract All), then run Install.bat from the unpacked folder.', 'Garasu')"
  exit /b 1
)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0files\install.ps1"
