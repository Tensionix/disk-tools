@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Disk Tools - Install System Rclone

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "DL=%ROOT%\install\download"
set "SYS_RCLONE_DIR=%LOCALAPPDATA%\Programs\rclone"
set "TMP_DIR=%ROOT%\system_core\_rclone_system_tmp"
set "PKG=%DL%\rclone-current-windows-amd64.zip"
set "URL=https://downloads.rclone.org/rclone-current-windows-amd64.zip"
set "PS_EXE="
set "CURL_EXE="
set "TAR_EXE="
set "NO_PAUSE=0"

if /I "%~1"=="/NOPAUSE" set "NO_PAUSE=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"
if not defined PS_EXE where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"

where curl.exe >nul 2>nul && set "CURL_EXE=curl.exe"
where tar.exe >nul 2>nul && set "TAR_EXE=tar.exe"

if not exist "%DL%\" mkdir "%DL%" >nul 2>nul

echo ======================================================================
echo   AUDION DISK TOOLS - INSTALL SYSTEM RCLONE
echo ======================================================================
echo Root:    %ROOT%
echo Target:  %SYS_RCLONE_DIR%
echo Config:  %%APPDATA%%\rclone\rclone.conf  ^(not touched^)
echo URL:     %URL%
echo.

if not defined LOCALAPPDATA goto ERR_LOCALAPPDATA
if not defined PS_EXE goto ERR_POWERSHELL
if not defined CURL_EXE if not defined PS_EXE goto ERR_DOWNLOADER
if not defined TAR_EXE if not defined PS_EXE goto ERR_EXTRACTOR

echo [1/5] Downloading latest Rclone Windows AMD64 package...
if defined CURL_EXE goto DOWNLOAD_WITH_CURL
goto DOWNLOAD_WITH_POWERSHELL

:DOWNLOAD_WITH_CURL
"%CURL_EXE%" -L --fail --retry 5 --retry-delay 5 --connect-timeout 30 -A "Audion-Disk-Tools" -o "%PKG%" "%URL%"
if errorlevel 1 goto ERR_DOWNLOAD
goto DOWNLOAD_DONE

:DOWNLOAD_WITH_POWERSHELL
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$ProgressPreference='SilentlyContinue';" ^
  "$headers=@{'User-Agent'='Audion-Disk-Tools'};" ^
  "Invoke-WebRequest -Headers $headers -Uri '%URL%' -OutFile '%PKG%'"
if errorlevel 1 goto ERR_DOWNLOAD

:DOWNLOAD_DONE
if not exist "%PKG%" goto ERR_DOWNLOAD
for %%F in ("%PKG%") do if %%~zF LSS 1000000 goto ERR_DOWNLOAD_SIZE
call :PRINT_SHA256 "%PKG%" "Package SHA256"
echo.

echo [2/5] Extracting package...
if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>nul
mkdir "%TMP_DIR%" >nul 2>nul
if defined TAR_EXE goto EXTRACT_WITH_TAR
goto EXTRACT_WITH_POWERSHELL

:EXTRACT_WITH_TAR
"%TAR_EXE%" -xf "%PKG%" -C "%TMP_DIR%"
if errorlevel 1 goto ERR_EXTRACT
goto EXTRACT_DONE

:EXTRACT_WITH_POWERSHELL
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "Expand-Archive -LiteralPath '%PKG%' -DestinationPath '%TMP_DIR%' -Force"
if errorlevel 1 goto ERR_EXTRACT

:EXTRACT_DONE
set "RCLONE_SRC_DIR="
for /f "delims=" %%F in ('dir /s /b "%TMP_DIR%\rclone.exe" 2^>nul') do (
    if not defined RCLONE_SRC_DIR for %%D in ("%%~dpF.") do set "RCLONE_SRC_DIR=%%~fD"
)
if not defined RCLONE_SRC_DIR goto ERR_VERIFY_EXTRACT
echo [OK] Source: %RCLONE_SRC_DIR%
echo.

