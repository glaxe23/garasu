@echo off
rem Garasu: zapusk vsego rabochego stola (okna, panel, klavisha Win), potom boot.pyw vklyuchaet
rem sohranennyj rezhim: v povsednevnom i rabochem zapuskaet vidzhety i pomoshchnika, v igrovom - net.
set "PF=%ProgramFiles%"
tasklist /fi "imagename eq glazewm.exe" | find /i "glazewm.exe" >nul || start "" "%PF%\glzr.io\GlazeWM\glazewm.exe"
tasklist /fi "imagename eq yasb.exe" | find /i "yasb.exe" >nul || start "" "%PF%\YASB\yasb.exe"
start "" pythonw "%~dp0theme\hide_taskbar.pyw"
set "AHK=%LOCALAPPDATA%\Programs\AutoHotkey\v2\AutoHotkey64.exe"
if not exist "%AHK%" set "AHK=%PF%\AutoHotkey\v2\AutoHotkey64.exe"
if exist "%AHK%" start "" "%AHK%" "%~dp0theme\win_launcher.ahk"
start "" pythonw "%~dp0theme\boot.pyw"
start "" pythonw "%~dp0theme\watcher.pyw"
