@echo off
REM 双击运行：快速启动 Electron（按需拉起后端/Vite，端口轮询；详见 scripts\start_logos_electron.ps1）
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_logos_electron.ps1"
if errorlevel 1 pause
