@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Disk Tools - Install Portable Rclone

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "DL=%ROOT%\install\download"
set "RCLONE_DIR=%ROOT%\Tools\rclone"
set "PORTABLE_CONFIG_DIR=%ROOT%\config\rclone"
set "PORTABLE_CACHE_DIR=%ROOT%\tmp\rclone-cache"
set "TMP_DIR=%ROOT%\system_core\_rclone_tmp"
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
echo   AUDION DISK TOOLS - INSTALL PORTABLE RCLONE
echo ======================================================================
echo Root:    %ROOT%
echo Target:  %RCLONE_DIR%
echo Config:  %PORTABLE_CONFIG_DIR%\rclone.conf  ^(not touched^)
echo Cache:   %PORTABLE_CACHE_DIR%
echo DL:      %DL%
echo URL:     %URL%
echo curl:    %CURL_EXE%
echo tar:     %TAR_EXE%
echo PS:      %PS_EXE%
echo.

if not defined CURL_EXE if not defined PS_EXE goto ERR_DOWNLOADER
if not defined TAR_EXE if not defined PS_EXE goto ERR_EXTRACTOR

echo [1/5] Downloading latest Rclone portable Windows AMD64 package...
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
for %%F in ("%PKG%") do echo [OK] Package: %%~fF
call :PRINT_SHA256 "%PKG%" "Package SHA256"
echo.

echo [2/5] Extracting package...
if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>nul
mkdir "%TMP_DIR%" >nul 2>nul
if not exist "%TMP_DIR%\" goto ERR_EXTRACT

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
if not exist "%TMP_DIR%\" goto ERR_EXTRACT
echo [OK] Extracted: %TMP_DIR%
echo.

echo [3/5] Locating rclone.exe in extracted package...
set "RCLONE_SRC_DIR="
for /f "delims=" %%F in ('dir /s /b "%TMP_DIR%\rclone.exe" 2^>nul') do (
    if not defined RCLONE_SRC_DIR for %%D in ("%%~dpF.") do set "RCLONE_SRC_DIR=%%~fD"
)
if not defined RCLONE_SRC_DIR goto ERR_VERIFY_EXTRACT
if not exist "%RCLONE_SRC_DIR%\rclone.exe" goto ERR_VERIFY_EXTRACT
echo [OK] Source: %RCLONE_SRC_DIR%
echo.

echo [4/5] Installing into Tools\rclone...
call :RESET_DIR "%RCLONE_DIR%"
if errorlevel 1 goto ERR_COPY
if not exist "%PORTABLE_CONFIG_DIR%\" mkdir "%PORTABLE_CONFIG_DIR%" >nul 2>nul
if not exist "%PORTABLE_CACHE_DIR%\" mkdir "%PORTABLE_CACHE_DIR%" >nul 2>nul

robocopy "%RCLONE_SRC_DIR%" "%RCLONE_DIR%" /E /NFL /NDL /NJH /NJS /NP >nul
set "ROBO_RC=%ERRORLEVEL%"
if %ROBO_RC% GEQ 8 goto ERR_COPY

echo [OK] Installed files copied.
echo.

echo [5/5] Verifying...
if not exist "%RCLONE_DIR%\rclone.exe" goto ERR_VERIFY
"%RCLONE_DIR%\rclone.exe" version
if errorlevel 1 goto ERR_VERIFY
call :PRINT_SHA256 "%RCLONE_DIR%\rclone.exe" "rclone.exe SHA256"

rd /s /q "%TMP_DIR%" >nul 2>nul

echo.
echo [SUCCESS] Rclone installed: %RCLONE_DIR%
echo [NEXT] Portable GUI commands use: --config "%PORTABLE_CONFIG_DIR%\rclone.conf"
echo [NOTE] Existing portable config is not overwritten by this installer.
call :PAUSE_IF_NEEDED
exit /b 0

:ERR_DOWNLOADER
echo [ERROR] curl.exe and PowerShell were not found.
echo [ERROR] Cannot download Rclone.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_EXTRACTOR
echo [ERROR] tar.exe and PowerShell were not found.
echo [ERROR] Cannot extract Rclone package.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOAD
echo [ERROR] Rclone download failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOAD_SIZE
echo [ERROR] Downloaded package is too small.
echo [ERROR] The file is probably an error page or incomplete download.
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
echo [ERROR] Copy to Tools\rclone failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_VERIFY
echo [ERROR] rclone.exe was not verified after install.
call :PAUSE_IF_NEEDED
exit /b 1

:RESET_DIR
set "TARGET_DIR=%~1"
if not defined TARGET_DIR exit /b 1
if /I not "%TARGET_DIR%"=="%RCLONE_DIR%" exit /b 1
if exist "%TARGET_DIR%\" rd /s /q "%TARGET_DIR%" >nul 2>nul
mkdir "%TARGET_DIR%" >nul 2>nul
if not exist "%TARGET_DIR%\" exit /b 1
exit /b 0

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
