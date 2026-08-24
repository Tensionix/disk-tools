@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion Disk Tools - Русский лаунчер

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "CORE_DIR=%BASE_DIR%\system_core"
set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\project_menu_ru.txt"
set "RES_FILE=%RUNTIME_DIR%\project_menu_ru_res.txt"
set "PATH_MENU_FILE=%RUNTIME_DIR%\project_path_mode_ru.txt"
set "PATH_RES_FILE=%RUNTIME_DIR%\project_path_mode_ru_res.txt"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
call :CLEAN_TEMP

call :RESOLVE_PYTHON
if errorlevel 1 goto NO_PYTHON

call :RESOLVE_FZF
if errorlevel 1 (
  set "MENU_MODE=CMD fallback"
) else (
  set "MENU_MODE=FZF"
)

:MAIN
cls
echo ======================================================================
echo   AUDION DISK AUDITOR - РУССКИЙ ЛАУНЧЕР
echo ======================================================================
echo Root:      %BASE_DIR%
echo Python:    %PYTHON_CMD% %PYTHON_ARGS%
echo Menu mode: %MENU_MODE%
echo.

if /I "%AUDION_AUTO_EXIT%"=="1" goto SMOKE_EXIT
if defined FZF_CMD goto FZF_MENU
goto FALLBACK_MENU

:FZF_MENU
call :WRITE_MAIN_MENU
"%FZF_CMD%" --prompt="audion@disk-auditor [PROJECT-RU] > " --pointer=">" --header="Выбери действие. BACKUP-MIRROR - основной sync-сценарий." --layout=reverse --border=rounded --info=hidden --margin=1,2 < "%MENU_FILE%" > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW
goto DISPATCH_MAIN

:FALLBACK_MENU
echo [1] Создать manifest
echo [2] Создать manifest без cloud roots
echo [3] Проверить manifest
echo [4] Сравнить one-way quick
echo [5] Сравнить one-way safe
echo [6] Backup mirror safe
echo [7] Dry run backup mirror safe
echo [8] Синхронизация one-way safe
echo [9] Dry run синхронизации one-way safe
echo [A] Full sync two-way safe
echo [B] Dry run full sync two-way safe
echo [C] Лаунчер сохранённых профилей
echo [D] Открыть папку output
echo [E] Открыть папку logs
echo [F] Открыть папку config
echo [G] Tools launcher
echo [H] Builder main
echo [V] English project launcher
echo [0] Выход
echo.
choice /C 123456789ABCDEFGHV0 /N /M "Выбор: "
if errorlevel 19 exit /b 0
if errorlevel 18 set "RAW=launcher_en" & goto DISPATCH_MAIN
if errorlevel 17 set "RAW=builder" & goto DISPATCH_MAIN
if errorlevel 16 set "RAW=tools" & goto DISPATCH_MAIN
if errorlevel 15 set "RAW=open_config" & goto DISPATCH_MAIN
if errorlevel 14 set "RAW=open_logs" & goto DISPATCH_MAIN
if errorlevel 13 set "RAW=open_output" & goto DISPATCH_MAIN
if errorlevel 12 set "RAW=profiles" & goto DISPATCH_MAIN
if errorlevel 11 set "RAW=sync2_dry" & goto DISPATCH_MAIN
if errorlevel 10 set "RAW=sync2_safe" & goto DISPATCH_MAIN
if errorlevel 9 set "RAW=sync_dry" & goto DISPATCH_MAIN
if errorlevel 8 set "RAW=sync_safe" & goto DISPATCH_MAIN
if errorlevel 7 set "RAW=backup_dry" & goto DISPATCH_MAIN
if errorlevel 6 set "RAW=backup_safe" & goto DISPATCH_MAIN
if errorlevel 5 set "RAW=compare_safe" & goto DISPATCH_MAIN
if errorlevel 4 set "RAW=compare_quick" & goto DISPATCH_MAIN
if errorlevel 3 set "RAW=verify" & goto DISPATCH_MAIN
if errorlevel 2 set "RAW=manifest_nocloud" & goto DISPATCH_MAIN
if errorlevel 1 set "RAW=manifest" & goto DISPATCH_MAIN
goto MAIN

