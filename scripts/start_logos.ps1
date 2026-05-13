# Logos 一键启动：新窗口后端 + 新窗口 Vite + 新窗口 Electron（文件须为 UTF-8 带 BOM，供 Windows PowerShell 5.1 正确解析中文）。
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $RepoRoot

$Py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Py)) {
    Write-Host "未找到虚拟环境：$Py" -ForegroundColor Red
    Write-Host '请在仓库根执行：python -m venv .venv ; .\.venv\Scripts\pip install -e ".[dev]"' -ForegroundColor Yellow
    exit 1
}

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npmCmd) {
    Write-Host "未找到 npm，请先安装 Node.js：https://nodejs.org/" -ForegroundColor Red
    exit 1
}

$BackendScript = Join-Path $RepoRoot "scripts\run_backend_stub.py"
if (-not (Test-Path -LiteralPath $BackendScript)) {
    Write-Host "未找到后端脚本：$BackendScript" -ForegroundColor Red
    exit 1
}

$GuiDir = Join-Path $RepoRoot "src\gui"
$ElectronDir = Join-Path $RepoRoot "src\electron"
if (-not (Test-Path -LiteralPath $GuiDir)) {
    Write-Host "未找到前端目录：$GuiDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath $ElectronDir)) {
    Write-Host "未找到 Electron 目录：$ElectronDir" -ForegroundColor Red
    exit 1
}

Write-Host "仓库根: $RepoRoot" -ForegroundColor Cyan
Write-Host "正在打开后端窗口 http://127.0.0.1:8000 …" -ForegroundColor Cyan

$BackendPs = "`$Host.UI.RawUI.WindowTitle = 'Logos Backend'; & `"$Py`" `"$BackendScript`""
Start-Process powershell -WorkingDirectory $RepoRoot -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $BackendPs
)

Start-Sleep -Seconds 2

Write-Host "正在打开 Vite 窗口 http://127.0.0.1:5173 （/api 代理到 8000）…" -ForegroundColor Cyan
$ViteCmd = "`$Host.UI.RawUI.WindowTitle = 'Logos Vite'; if (-not (Test-Path -LiteralPath 'node_modules')) { npm install }; npm run dev"
Start-Process powershell -WorkingDirectory $GuiDir -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $ViteCmd
)

# Electron loadURL 依赖 Vite 已监听；首次 Vite 编译可能较慢
$ViteWarmupSeconds = 5
Write-Host "等待约 ${ViteWarmupSeconds} 秒以便 Vite 就绪，再打开 Electron 壳 …" -ForegroundColor DarkGray
Start-Sleep -Seconds $ViteWarmupSeconds

Write-Host "正在打开 Electron 窗口（加载上述 Vite 地址）…" -ForegroundColor Cyan
$ElectronCmd = "`$Host.UI.RawUI.WindowTitle = 'Logos Electron'; `$env:LOGOS_ELECTRON_SKIP_BACKEND='1'; if (-not (Test-Path -LiteralPath 'node_modules')) { npm run install:with-mirror }; npm run electron:dev"
Start-Process powershell -WorkingDirectory $ElectronDir -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $ElectronCmd
)

Write-Host ""
Write-Host "已在新窗口启动：Logos Backend、Logos Vite、Logos Electron。" -ForegroundColor Green
Write-Host "若 Electron 白屏或告警未检测到 5173，请在 Vite 窗口确认编译完成后再于 Electron 窗口按 Ctrl+R 或重启 Electron。" -ForegroundColor Yellow
Write-Host "关闭各窗口即停止对应进程；本启动脚本窗口可直接关闭。" -ForegroundColor DarkGray
