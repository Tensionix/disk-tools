@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

for %%A in ("%SCRIPT_DIR%") do set "HERE=%%~nxA"

set "ROOT=%SCRIPT_DIR%"
if /I "%HERE%"=="install" for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

rem Audion Disk Auditor managed user/workspace folders.
call :MK "%ROOT%\input"
call :MK "%ROOT%\output"
call :MK "%ROOT%\logs"
call :MK "%ROOT%\report"
call :MK "%ROOT%\workspace"

rem Permanent project/configuration folders.
call :MK "%ROOT%\config"
rem Where the owner puts SSH keys and the rclone config by hand. Their contents
rem never enter git, so the folders have to come from here - a .gitkeep used to
rem hold them and no longer exists.
call :MK "%ROOT%\config\ssh"
call :MK "%ROOT%\config\rclone"
call :MK "%ROOT%\data"
call :MK "%ROOT%\docs"

rem Portable runtime, release and cache folders.
call :MK "%ROOT%\runtime"
call :MK "%ROOT%\wheelhouse"
call :MK "%ROOT%\release"
call :MK "%ROOT%\._runtime"

rem Source and helper folders expected by CLI, GUI and release tooling.
call :MK "%ROOT%\system_core"
call :MK "%ROOT%\system_core\core"
call :MK "%ROOT%\system_core\services"
call :MK "%ROOT%\system_core\ui_nicegui"
call :MK "%ROOT%\system_core\powershell"
call :MK "%ROOT%\system_core\license"
call :MK "%ROOT%\system_core\license\files"
call :MK "%ROOT%\system_core\license\fallbacks"
call :MK "%ROOT%\install"
call :MK "%ROOT%\install\download"
call :MK "%ROOT%\licenses"

exit /b 0

:MK
if not exist "%~1\" mkdir "%~1" >nul 2>nul
goto :eof
