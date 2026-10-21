@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment missing. Run INSTALL_AND_START.bat first.
    pause
    exit /b 1
)
set "ARGOS_PACKAGES_DIR=%CD%\models\argos-packages"
set "ARGOS_DEVICE_TYPE=cpu"
set "XDG_DATA_HOME=%CD%\.local-data"
set "XDG_CONFIG_HOME=%CD%\.local-config"
set "XDG_CACHE_HOME=%CD%\.local-cache"
set "HF_HOME=%CD%\.cache\huggingface"
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo [ERROR] Interpreter stopped with an error.
    pause
    exit /b 1
)
exit /b 0
