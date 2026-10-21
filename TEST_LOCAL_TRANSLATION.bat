@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PROJECT_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PROJECT_PYTHON%" (
  echo [ERROR] Project Python is missing: "%PROJECT_PYTHON%"
  pause
  exit /b 1
)
"%PROJECT_PYTHON%" "%~dp0tools\test_local_translation.py"
set "TEST_EXIT=%ERRORLEVEL%"
echo.
echo Diagnostic log: %~dp0logs\local-translation-test.log
pause
exit /b %TEST_EXIT%
