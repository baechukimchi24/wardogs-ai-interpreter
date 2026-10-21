@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Cannot open the extracted app folder.
    pause
    exit /b 1
)
echo ==========================================================
echo WARDOGS AI INTERPRETER v0.9 - FIRST RUN SETUP
 echo No Visual Studio, no C++ compiler and no Ollama needed.
 echo Python and AI translation models download on first use.
echo ==========================================================
where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Windows PowerShell is required.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] Installation incomplete. See install.log in this folder.
    echo No changes were made to your game microphone or VAC routing.
    pause
    exit /b 1
)
echo.
echo [OK] First-run setup complete. Starting application...
call "%~dp0START.bat"
if errorlevel 1 (
    echo [ERROR] App startup failed. Please copy the console error.
    pause
    exit /b 1
)
exit /b 0
