@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Audion Disk Tools - Folder Picker

set "CORE_DIR=%~dp0"
if "%CORE_DIR:~-1%"=="\" set "CORE_DIR=%CORE_DIR:~0,-1%"
for %%A in ("%CORE_DIR%\..") do set "BASE_DIR=%%~fA"
cd /d "%BASE_DIR%"

set "ACTION=%~1"
set "FILE_MASK=%~2"
if not defined ACTION goto USAGE

set "PICKER_PS1=%CORE_DIR%\Pick-Folder.ps1"
set "PORTABLE_PWSH=%CORE_DIR%\powershell\pwsh.exe"
set "POWERSHELL_EXE="
set "PICKER_RESULT=%TEMP%\audion_pick_%RANDOM%_%RANDOM%.tmp"

if exist "%PORTABLE_PWSH%" (
  set "POWERSHELL_EXE=%PORTABLE_PWSH%"
) else (
  set "POWERSHELL_EXE=powershell.exe"
)

if not exist "%PICKER_PS1%" (
  echo [ERROR] Folder picker helper was not found:
  echo %PICKER_PS1%
  if not defined AUDION_NO_PAUSE pause
  exit /b 1
)

call :RESOLVE_PYTHON
if errorlevel 1 goto NO_PYTHON

call :PICK_ONE SOURCE "Select source folder"
if not defined SOURCE goto CANCELLED
echo.
echo Selected source:
echo   %SOURCE%
echo.
echo Select target folder...
call :PICK_ONE TARGET "Select target folder"
if not defined TARGET goto CANCELLED
call :PROMPT_MASK
echo.
echo Source:
echo   %SOURCE%
echo Target:
echo   %TARGET%
if defined FILE_MASK (
echo Mask:
echo   %FILE_MASK%
) else (
echo Mask:
echo   all files
)
echo.
choice /C YN /N /M "Start operation? [Y/N]: "
if errorlevel 2 goto CANCELLED

if /I "%ACTION%"=="compare_quick" goto COMPARE_QUICK
if /I "%ACTION%"=="compare_safe" goto COMPARE_SAFE
if /I "%ACTION%"=="sync_safe" goto SYNC_SAFE
if /I "%ACTION%"=="sync_dry" goto SYNC_DRY
if /I "%ACTION%"=="backup_safe" goto BACKUP_SAFE
if /I "%ACTION%"=="backup_dry" goto BACKUP_DRY
if /I "%ACTION%"=="sync2_safe" goto SYNC2_SAFE
if /I "%ACTION%"=="sync2_dry" goto SYNC2_DRY

echo [ERROR] Unknown picker action: %ACTION%
if not defined AUDION_NO_PAUSE pause
exit /b 1

:COMPARE_QUICK
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" compare --source "%SOURCE%" --target "%TARGET%" --mode quick %MASK_ARGS%
goto FINISH

:COMPARE_SAFE
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" compare --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
goto FINISH

:SYNC_SAFE
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
goto FINISH

:SYNC_DRY
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS% --dry-run
goto FINISH

:BACKUP_SAFE
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" backup --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
goto FINISH

:BACKUP_DRY
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" backup --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS% --dry-run
goto FINISH

:SYNC2_SAFE
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync2 --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
goto FINISH

:SYNC2_DRY
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync2 --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS% --dry-run
goto FINISH

:FINISH
set "LAST_ERROR=%ERRORLEVEL%"
echo.
if not "%LAST_ERROR%"=="0" (
  echo [ERROR] Operation failed with exit code %LAST_ERROR%.
  echo Review the messages above.
)
if not defined AUDION_NO_PAUSE pause
exit /b %LAST_ERROR%

:CANCELLED
echo.
echo [INFO] Picker operation was cancelled.
if not defined AUDION_NO_PAUSE pause
exit /b 0

:NO_PYTHON
echo [ERROR] Python runtime was not resolved.
if not defined AUDION_NO_PAUSE pause
exit /b 1

:USAGE
echo [ERROR] No picker action was provided.
if not defined AUDION_NO_PAUSE pause
exit /b 1

