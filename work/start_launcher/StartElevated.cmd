@echo off
chcp 65001 >nul
setlocal EnableExtensions
set "AUDION_APP_NAME=Audion Disk Tools"
set "AUDION_APP_ID=Audion.Tools.Audion.Disk.Tools"
set "AUDION_GUI_ELEVATE=1"
set "AUDION_APP_ICON=E:\TOOLS\Audion Disk Tools\system_core\icons\app.ico"
call "E:\TOOLS\Audion Disk Tools\launcher_gui.cmd"
exit /b %ERRORLEVEL%
