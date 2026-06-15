# Logos 快速启动 Electron：按需拉起后端/Vite（端口探测 + 轮询），跳过固定等待与多余 tsc。
# 文件须为 UTF-8 带 BOM，供 Windows PowerShell 5.1 正确解析中文。
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Test-TcpPortOpen {
    param(
        [string] $HostName = "127.0.0.1",
        [int] $Port,
        [int] $TimeoutMs = 400
    )
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $connect = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $connect.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($ok -and $client.Connected) {
            $client.EndConnect($connect)
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $client) {
            $client.Close()
        }
    }
}

function Test-BackendHealth {
  param([int] $TimeoutSec = 2)
  try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec $TimeoutSec | Out-Null
    return $true
  }
  catch {
    return $false
  }
}

function Wait-DevReady {
  param(
    [int] $TimeoutSec = 120,
    [int] $PollMs = 300
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    $viteOk = Test-TcpPortOpen -Port 5173
    $backendOk = Test-BackendHealth
    if ($viteOk -and $backendOk) {
      return $true
    }
    Start-Sleep -Milliseconds $PollMs
  }
  return $false
}

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

$BackendScript = Join-Path $RepoRoot "scripts\run_dev_backend.py"
$GuiDir = Join-Path $RepoRoot "src\gui"
$ElectronDir = Join-Path $RepoRoot "src\electron"

foreach ($pair in @(
    @{ Path = $BackendScript; Label = "后端脚本" },
    @{ Path = $GuiDir; Label = "前端目录" },
    @{ Path = $ElectronDir; Label = "Electron 目录" }
  )) {
  if (-not (Test-Path -LiteralPath $pair.Path)) {
    Write-Host "未找到 $($pair.Label)：$($pair.Path)" -ForegroundColor Red
    exit 1
  }
}

$backendReady = Test-BackendHealth
$viteReady = Test-TcpPortOpen -Port 5173

Write-Host "仓库根: $RepoRoot" -ForegroundColor Cyan
Write-Host ("后端 :8000 {0} | Vite :5173 {1}" -f $(if ($backendReady) { "已就绪" } else { "未检测到" }), $(if ($viteReady) { "已就绪" } else { "未检测到" })) -ForegroundColor DarkGray

if (-not $backendReady) {
  Write-Host "正在打开后端窗口 http://127.0.0.1:8000 …" -ForegroundColor Cyan
  $BackendPs = "`$Host.UI.RawUI.WindowTitle = 'Logos Backend'; & `"$Py`" `"$BackendScript`""
  Start-Process powershell -WorkingDirectory $RepoRoot -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $BackendPs
  )
}

if (-not $viteReady) {
  Write-Host "正在打开 Vite 窗口 http://127.0.0.1:5173 …" -ForegroundColor Cyan
  $ViteCmd = "`$Host.UI.RawUI.WindowTitle = 'Logos Vite'; if (-not (Test-Path -LiteralPath 'node_modules')) { npm install }; npm run dev"
  Start-Process powershell -WorkingDirectory $GuiDir -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $ViteCmd
  )
}

if (-not $backendReady -or -not $viteReady) {
  Write-Host "轮询等待后端 health 与 Vite :5173（最多约 120 秒）…" -ForegroundColor DarkGray
  if (-not (Wait-DevReady)) {
    Write-Host "超时：请确认 Backend / Vite 窗口无报错后重试本脚本。" -ForegroundColor Red
    exit 1
  }
  Write-Host "开发服务已就绪。" -ForegroundColor Green
}

Write-Host "正在打开 Electron（electron:dev:fast，按需跳过 tsc）…" -ForegroundColor Cyan
$ElectronCmd = "`$Host.UI.RawUI.WindowTitle = 'Logos Electron'; `$env:LOGOS_ELECTRON_SKIP_BACKEND='1'; if (-not (Test-Path -LiteralPath 'node_modules')) { npm run install:with-mirror }; npm run electron:dev:fast"
Start-Process powershell -WorkingDirectory $ElectronDir -ArgumentList @(
  "-NoExit",
  "-NoProfile",
  "-Command",
  $ElectronCmd
)

Write-Host ""
Write-Host "已启动 Electron 壳（LOGOS_ELECTRON_SKIP_BACKEND=1）。" -ForegroundColor Green
Write-Host "若白屏，请在 Vite 窗口确认编译完成后于 Electron 窗口按 Ctrl+R。" -ForegroundColor Yellow
Write-Host "本脚本窗口可直接关闭。" -ForegroundColor DarkGray
