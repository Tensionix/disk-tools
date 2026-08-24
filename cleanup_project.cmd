@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

title Audion Disk Tools - Cleanup

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
set "BASE_PREFIX=%BASE_DIR%\"
set "ERROR_COUNT=0"
set "AUTO_YES=0"
set "NO_PAUSE=0"

for %%A in (%*) do (
  if /I "%%~A"=="/Y" set "AUTO_YES=1"
  if /I "%%~A"=="/YES" set "AUTO_YES=1"
  if /I "%%~A"=="--yes" set "AUTO_YES=1"
  if /I "%%~A"=="/NOPAUSE" set "NO_PAUSE=1"
  if /I "%%~A"=="--no-pause" set "NO_PAUSE=1"
)

cd /d "%BASE_DIR%" || exit /b 1

if not exist "%BASE_DIR%\system_core\ui_nicegui\app.py" (
  echo [ERROR] Project marker not found:
  echo %BASE_DIR%\system_core\ui_nicegui\app.py
  echo.
  echo Cleanup aborted.
  call :WAIT_IF_NEEDED
  exit /b 1
)

if not exist "%BASE_DIR%\config\tool_manifest.yaml" (
  echo [ERROR] Project marker not found:
  echo %BASE_DIR%\config\tool_manifest.yaml
  echo.
  echo Cleanup aborted.
  call :WAIT_IF_NEEDED
  exit /b 1
)

echo ======================================================================
echo   AUDION DISK TOOLS - PROJECT CLEANUP
echo ======================================================================
echo Root:
echo   %BASE_DIR%
echo.
echo This keeps source scripts, documentation, permanent configs and licenses.
echo It removes generated workspace content, build/runtime payloads and caches:
echo   - input, output, logs, report, workspace, data and release contents
echo   - runtime, wheelhouse and install\download contents
echo   - folders named .runtime, _runtime, ._runtime, __pycache__
echo   - folders named .pytest_cache, .mypy_cache and .ruff_cache
echo   - tmp scratch folder
echo   - Tools portable payloads: PeaZip, rclone, lz4
echo   - system_core\fzf.exe and system_core\powershell contents
echo   - system_core\_pwsh_tmp, system_core\_powershell_tmp, system_core\_fzf_tmp
echo   - system_core\_peazip_tmp, system_core\_7zip_tmp, system_core\_rclone_tmp
echo   - generated *.pyc, *.pyo, *.tmp, *.bak, Thumbs.db, desktop.ini
echo.
echo Protected: system_core source, docs, launchers, install scripts,
echo tests, licenses and the whole config folder - nothing inside it is
echo touched, including rclone.conf, SSH keys, sync profiles and caches.
echo RClone note: project Tools\rclone is removed, but no rclone.conf is,
echo neither the portable one in config\rclone nor a user one outside.
echo.

if "%AUTO_YES%"=="1" goto CLEAN
:ASK
choice /C YNQ /N /M "Proceed with project cleanup? [Y/N/Q]: "
if errorlevel 3 goto QUIT
if errorlevel 2 goto CANCELLED
if errorlevel 1 goto CLEAN
goto ASK

:CLEAN
echo.
echo [CLEAN] Starting Audion Disk Tools cleanup...
echo.

if exist "%BASE_DIR%\install\init_folders.cmd" (
  call "%BASE_DIR%\install\init_folders.cmd" >nul 2>nul
)

call :CLEAN_DIR "%BASE_DIR%\input"
call :CLEAN_DIR "%BASE_DIR%\output"
call :CLEAN_DIR "%BASE_DIR%\logs"
call :CLEAN_DIR "%BASE_DIR%\report"
call :CLEAN_DIR "%BASE_DIR%\workspace"
call :CLEAN_DIR "%BASE_DIR%\data"
call :CLEAN_DIR "%BASE_DIR%\release"
call :CLEAN_DIR "%BASE_DIR%\runtime"
call :CLEAN_DIR "%BASE_DIR%\wheelhouse"
call :CLEAN_DIR "%BASE_DIR%\install\download"
call :CLEAN_DIR "%BASE_DIR%\system_core\powershell"
call :CLEAN_DIR "%BASE_DIR%\Tools\"
call :REMOVE_DIR "%BASE_DIR%\tmp"
call :REMOVE_DIR "%BASE_DIR%\system_core\_pwsh_tmp"
call :REMOVE_DIR "%BASE_DIR%\system_core\_powershell_tmp"
call :REMOVE_DIR "%BASE_DIR%\system_core\_fzf_tmp"
call :REMOVE_DIR "%BASE_DIR%\system_core\_peazip_tmp"
call :REMOVE_DIR "%BASE_DIR%\system_core\_7zip_tmp"
call :REMOVE_DIR "%BASE_DIR%\system_core\_rclone_tmp"

call :REMOVE_GENERATED_DIRS

call :REMOVE_FILE "%BASE_DIR%\system_core\fzf.exe"

call :REMOVE_GENERATED_FILES

if exist "%BASE_DIR%\install\init_folders.cmd" (
  call "%BASE_DIR%\install\init_folders.cmd" >nul 2>nul
)

echo.
if "%ERROR_COUNT%"=="0" (
  echo [OK] Cleanup finished.
  call :WAIT_IF_NEEDED
  exit /b 0
)

echo [ERROR] Cleanup finished with %ERROR_COUNT% error(s).
echo Close GUI, terminals, Python processes, and try again.
call :WAIT_IF_NEEDED
exit /b 1

