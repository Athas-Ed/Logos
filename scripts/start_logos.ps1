# Logos 一键启动：新窗口后端 + 本窗口 Vite（文件须为 UTF-8 带 BOM，供 Windows PowerShell 5.1 正确解析中文）。
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

Write-Host "启动 Vite http://localhost:5173 （/api 代理到 8000）…" -ForegroundColor Cyan
Write-Host "Ctrl+C 仅结束前端；请单独关闭后端窗口。" -ForegroundColor DarkGray

Set-Location -LiteralPath (Join-Path $RepoRoot "src\gui")
if (-not (Test-Path -LiteralPath "node_modules")) {
    npm install
}
npm run dev