:DISPATCH_MAIN
if /I "%RAW%"=="manifest" goto MANIFEST
if /I "%RAW%"=="manifest_nocloud" goto MANIFEST_NOCLOUD
if /I "%RAW%"=="verify" goto VERIFY
if /I "%RAW%"=="compare_quick" goto COMPARE_QUICK
if /I "%RAW%"=="compare_safe" goto COMPARE_SAFE
if /I "%RAW%"=="sync_safe" goto SYNC_SAFE
if /I "%RAW%"=="sync_dry" goto SYNC_DRY
if /I "%RAW%"=="backup_safe" goto BACKUP_SAFE
if /I "%RAW%"=="backup_dry" goto BACKUP_DRY
if /I "%RAW%"=="sync2_safe" goto SYNC2_SAFE
if /I "%RAW%"=="sync2_dry" goto SYNC2_DRY
if /I "%RAW%"=="profiles" goto PROFILES
if /I "%RAW%"=="open_output" goto OPEN_OUTPUT
if /I "%RAW%"=="open_logs" goto OPEN_LOGS
if /I "%RAW%"=="open_config" goto OPEN_CONFIG
if /I "%RAW%"=="tools" goto TOOLS
if /I "%RAW%"=="builder" goto BUILDER
if /I "%RAW%"=="launcher_en" goto LAUNCHER_EN
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:MANIFEST
call :PROMPT_PATH ROOT "Папка для аудита"
if not defined ROOT goto MAIN
call :RUNPY "%CORE_DIR%\main.py" manifest --root "%ROOT%" --project-root "%BASE_DIR%"
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:MANIFEST_NOCLOUD
call :PROMPT_PATH ROOT "Папка для аудита"
if not defined ROOT goto MAIN
call :RUNPY "%CORE_DIR%\main.py" manifest --root "%ROOT%" --exclude-cloud-roots --project-root "%BASE_DIR%"
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:VERIFY
call :PROMPT_PATH ROOT "Папка для проверки"
if not defined ROOT goto MAIN
call :RUNPY "%CORE_DIR%\main.py" verify --root "%ROOT%"
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:COMPARE_QUICK
call :GET_PATHS compare_quick
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" compare --source "%SOURCE%" --target "%TARGET%" --mode quick %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:COMPARE_SAFE
call :GET_PATHS compare_safe
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" compare --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:SYNC_SAFE
call :GET_PATHS sync_safe
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:SYNC_DRY
call :GET_PATHS sync_dry
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS% --dry-run
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:BACKUP_SAFE
call :GET_PATHS backup_safe
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" backup --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:BACKUP_DRY
call :GET_PATHS backup_dry
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" backup --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS% --dry-run
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:SYNC2_SAFE
call :GET_PATHS sync2_safe
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync2 --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:SYNC2_DRY
call :GET_PATHS sync2_dry
if defined PICKER_USED goto MAIN
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync2 --source "%SOURCE%" --target "%TARGET%" --mode safe %MASK_ARGS% --dry-run
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:PROFILES
if exist "%BASE_DIR%\launcher_profiles_ru.cmd" (
  call "%BASE_DIR%\launcher_profiles_ru.cmd"
) else if exist "%BASE_DIR%\launcher_profiles.cmd" (
  call "%BASE_DIR%\launcher_profiles.cmd"
) else (
  echo [ERROR] Лаунчер профилей не найден.
  goto RETURN_TO_MENU
)
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:OPEN_OUTPUT
start "" explorer "%BASE_DIR%\output"
goto RETURN_TO_MENU

:OPEN_LOGS
start "" explorer "%BASE_DIR%\logs"
goto RETURN_TO_MENU

:OPEN_CONFIG
start "" explorer "%BASE_DIR%\config"
goto RETURN_TO_MENU

:TOOLS
call "%BASE_DIR%\launcher_tools.cmd"
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:BUILDER
call "%BASE_DIR%\builder_main.cmd"
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:LAUNCHER_EN
if exist "%BASE_DIR%\launcher_project.cmd" (
  call "%BASE_DIR%\launcher_project.cmd"
) else (
  echo [ERROR] Английский launcher проекта не найден.
  goto RETURN_TO_MENU
)
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:GET_PATHS
set "SOURCE="
set "TARGET="
set "FILE_MASK="
set "MASK_ARGS="
set "PICKER_USED="
if defined FZF_CMD goto GET_PATHS_FZF
goto GET_PATHS_FALLBACK

