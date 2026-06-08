@echo off
cd /d "%~dp0"
title Logos Docker Launcher

docker info >nul 2>&1
if errorlevel 1 goto err_docker

if not exist config\local.yaml goto genconfig
goto build

:genconfig
echo Creating default config/local.yaml (stub LLM mode)...
echo # Auto-generated, no API key > config\local.yaml
echo # To use real model, uncomment: >> config\local.yaml
echo # llm: >> config\local.yaml

:build
echo Building Docker images (first time may be slow)...
docker compose build
if errorlevel 1 goto err_build

echo Starting Logos...
docker compose up -d
if errorlevel 1 goto err_start

echo Waiting for backend...
set WAIT_COUNT=0

:wait_loop
curl -sf http://localhost:8000/api/v1/health >nul 2>&1
if not errorlevel 1 goto ready
set /a WAIT_COUNT=WAIT_COUNT+1
if %WAIT_COUNT% geq 30 goto timeout
timeout /t 2 /nobreak >nul 2>&1
goto wait_loop

:ready
echo Backend is ready.
goto open_browser

:timeout
echo [WARN] Backend health check timed out. Last 30 lines of backend logs:
docker compose logs --tail=30 logos-backend
echo.
echo You can retry: docker compose logs -f

:open_browser
start http://localhost:3000
echo.
echo +-----------------------------------+
echo  Logos is running
echo  Frontend : http://localhost:3000
echo  Backend  : http://localhost:8000
echo  Stop     : docker compose down
echo +-----------------------------------+
echo.
echo Close this window. Containers run in background.
pause
exit /b 0

:err_docker
echo [ERROR] Docker Desktop is not running. Please start Docker Desktop first.
pause
exit /b 1

:err_build
echo [ERROR] Build failed.
pause
exit /b 1

:err_start
echo [ERROR] Failed to start services. Last 30 lines of backend logs:
docker compose logs --tail=30 logos-backend
echo.
echo Check Docker Desktop or run: docker compose logs -f
pause
exit /b 1
