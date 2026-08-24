@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion Disk Tools - Профили синхронизации

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "CORE_DIR=%BASE_DIR%\system_core"
set "DEFAULT_PROFILES=%BASE_DIR%\config\sync_pairs.json"
set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\profiles_menu_ru.txt"
set "RES_FILE=%RUNTIME_DIR%\profiles_menu_ru_res.txt"
set "PATH_MENU_FILE=%RUNTIME_DIR%\profiles_path_mode_ru.txt"
set "PATH_RES_FILE=%RUNTIME_DIR%\profiles_path_mode_ru_res.txt"
set "PROFILE_MENU_FILE=%RUNTIME_DIR%\profiles_pick_ru.txt"
set "PROFILE_RES_FILE=%RUNTIME_DIR%\profiles_pick_ru_res.txt"

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
echo   AUDION DISK AUDITOR - ПРОФИЛИ СИНХРОНИЗАЦИИ
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
"%FZF_CMD%" --prompt="audion@disk-auditor [PROFILES-RU] > " --pointer=">" --header="Выбери действие для сохранённого профиля. Backup-профили работают как BACKUP-MIRROR." --layout=reverse --border=rounded --info=hidden --margin=1,2 < "%MENU_FILE%" > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW
goto DISPATCH_MAIN

:FALLBACK_MENU
echo [1] Показать сохранённые профили
echo [2] Сравнить сохранённый профиль
echo [3] Запустить сохранённый профиль
echo [4] Dry run сохранённого профиля
echo [V] English profiles launcher
echo [0] Назад
echo.
choice /C 1234V0 /N /M "Выбор: "
if errorlevel 6 exit /b 0
if errorlevel 5 set "RAW=launcher_en" & goto DISPATCH_MAIN
if errorlevel 4 set "RAW=dry_profile" & goto DISPATCH_MAIN
if errorlevel 3 set "RAW=sync_profile" & goto DISPATCH_MAIN
if errorlevel 2 set "RAW=compare_profile" & goto DISPATCH_MAIN
if errorlevel 1 set "RAW=list_profiles" & goto DISPATCH_MAIN
goto MAIN

:DISPATCH_MAIN
if /I "%RAW%"=="list_profiles" goto LIST_PROFILES
if /I "%RAW%"=="compare_profile" goto COMPARE_PROFILE
if /I "%RAW%"=="sync_profile" goto SYNC_PROFILE
if /I "%RAW%"=="dry_profile" goto DRY_PROFILE
if /I "%RAW%"=="launcher_en" goto LAUNCHER_EN
if /I "%RAW%"=="back" exit /b 0
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:LIST_PROFILES
if not exist "%DEFAULT_PROFILES%" (
  echo [ERROR] Конфиг профилей не найден:
  echo %DEFAULT_PROFILES%
  goto RETURN_TO_MENU
)
call :RUNPY "%CORE_DIR%\main.py" pairs --pairs-config "%DEFAULT_PROFILES%"
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:COMPARE_PROFILE
call :PICK_PROFILE PROFILE_NAME
if not defined PROFILE_NAME goto MAIN
call :GET_PROFILE_PATHS compare_profile "%PROFILE_NAME%"
if defined PICKER_USED exit /b %ERRORLEVEL%
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" compare --pair "%PROFILE_NAME%" --source "%SOURCE%" --target "%TARGET%" --pairs-config "%DEFAULT_PROFILES%" %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:SYNC_PROFILE
call :PICK_PROFILE PROFILE_NAME
if not defined PROFILE_NAME goto MAIN
call :GET_PROFILE_PATHS sync_profile "%PROFILE_NAME%"
if defined PICKER_USED exit /b %ERRORLEVEL%
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync --pair "%PROFILE_NAME%" --source "%SOURCE%" --target "%TARGET%" --pairs-config "%DEFAULT_PROFILES%" %MASK_ARGS%
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:DRY_PROFILE
call :PICK_PROFILE PROFILE_NAME
if not defined PROFILE_NAME goto MAIN
call :GET_PROFILE_PATHS dry_profile "%PROFILE_NAME%"
if defined PICKER_USED exit /b %ERRORLEVEL%
if not defined SOURCE goto MAIN
if not defined TARGET goto MAIN
call :BUILD_MASK_ARGS
call :RUNPY "%CORE_DIR%\main.py" sync --pair "%PROFILE_NAME%" --source "%SOURCE%" --target "%TARGET%" --pairs-config "%DEFAULT_PROFILES%" %MASK_ARGS% --dry-run
if errorlevel 1 goto ACTION_FAILED
goto RETURN_TO_MENU

