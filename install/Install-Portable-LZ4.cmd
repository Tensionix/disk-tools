@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Disk Tools - Install Portable LZ4

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "DL=%ROOT%\install\download"
set "LZ4_DIR=%ROOT%\Tools\lz4"
set "TMP=%ROOT%\system_core\_lz4_tmp"
set "PKG=%DL%\lz4_win64.zip"
set "PS_EXE="
set "NO_PAUSE=0"

if /I "%~1"=="/NOPAUSE" set "NO_PAUSE=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

if exist "%ROOT%\system_core\powershell\pwsh.exe" set "PS_EXE=%ROOT%\system_core\powershell\pwsh.exe"
if not defined PS_EXE where pwsh.exe >nul 2>nul && set "PS_EXE=pwsh.exe"
if not defined PS_EXE where powershell.exe >nul 2>nul && set "PS_EXE=powershell.exe"

if not exist "%DL%\" mkdir "%DL%" >nul 2>nul

echo ======================================================================
echo   AUDION DISK TOOLS - INSTALL PORTABLE LZ4
echo ======================================================================
echo Root:    %ROOT%
echo Target:  %LZ4_DIR%
echo DL:      %DL%
echo PS:      %PS_EXE%
echo.
echo TAR.LZ4 needs the standalone lz4 CLI: the bundled 7-Zip carries lz4
echo only as a codec and cannot write a .lz4 stream.
echo.

if not defined PS_EXE goto ERR_POWERSHELL

echo [1/4] Resolving latest lz4 win64 release...
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$ProgressPreference='SilentlyContinue';" ^
  "$headers=@{'User-Agent'='Audion-Disk-Tools'}; if($env:GITHUB_TOKEN){$headers['Authorization']='Bearer '+$env:GITHUB_TOKEN};" ^
  "$repo='https://github.com/lz4/lz4'; $api='https://api.github.com/repos/lz4/lz4/releases/latest'; $tag=$null; $url=$null; $downloaded=$false;" ^
  "try { $resp=$null; try { $resp=Invoke-WebRequest -Uri ($repo + '/releases/latest') -Headers $headers -MaximumRedirection 0 -ErrorAction Stop } catch { $resp=$_.Exception.Response }; $loc=$null; if($resp){ if($resp.Headers.Location){ $loc=[string]$resp.Headers.Location } elseif($resp.Headers['Location']){ $loc=[string]$resp.Headers['Location'] } }; if(-not $loc -or $loc -notmatch '/tag/(?<tag>[^/]+)$'){ throw 'Could not resolve latest lz4 release tag without API.' }; $tag=$Matches.tag; $version=$tag.TrimStart('v').Replace('.','_'); $url=($repo + '/releases/download/' + $tag + '/lz4_win64_v' + $version + '.zip'); Write-Host ('[INFO] Resolved through releases/latest redirect: ' + $tag) } catch { Write-Host ('[WARN] releases/latest resolver unavailable, using GitHub API: ' + $_.Exception.Message) };" ^
  "if($url){ try { Write-Host ('[URL] ' + $url); Invoke-WebRequest -Headers $headers -Uri $url -OutFile '%PKG%'; $downloaded=$true; Write-Host '[INFO] Direct release download succeeded.' } catch { Write-Host ('[WARN] Direct asset URL failed, using GitHub API: ' + $_.Exception.Message); $url=$null; Remove-Item -LiteralPath '%PKG%' -Force -ErrorAction SilentlyContinue } };" ^
  "if(-not $url){ $release=Invoke-RestMethod -Headers $headers $api; $tag=$release.tag_name; $asset=$release.assets | Where-Object { $_.name -like 'lz4_win64*.zip' } | Select-Object -First 1; if(-not $asset){ throw 'Asset not found: lz4_win64*.zip' }; $url=$asset.browser_download_url; Write-Host '[INFO] Resolved through GitHub API fallback.' };" ^
  "Write-Host ('[VER] ' + $tag);" ^
  "Write-Host ('[URL] ' + $url);" ^
  "if(-not $downloaded){ Invoke-WebRequest -Headers $headers -Uri $url -OutFile '%PKG%' }"
if errorlevel 1 goto ERR_DOWNLOAD
if not exist "%PKG%" goto ERR_DOWNLOAD

echo [2/4] Extracting package...
if exist "%TMP%" rd /s /q "%TMP%" >nul 2>nul
mkdir "%TMP%" >nul 2>nul
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "Expand-Archive -LiteralPath '%PKG%' -DestinationPath '%TMP%' -Force"
if errorlevel 1 goto ERR_EXTRACT

echo [3/4] Installing into Tools\lz4...
call :RESET_DIR "%LZ4_DIR%"
if errorlevel 1 goto ERR_COPY
"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$exe=Get-ChildItem -LiteralPath '%TMP%' -Recurse -Filter 'lz4.exe' | Select-Object -First 1;" ^
  "if(-not $exe){ throw 'lz4.exe was not found inside the package.' };" ^
  "Copy-Item -LiteralPath $exe.FullName -Destination '%LZ4_DIR%\' -Force;" ^
  "Get-ChildItem -LiteralPath $exe.Directory.FullName -Filter '*.dll' | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination '%LZ4_DIR%\' -Force };" ^
  "Write-Host ('[INFO] Runtime binary only. The win64 package ships no LICENSE/COPYING file at all.');" ^
  "Write-Host ('[LEGAL] lz4.exe (CLI) is GPL-2.0-or-later; liblz4 itself is BSD-2-Clause. Register lz4 in Audion License Fleet Manager before a release.')"
if errorlevel 1 goto ERR_COPY

echo [4/4] Verifying...
if not exist "%LZ4_DIR%\lz4.exe" goto ERR_VERIFY
for %%F in ("%LZ4_DIR%\lz4.exe") do echo [OK] LZ4: %%~fF
"%LZ4_DIR%\lz4.exe" --version
if errorlevel 1 goto ERR_VERIFY

rd /s /q "%TMP%" >nul 2>nul

echo.
echo [SUCCESS] LZ4 installed: %LZ4_DIR%
echo TAR.LZ4 is now selectable in the GUI archive formats.
call :PAUSE_IF_NEEDED
exit /b 0

:ERR_POWERSHELL
echo [ERROR] PowerShell was not found.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_DOWNLOAD
echo [ERROR] LZ4 download failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_EXTRACT
echo [ERROR] LZ4 extract failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_COPY
echo [ERROR] Copy to Tools\lz4 failed.
call :PAUSE_IF_NEEDED
exit /b 1

:ERR_VERIFY
echo [ERROR] lz4.exe was not found or is not runnable after install.
call :PAUSE_IF_NEEDED
exit /b 1

:RESET_DIR
set "TARGET_DIR=%~1"
if not defined TARGET_DIR exit /b 1
if /I not "%TARGET_DIR%"=="%LZ4_DIR%" exit /b 1
if exist "%TARGET_DIR%\" rd /s /q "%TARGET_DIR%" >nul 2>nul
mkdir "%TARGET_DIR%" >nul 2>nul
if not exist "%TARGET_DIR%\" exit /b 1
exit /b 0

:PAUSE_IF_NEEDED
if not "%NO_PAUSE%"=="1" pause
goto :eof
