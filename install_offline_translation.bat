@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup_windows.bat first. & pause & exit /b 1)
set "ARGOS_PACKAGES_DIR=%CD%\models\argos-packages"
set "XDG_DATA_HOME=%CD%\.local-data"
set "XDG_CONFIG_HOME=%CD%\.local-config"
set "XDG_CACHE_HOME=%CD%\.local-cache"
.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
if errorlevel 1 (
  echo Could not install offline translation dependencies.
  pause
  exit /b 1
)
.venv\Scripts\python.exe install_argos_ko.py
pause