:LAUNCHER_EN
if exist "%BASE_DIR%\launcher_profiles.cmd" (
  call "%BASE_DIR%\launcher_profiles.cmd"
  if errorlevel 1 goto ACTION_FAILED
  goto RETURN_TO_MENU
)
echo [ERROR] Английский launcher профилей не найден.
goto RETURN_TO_MENU

:PICK_PROFILE
set "%~1="
if not exist "%DEFAULT_PROFILES%" (
  echo [ERROR] Конфиг профилей не найден:
  echo %DEFAULT_PROFILES%
  goto :eof
)
if defined FZF_CMD goto PICK_PROFILE_FZF
goto PICK_PROFILE_CMD

:PICK_PROFILE_FZF
call :WRITE_PROFILE_MENU
if not defined PROFILE_COUNT goto PICK_PROFILE_CLEANUP
"%FZF_CMD%" --prompt="audion@disk-auditor [PROFILE-RU] > " --pointer=">" --header="Выбери профиль. *_backup профили - BACKUP-MIRROR." --layout=reverse --border=rounded --info=hidden --margin=1,2 < "%PROFILE_MENU_FILE%" > "%PROFILE_RES_FILE%"
set "PROFILE_CHOICE="
set /p PROFILE_CHOICE=<"%PROFILE_RES_FILE%"
if not defined PROFILE_CHOICE goto PICK_PROFILE_CLEANUP
for /f "tokens=2 delims=|" %%a in ("%PROFILE_CHOICE%") do set "%~1=%%a"
call :TRIM %~1
goto PICK_PROFILE_CLEANUP

:PICK_PROFILE_CMD
echo.
echo Сохранённые профили:
call :COLLECT_PROFILES
if not defined PROFILE_COUNT goto PICK_PROFILE_CLEANUP
call :PROMPT_TEXT PROFILE_INDEX "Номер профиля"
if not defined PROFILE_INDEX goto PICK_PROFILE_CLEANUP
call :TRIM PROFILE_INDEX
set "PROFILE_INDEX_INVALID="
for /f "delims=0123456789" %%a in ("%PROFILE_INDEX%") do set "PROFILE_INDEX_INVALID=%%a"
if defined PROFILE_INDEX_INVALID (
  echo [ERROR] Номер профиля должен быть числом.
  goto PICK_PROFILE_CLEANUP
)
set /a PROFILE_INDEX_NUM=%PROFILE_INDEX% 2>nul
if !PROFILE_INDEX_NUM! LSS 1 (
  echo [ERROR] Номер профиля вне диапазона.
  goto PICK_PROFILE_CLEANUP
)
if !PROFILE_INDEX_NUM! GTR !PROFILE_COUNT! (
  echo [ERROR] Номер профиля вне диапазона.
  goto PICK_PROFILE_CLEANUP
)
for %%n in (!PROFILE_INDEX_NUM!) do set "%~1=!PROFILE_%%n!"

:PICK_PROFILE_CLEANUP
set "PROFILE_INDEX="
set "PROFILE_INDEX_NUM="
set "PROFILE_INDEX_INVALID="
set "PROFILE_CHOICE="
if defined PROFILE_COUNT for /l %%n in (1,1,!PROFILE_COUNT!) do set "PROFILE_%%n="
set "PROFILE_COUNT="
goto :eof

:COLLECT_PROFILES
set "PROFILE_COUNT="
for /f "usebackq delims=" %%a in (`cmd /d /c ""%PYTHON_CMD%" %PYTHON_ARGS% "%CORE_DIR%\main.py" pairs --pairs-config "%DEFAULT_PROFILES%" --names-only"`) do (
  if not defined PROFILE_COUNT set "PROFILE_COUNT=0"
  set /a PROFILE_COUNT+=1
  set "PROFILE_!PROFILE_COUNT!=%%a"
  echo [!PROFILE_COUNT!] %%a
)
if not defined PROFILE_COUNT (
  echo [ERROR] Сохранённые профили не найдены.
)
goto :eof

:WRITE_PROFILE_MENU
if exist "%PROFILE_MENU_FILE%" del /q "%PROFILE_MENU_FILE%" >nul 2>nul
call :COLLECT_PROFILES
if not defined PROFILE_COUNT goto :eof
for /l %%n in (1,1,!PROFILE_COUNT!) do (
  >>"%PROFILE_MENU_FILE%" echo [%%n] !PROFILE_%%n! ^| !PROFILE_%%n! ^| configured profile / pair
)
goto :eof

