@echo off
REM 双击运行：在仓库根启动后端、Vite、Electron（各新窗口；详见 scripts\start_logos.ps1）
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_logos.ps1"
if errorlevel 1 pause