:CANCELLED
echo.
echo [CANCELLED] Nothing was deleted.
call :WAIT_IF_NEEDED
exit /b 0

:QUIT
echo.
echo [QUIT] Nothing was deleted.
call :WAIT_IF_NEEDED
exit /b 0

:CLEAN_DIR
set "TARGET=%~1"
call :ASSERT_INSIDE "%TARGET%"
if errorlevel 1 (
  set /a ERROR_COUNT+=1
  exit /b 1
)
if not exist "%TARGET%\" (
  echo [CREATE] %TARGET%
  mkdir "%TARGET%" >nul 2>nul
  if not exist "%TARGET%\" (
    echo   [ERROR] Could not create directory: %TARGET%
    set /a ERROR_COUNT+=1
    exit /b 1
  )
  exit /b 0
)
echo [CLEAR] %TARGET%
attrib -r -s -h "%TARGET%\*" /s /d >nul 2>nul
for /f "delims=" %%F in ('dir /b /a "%TARGET%" 2^>nul') do (
    if exist "%TARGET%\%%F\" (
      call :REMOVE_DIR "%TARGET%\%%F"
    ) else (
      call :REMOVE_FILE "%TARGET%\%%F"
    )
)
exit /b 0

:REMOVE_GENERATED_DIRS
echo [DIRS] Removing generated/cache folders
for /f "delims=" %%D in ('dir /ad /b /s "%BASE_DIR%" 2^>nul') do (
  call :IS_GENERATED_DIR "%%~nxD"
  if not errorlevel 1 call :REMOVE_DIR "%%~fD"
)
exit /b 0

:IS_GENERATED_DIR
if /I "%~1"==".runtime" exit /b 0
if /I "%~1"=="_runtime" exit /b 0
if /I "%~1"=="._runtime" exit /b 0
if /I "%~1"=="__pycache__" exit /b 0
if /I "%~1"==".pytest_cache" exit /b 0
if /I "%~1"==".mypy_cache" exit /b 0
if /I "%~1"==".ruff_cache" exit /b 0
exit /b 1

:REMOVE_GENERATED_FILES
echo [FILES] Removing generated file patterns
for /r "%BASE_DIR%" %%F in (*.pyc *.pyo *.tmp *.bak Thumbs.db desktop.ini) do (
  call :IS_PROTECTED_GENERATED_FILE "%%~fF"
  if errorlevel 1 if exist "%%~fF" call :REMOVE_FILE "%%~fF"
)
exit /b 0

:IS_PROTECTED_GENERATED_FILE
rem The whole config folder, not a list of its subfolders. The banner above says
rem config is protected, and until now that was only true of config\rclone: the
rem generated-file sweep walks the entire project, so a stray .bak or .tmp beside
rem a private key was fair game, and one named file was deleted outright.
rem
rem Nothing under config is a build product. Keys, known_hosts and the rclone
rem config travel with the project and cannot be regenerated; profiles and caches
rem are the owner's own state. Clearing the SFTP endpoint history is a button in
rem the window, where the person doing it knows what they are clearing.
set "FILE_ABS=%~f1"
set "CONFIG_PREFIX=%BASE_DIR%\config\"
echo "%FILE_ABS%" | findstr /I /B /C:"%CONFIG_PREFIX%" >nul 2>nul
if not errorlevel 1 exit /b 0
exit /b 1

:REMOVE_DIR
set "TARGET=%~1"
if not exist "%TARGET%\" exit /b 0
call :ASSERT_INSIDE "%TARGET%"
if errorlevel 1 (
  set /a ERROR_COUNT+=1
  exit /b 1
)
echo   rmdir "%TARGET%"
attrib -r -s -h "%TARGET%\*" /s /d >nul 2>nul
rd /s /q "%TARGET%" >nul 2>nul
if exist "%TARGET%\" (
  echo   [ERROR] Could not remove directory: "%TARGET%"
  set /a ERROR_COUNT+=1
  exit /b 1
)
exit /b 0

:REMOVE_FILE
set "TARGET=%~1"
if not exist "%TARGET%" exit /b 0
call :ASSERT_INSIDE "%TARGET%"
if errorlevel 1 (
  set /a ERROR_COUNT+=1
  exit /b 1
)
echo   del "%TARGET%"
attrib -r -s -h "%TARGET%" >nul 2>nul
del /f /q "%TARGET%" >nul 2>nul
if exist "%TARGET%" (
  echo   [ERROR] Could not remove file: "%TARGET%"
  set /a ERROR_COUNT+=1
  exit /b 1
)
exit /b 0

:ASSERT_INSIDE
set "TARGET_ABS=%~f1"
if /I "%TARGET_ABS%"=="%BASE_DIR%" (
  echo [SKIP] Refusing to clean project root directly.
  exit /b 1
)
set "TARGET_REMAINDER=%TARGET_ABS:%BASE_PREFIX%=%"
if not "%TARGET_REMAINDER%"=="%TARGET_ABS%" exit /b 0
echo [SKIP] Outside project root: %TARGET_ABS%
exit /b 1

:WAIT_IF_NEEDED
if "%AUTO_YES%"=="1" goto :eof
if "%NO_PAUSE%"=="1" goto :eof
call :WAIT_KEY
goto :eof

:WAIT_KEY
echo Press any key to continue . . .
if not defined AUDION_NO_PAUSE pause >nul
goto :eof
