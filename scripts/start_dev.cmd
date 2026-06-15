@echo off
setlocal enabledelayedexpansion
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

echo Waiting for Vite (port 5173)...
set WAIT_COUNT=0
:wait_vite
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "& {param($p=5173) try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',$p);$c.Close();exit 0}catch{exit 1}}" 2>nul
if errorlevel 1 (
    set /a WAIT_COUNT+=1
    if !WAIT_COUNT! lss 15 goto wait_vite
    echo [WARN] Vite not ready after ~30s, starting Electron anyway...
)

echo [3/3] Starting Electron...
set LOGOS_ELECTRON_SKIP_BACKEND=1
start "Logos Electron" cmd /c "cd /d "%ELECTRON_DIR%" && npm run electron:dev:fast"

endlocal
echo.
echo All services launched. Close this window when done.