:GET_PATHS_FZF
call :WRITE_PATH_MODE_MENU
"%FZF_CMD%" --prompt="audion@disk-auditor [PATHS-RU] > " --pointer=">" --header="Выбери способ ввода source и target. Можно задать маску файлов." --layout=reverse --border=rounded --info=hidden --margin=1,2 < "%PATH_MENU_FILE%" > "%PATH_RES_FILE%"
set "PATH_CHOICE="
set /p PATH_CHOICE=<"%PATH_RES_FILE%"
if not defined PATH_CHOICE goto :eof
for /f "tokens=2 delims=|" %%a in ("%PATH_CHOICE%") do set "PATH_MODE=%%a"
call :TRIM PATH_MODE
if /I "%PATH_MODE%"=="picker" goto GET_PATHS_PICKER
call :PROMPT_PATHS SOURCE TARGET FILE_MASK
goto :eof

:GET_PATHS_FALLBACK
echo.
echo [1] Ручной ввод
echo [2] Folder picker
echo.
choice /C 12 /N /M "Выбери ввод путей [1-2]: "
if errorlevel 2 goto GET_PATHS_PICKER
call :PROMPT_PATHS SOURCE TARGET FILE_MASK
goto :eof

:GET_PATHS_PICKER
set "PICKER_USED=1"
call "%CORE_DIR%\launcher_picker_main.cmd" %~1 "%FILE_MASK%"
goto :eof

:ACTION_FAILED
set "LAST_ERROR=%ERRORLEVEL%"
echo.
echo [ERROR] Операция завершилась с кодом %LAST_ERROR%.
echo Проверь сообщения выше.
if not defined AUDION_NO_PAUSE pause
goto MAIN

:RETURN_TO_MENU
echo.
if not defined AUDION_NO_PAUSE pause
goto MAIN

:SMOKE_EXIT
call :CLEAN_TEMP
if defined FZF_CMD (
  call :WRITE_MAIN_MENU
  type nul > "%RES_FILE%"
  call :WRITE_PATH_MODE_MENU
  type nul > "%PATH_RES_FILE%"
)
echo [INFO] Smoke-check launcher завершён.
exit /b 0

:NO_PYTHON
cls
echo [ERROR] Python runtime не найден.
echo.
echo Поддерживаемые пути:
echo   runtime\python.exe
echo   runtime\python\python.exe
echo   py -3.12
echo   python
echo.
echo Используй builder_main.cmd или install\Build_Portable_Env_Build.cmd
if not defined AUDION_NO_PAUSE pause
exit /b 1

:WRITE_MAIN_MENU
> "%MENU_FILE%" echo [01] СОЗДАТЬ MANIFEST                         ^| manifest          ^| записать __CHECKSUMS__.b3 для папки
>>"%MENU_FILE%" echo [02] СОЗДАТЬ MANIFEST БЕЗ CLOUD ROOTS         ^| manifest_nocloud  ^| пропустить типовые cloud roots
>>"%MENU_FILE%" echo [03] ПРОВЕРИТЬ MANIFEST                       ^| verify            ^| сверить __CHECKSUMS__.b3 с файлами
>>"%MENU_FILE%" echo [04] СРАВНИТЬ ONE-WAY QUICK                   ^| compare_quick     ^| сравнение по размеру и времени
>>"%MENU_FILE%" echo [05] СРАВНИТЬ ONE-WAY SAFE                    ^| compare_safe      ^| BLAKE3-safe сравнение при необходимости
>>"%MENU_FILE%" echo [06] BACKUP MIRROR SAFE                       ^| backup_safe       ^| привести target к source; лишнее в target может удаляться
>>"%MENU_FILE%" echo [07] DRY RUN BACKUP MIRROR SAFE               ^| backup_dry        ^| превью mirror-копирования и удалений
>>"%MENU_FILE%" echo [08] СИНХРОНИЗАЦИЯ ONE-WAY SAFE               ^| sync_safe         ^| копировать новые и изменённые без удалений
>>"%MENU_FILE%" echo [09] DRY RUN СИНХРОНИЗАЦИИ ONE-WAY SAFE       ^| sync_dry          ^| только превью копирования
>>"%MENU_FILE%" echo [10] FULL SYNC TWO-WAY SAFE                   ^| sync2_safe        ^| union sync без удалений
>>"%MENU_FILE%" echo [11] DRY RUN FULL SYNC TWO-WAY SAFE           ^| sync2_dry         ^| только превью two-way sync
>>"%MENU_FILE%" echo [12] ЛАУНЧЕР СОХРАНЁННЫХ ПРОФИЛЕЙ             ^| profiles          ^| сохранённые sync pairs
>>"%MENU_FILE%" echo [13] ОТКРЫТЬ ПАПКУ OUTPUT                     ^| open_output       ^| explorer output
>>"%MENU_FILE%" echo [14] ОТКРЫТЬ ПАПКУ LOGS                       ^| open_logs         ^| explorer logs
>>"%MENU_FILE%" echo [15] ОТКРЫТЬ ПАПКУ CONFIG                     ^| open_config       ^| explorer config
>>"%MENU_FILE%" echo [16] TOOLS LAUNCHER                           ^| tools             ^| сервисные утилиты
>>"%MENU_FILE%" echo [17] BUILDER MAIN                             ^| builder           ^| portable build и release
>>"%MENU_FILE%" echo [31] ENGLISH PROJECT LAUNCHER                 ^| launcher_en       ^| переключиться на english UI
>>"%MENU_FILE%" echo [00] ВЫХОД                                    ^| exit              ^| закрыть launcher
goto :eof

