@echo off
cd /d "%~dp0.."
title Logos Dev Launcher

set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "BACKEND=%ROOT%\original_scripts\run_dev_backend.py"
set "GUI_DIR=%ROOT%\src\gui"
set "ELECTRON_DIR=%ROOT%\src\electron"

if not exist "%PY%" (
    echo [ERR] .venv not found. Run: python -m venv .venv
    pause & exit /b 1
)
if not exist "%BACKEND%" (
    echo [ERR] Backend script not found
    pause & exit /b 1
)

echo [1/3] Starting backend...
start "Logos Backend" "%PY%" "%BACKEND%"

echo [2/3] Starting Vite dev server...
start "Logos Vite" cmd /c "cd /d "%GUI_DIR%" && if not exist node_modules npm install && npm run dev"

echo [3/3] Starting Electron...
start "Logos Electron" cmd /c "set LOGOS_ELECTRON_SKIP_BACKEND=1 && cd /d "%ELECTRON_DIR%" && npm run electron:dev:fast"

echo.
echo All services launched. Close this window when done.