echo [3/5] Installing into user system location...
if exist "%SYS_RCLONE_DIR%\" (
    if exist "%LOCALAPPDATA%\Programs\rclone.previous\" rd /s /q "%LOCALAPPDATA%\Programs\rclone.previous" >nul 2>nul
    ren "%SYS_RCLONE_DIR%" "rclone.previous" >nul 2>nul
    if errorlevel 1 goto ERR_COPY
)
mkdir "%SYS_RCLONE_DIR%" >nul 2>nul
robocopy "%RCLONE_SRC_DIR%" "%SYS_RCLONE_DIR%" /E /NFL /NDL /NJH /NJS /NP >nul
set "ROBO_RC=%ERRORLEVEL%"
if %ROBO_RC% GEQ 8 goto ERR_COPY
echo [OK] Installed files copied.
echo.

echo [4/5] Adding user PATH entry if needed...
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$dir='%SYS_RCLONE_DIR%';" ^
  "$old=[Environment]::GetEnvironmentVariable('Path','User');" ^
  "$parts=@($old -split ';' | Where-Object { $_ });" ^
  "if ($parts -notcontains $dir) { [Environment]::SetEnvironmentVariable('Path', (($parts + $dir) -join ';'), 'User'); Write-Host '[OK] Added to user PATH.' } else { Write-Host '[OK] User PATH already contains Rclone.' }"
if errorlevel 1 goto ERR_PATH
echo.

echo [5/5] Verifying...
if not exist "%SYS_RCLONE_DIR%\rclone.exe" goto ERR_VERIFY
"%SYS_RCLONE_DIR%\rclone.exe" version
if errorlevel 1 goto ERR_VERIFY
call :PRINT_SHA256 "%SYS_RCLONE_DIR%\rclone.exe" "rclone.exe SHA256"

rd /s /q "%TMP_DIR%" >nul 2>nul

echo.
echo [SUCCESS] System Rclone installed: %SYS_RCLONE_DIR%
echo [NOTE] Open a new terminal to refresh PATH.
echo [NOTE] Rclone system config was not touched.
call :PAUSE_IF_NEEDED
exit /b 0

:ERR_LOCALAPPDATA
echo [ERROR] LOCALAPPDATA is not defined.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOADER
echo [ERROR] curl.exe and PowerShell were not found.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_POWERSHELL
echo [ERROR] PowerShell was not found.
echo [ERROR] It is required to update the user PATH safely.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_EXTRACTOR
echo [ERROR] tar.exe and PowerShell were not found.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOAD
echo [ERROR] Rclone download failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOAD_SIZE
echo [ERROR] Downloaded package is too small.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_EXTRACT
echo [ERROR] Rclone extract failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_VERIFY_EXTRACT
echo [ERROR] rclone.exe was not found in extracted package.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_COPY
echo [ERROR] Copy to system Rclone folder failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_PATH
echo [ERROR] Could not update user PATH.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_VERIFY
echo [ERROR] System Rclone was not verified after install.
call :PAUSE_IF_NEEDED
exit /b 1

:PRINT_SHA256
set "HASH_FILE=%~1"
set "HASH_LABEL=%~2"
if not exist "%HASH_FILE%" exit /b 0
if defined PS_EXE (
    "%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $hash=(Get-FileHash -Algorithm SHA256 -LiteralPath '%HASH_FILE%').Hash; Write-Host ('[HASH] %HASH_LABEL%: ' + $hash)"
    exit /b 0
)
where certutil.exe >nul 2>nul
if not errorlevel 1 (
    echo [HASH] %HASH_LABEL%:
    certutil.exe -hashfile "%HASH_FILE%" SHA256 | findstr /R /C:"^[0-9A-Fa-f][0-9A-Fa-f ]*$"
)
exit /b 0

:PAUSE_IF_NEEDED
if not "%NO_PAUSE%"=="1" pause
goto :eof