:WRITE_PATH_MODE_MENU
> "%PATH_MENU_FILE%" echo [01] РУЧНОЙ ВВОД                         ^| manual            ^| ввести source, target и маску
>>"%PATH_MENU_FILE%" echo [02] FOLDER PICKER                       ^| picker            ^| использовать picker и маску файлов
goto :eof

:PROMPT_TEXT
set "%~1="
echo.
setlocal DisableDelayedExpansion
set /p "_AUDION_TEXT=%~2: "
endlocal & set "%~1=%_AUDION_TEXT%"
goto :eof

:PROMPT_PATH
call :PROMPT_TEXT %~1 "%~2"
call :NORMALIZE_PATH_VAR "%~1"
goto :eof

:PROMPT_PATHS
set "%~1="
set "%~2="
if not "%~3"=="" set "%~3="
echo.
setlocal DisableDelayedExpansion
set /p "_AUDION_SOURCE=Папка source: "
set /p "_AUDION_TARGET=Папка target: "
if not "%~3"=="" set /p "_AUDION_MASK=Какие файлы обрабатываем? Введите маски имени и/или расширения через ;, например: *.xxx; *xyz*.yyy; *.zzz (Enter = все файлы): "
endlocal & (
  set "%~1=%_AUDION_SOURCE%"
  set "%~2=%_AUDION_TARGET%"
  if not "%~3"=="" set "%~3=%_AUDION_MASK%"
)
call :NORMALIZE_PATH_VAR "%~1"
call :NORMALIZE_PATH_VAR "%~2"
goto :eof

:BUILD_MASK_ARGS
set "MASK_ARGS="
if not defined FILE_MASK goto :eof
call :TRIM FILE_MASK
if not defined FILE_MASK goto :eof
set "MASK_ARGS=--mask-globs ""%FILE_MASK%"""
goto :eof

:CLEAN_TEMP
for %%F in ("%MENU_FILE%" "%RES_FILE%" "%PATH_MENU_FILE%" "%PATH_RES_FILE%") do (
  if exist "%%~F" del /q "%%~F" >nul 2>nul
)
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
  echo [ERROR] Скрипт не найден:
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

:RESOLVE_FZF
set "FZF_CMD="
if /I "%AUDION_DISABLE_FZF%"=="1" exit /b 1
if exist "%CORE_DIR%\fzf.exe" (
  set "FZF_CMD=%CORE_DIR%\fzf.exe"
  exit /b 0
)
where fzf >nul 2>nul
if not errorlevel 1 (
  set "FZF_CMD=fzf"
  exit /b 0
)
exit /b 1

:TRIM
for /f "tokens=* delims= " %%z in ("!%~1!") do set "%~1=%%z"
:TRIM_R
if "!%~1:~-1!"==" " set "%~1=!%~1:~0,-1!" & goto TRIM_R
goto :eof