:PROMPT_MASK
if defined FILE_MASK goto :eof
echo.
setlocal DisableDelayedExpansion
set /p "_AUDION_MASK=Which files do we process? Enter filename and/or extension masks separated by ;, for example: *.xxx; *xyz*.yyy; *.zzz (Enter = all files): "
endlocal & set "FILE_MASK=%_AUDION_MASK%"
goto :eof

:BUILD_MASK_ARGS
set "MASK_ARGS="
if not defined FILE_MASK goto :eof
set "MASK_ARGS=--mask-globs ""%FILE_MASK%"""
goto :eof

:PICK_ONE
set "%~1="
if exist "%PICKER_RESULT%" del /q "%PICKER_RESULT%" >nul 2>nul
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PICKER_PS1%" -ResultFile "%PICKER_RESULT%" -Description "%~2"
if exist "%PICKER_RESULT%" (
  set "_PICKED_PATH="
  set /p "_PICKED_PATH="<"%PICKER_RESULT%"
  del /q "%PICKER_RESULT%" >nul 2>nul
  if defined _PICKED_PATH set "%~1=!_PICKED_PATH!"
  set "_PICKED_PATH="
)
call :NORMALIZE_PATH_VAR "%~1"
goto :eof

:NORMALIZE_PATH_VAR
set "_NP_NAME=%~1"
if not defined _NP_NAME goto :eof
call set "_NP_VALUE=%%%_NP_NAME%%%"
if not defined _NP_VALUE goto NP_DONE
:NP_TRIM_TAIL
if not defined _NP_VALUE goto NP_DONE
if "!_NP_VALUE:~-1!"=="\" (
  if /I "!_NP_VALUE:~1,2!"==":\" (
    if not "!_NP_VALUE:~3!"=="" (
      set "_NP_VALUE=!_NP_VALUE:~0,-1!"
      goto NP_TRIM_TAIL
    )
  ) else (
    if not "!_NP_VALUE:~0,2!"=="\\" (
      set "_NP_VALUE=!_NP_VALUE:~0,-1!"
      goto NP_TRIM_TAIL
    ) else (
      if not "!_NP_VALUE:~2!"=="" (
        set "_NP_VALUE=!_NP_VALUE:~0,-1!"
        goto NP_TRIM_TAIL
      )
    )
  )
)
if "!_NP_VALUE:~-1!"=="/" (
  if /I "!_NP_VALUE:~1,2!"==":/" (
    if not "!_NP_VALUE:~3!"=="" (
      set "_NP_VALUE=!_NP_VALUE:~0,-1!"
      goto NP_TRIM_TAIL
    )
  ) else (
    if not "!_NP_VALUE:~0,2!"=="//" (
      set "_NP_VALUE=!_NP_VALUE:~0,-1!"
      goto NP_TRIM_TAIL
    ) else (
      if not "!_NP_VALUE:~2!"=="" (
        set "_NP_VALUE=!_NP_VALUE:~0,-1!"
        goto NP_TRIM_TAIL
      )
    )
  )
)
:NP_DONE
set "%_NP_NAME%=%_NP_VALUE%"
set "_NP_NAME="
set "_NP_VALUE="
goto :eof

:RUNPY
set "TARGET=%~1"
shift
if not exist "%TARGET%" (
  echo [ERROR] Script not found:
  echo %TARGET%
  exit /b 1
)
set "RUN_ARGS="
:RUNPY_COLLECT
if "%~1"=="" goto RUNPY_EXEC
set "RUN_ARGS=!RUN_ARGS! %1"
shift
goto RUNPY_COLLECT
:RUNPY_EXEC
"%PYTHON_CMD%" %PYTHON_ARGS% "%TARGET%" !RUN_ARGS!
exit /b %ERRORLEVEL%

:RESOLVE_PYTHON
set "PYTHON_CMD="
set "PYTHON_ARGS="

if exist "%BASE_DIR%\runtime\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python.exe"
  goto PY_OK
)

if exist "%BASE_DIR%\runtime\python\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\python.exe"
  goto PY_OK
)

py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  goto PY_OK
)

where python >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  goto PY_OK
)

exit /b 1

:PY_OK
exit /b 0