:GET_PROFILE_PATHS
set "SOURCE="
set "TARGET="
set "FILE_MASK="
set "MASK_ARGS="
set "PICKER_USED="
if defined FZF_CMD goto GET_PROFILE_PATHS_FZF
goto GET_PROFILE_PATHS_FALLBACK

:GET_PROFILE_PATHS_FZF
call :WRITE_PATH_MODE_MENU
"%FZF_CMD%" --prompt="audion@disk-auditor [PROFILE-PATHS-RU] > " --pointer=">" --header="Выбери способ ввода source и target." --layout=reverse --border=rounded --info=hidden --margin=1,2 < "%PATH_MENU_FILE%" > "%PATH_RES_FILE%"
set "PATH_CHOICE="
set /p PATH_CHOICE=<"%PATH_RES_FILE%"
if not defined PATH_CHOICE goto :eof
for /f "tokens=2 delims=|" %%a in ("%PATH_CHOICE%") do set "PATH_MODE=%%a"
call :TRIM PATH_MODE
if /I "%PATH_MODE%"=="picker" goto GET_PROFILE_PATHS_PICKER
call :PROMPT_PATHS SOURCE TARGET FILE_MASK
goto :eof

:GET_PROFILE_PATHS_FALLBACK
echo.
echo [1] Ручной ввод
echo [2] Folder picker
echo.
choice /C 12 /N /M "Выбери ввод путей [1-2]: "
if errorlevel 2 goto GET_PROFILE_PATHS_PICKER
call :PROMPT_PATHS SOURCE TARGET FILE_MASK
goto :eof

:GET_PROFILE_PATHS_PICKER
set "PICKER_USED=1"
call "%CORE_DIR%\launcher_picker_profiles.cmd" %1 %2 "%FILE_MASK%"
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
echo [INFO] Smoke-check launcher профилей завершён.
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
> "%MENU_FILE%" echo [01] ПОКАЗАТЬ СОХРАНЁННЫЕ ПРОФИЛИ             ^| list_profiles    ^| показать saved pairs из config
>>"%MENU_FILE%" echo [02] СРАВНИТЬ СОХРАНЁННЫЙ ПРОФИЛЬ             ^| compare_profile  ^| выбрать pair и сравнить
>>"%MENU_FILE%" echo [03] ЗАПУСТИТЬ СОХРАНЁННЫЙ ПРОФИЛЬ            ^| sync_profile     ^| выполнить режим, заданный профилем
>>"%MENU_FILE%" echo [04] DRY RUN СОХРАНЁННОГО ПРОФИЛЯ             ^| dry_profile      ^| превью режима, заданного профилем
>>"%MENU_FILE%" echo [31] ENGLISH PROFILES LAUNCHER                ^| launcher_en      ^| переключиться на english UI
>>"%MENU_FILE%" echo [00] НАЗАД                                    ^| back             ^| вернуться назад
goto :eof

:WRITE_PATH_MODE_MENU
> "%PATH_MENU_FILE%" echo [01] РУЧНОЙ ВВОД                         ^| manual           ^| ввести source и target вручную
>>"%PATH_MENU_FILE%" echo [02] FOLDER PICKER                       ^| picker           ^| использовать Windows folder picker
goto :eof

:PROMPT_TEXT
set "%~1="
echo.
setlocal DisableDelayedExpansion
set /p "_AUDION_TEXT=%~2: "
endlocal & set "%~1=%_AUDION_TEXT%"
goto :eof

:PROMPT_PATHS
set "%~1="
set "%~2="
if not "%~3"=="" set "%~3="
echo.
setlocal DisableDelayedExpansion
set /p "_AUDION_SOURCE=Папка source: "
set /p "_AUDION_TARGET=Папка target: "
if not "%~3"=="" set /p "_AUDION_MASK=Какие файлы обрабатываем? Введите маски имени и/или расширения через ;, например: *.xxx; *xyz*.yyy; *.zzz (Enter = фильтры профиля или все файлы): "
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
for %%F in ("%MENU_FILE%" "%RES_FILE%" "%PATH_MENU_FILE%" "%PATH_RES_FILE%" "%PROFILE_MENU_FILE%" "%PROFILE_RES_FILE%") do (
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
