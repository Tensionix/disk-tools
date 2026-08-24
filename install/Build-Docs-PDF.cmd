@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"

set "PYTHON_EXE=%ROOT%\runtime\python.exe"
if not exist "%PYTHON_EXE%" (
  set "PYTHON_EXE=E:\TOOLS\Audion Office OCR AI\runtime\python.exe"
)

if not exist "%PYTHON_EXE%" goto ERR_PYTHON

"%PYTHON_EXE%" "%ROOT%\system_core\build_docs_pdf.py" %*
exit /b %errorlevel%

:ERR_PYTHON
echo [ERROR] Python runtime was not found.
echo [INFO] Build the local runtime or install Audion Office OCR AI runtime.
exit /b 1
