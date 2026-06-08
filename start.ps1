<#
.SYNOPSIS
    Logos 一键启动脚本（Docker 方式）
.DESCRIPTION
    从仓库根目录执行，自动完成：
    1. 生成默认配置（如不存在）
    2. 构建并启动后端 + 前端容器
    3. 等待服务就绪
    4. 打开浏览器

    要求：Docker Desktop 已安装并运行。
.EXAMPLE
    .\start.ps1              # 构建 + 启动 + 打开浏览器
    .\start.ps1 -NoBrowser   # 构建 + 启动，不打开浏览器
    .\start.ps1 -Rebuild     # 强制重建镜像 + 启动
    .\start.ps1 -Down        # 停止所有容器
    .\start.ps1 -Logs        # 跟踪日志
#>

param(
    [switch]$NoBrowser,  # 启动后不自动打开浏览器
    [switch]$Rebuild,    # 强制重建镜像（不使用缓存）
    [switch]$Down,       # 停止所有容器
    [switch]$Logs,       # 启动后跟踪日志
    [switch]$Help        # 显示帮助
)

if ($Help) {
    Get-Help $PSCommandPath
    exit 0
}

$ROOT = $PSScriptRoot

# ─── 停止 ───────────────────────────────────────────────────────────
if ($Down) {
    Write-Host "⏹️  停止 Logos 容器..." -ForegroundColor Cyan
    Set-Location $ROOT
    docker compose down
    Write-Host "✅ 已停止" -ForegroundColor Green
    exit 0
}

# ─── 确保 Docker 运行 ───────────────────────────────────────────────
try {
    $null = docker info --format "{{.ServerVersion}}" 2>&1 | Out-Null
    if (-not $?) { throw "Docker 未运行" }
} catch {
    Write-Host "❌ Docker Desktop 未运行，请先启动 Docker Desktop。" -ForegroundColor Red
    exit 1
}

Set-Location $ROOT

# ─── 自动生成默认配置 ─────────────────────────────────────────────
if (-not (Test-Path "config/local.yaml")) {
    Write-Host "📝 生成默认配置 config/local.yaml（无 API Key = 桩后端模式）..." -ForegroundColor Yellow
    @"
# 自动生成 — 无 API Key，使用桩后端 LLM
# 如需调用真实模型，取消注释并填入：
# llm:
#   api_key: "sk-..."
#   base_url: "https://api.deepseek.com/v1"
#   model: "deepseek-chat"
"@ | Out-File -FilePath "config/local.yaml" -Encoding utf8
}

# ─── 构建镜像 ──────────────────────────────────────────────────────
if ($Rebuild) {
    Write-Host "🏗️  强制重建 Docker 镜像..." -ForegroundColor Yellow
    docker compose build --no-cache
} else {
    Write-Host "🏗️  构建 Docker 镜像（如有变更）..." -ForegroundColor Yellow
    docker compose build
}

if (-not $?) {
    Write-Host "❌ 构建失败" -ForegroundColor Red
    exit 1
}

# ─── 启动容器 ──────────────────────────────────────────────────────
Write-Host "🚀 启动 Logos（后端 :8000 + 前端 :3000）..." -ForegroundColor Green
docker compose up -d

if (-not $?) {
    Write-Host "❌ 启动失败" -ForegroundColor Red
    exit 1
}

# ─── 等待就绪 ──────────────────────────────────────────────────────
Write-Host "⏳ 等待后端就绪..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # 还没好
    }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
}
Write-Host ""

if (-not $ready) {
    Write-Host "⚠️  后端未在预期时间内就绪，请手动检查：docker compose logs" -ForegroundColor Yellow
} else {
    Write-Host "✅ 后端就绪" -ForegroundColor Green
}

# ─── 打开浏览器 ────────────────────────────────────────────────────
if (-not $NoBrowser) {
    Write-Host "🌐 打开 http://localhost:3000 ..." -ForegroundColor Green
    Start-Process "http://localhost:3000"
}

# ─── 提示 ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Logos 已启动                          ║" -ForegroundColor Cyan
Write-Host "║  前端: http://localhost:3000           ║" -ForegroundColor Cyan
Write-Host "║  后端: http://localhost:8000           ║" -ForegroundColor Cyan
Write-Host "║  停止: .\start.ps1 -Down              ║" -ForegroundColor Cyan
Write-Host "║  日志: .\start.ps1 -Logs              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan

if ($Logs) {
    Write-Host "📋 跟踪日志（Ctrl+C 停止，容器继续运行）..." -ForegroundColor Cyan
    docker compose logs -f
}
