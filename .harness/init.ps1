#Requires -Version 5.1
<#
.SYNOPSIS
    Standard initialization for FPGA_transDATA V6.4 harness.
.DESCRIPTION
    Run this when starting a new session or after a long break.
    Checks environment, reports project status, ensures clean restart path.
#>
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$subProjectRoot = Join-Path $projectRoot "PUF_dataTransFreq_v60_capture"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FPGA_transDATA V6.4 — Session Init" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 0. Harness state initialization
Write-Host "[init] Harness state check..." -ForegroundColor Cyan
$stateDir = Join-Path $scriptDir "state"
$logsDir = Join-Path $scriptDir "logs"
$qaDir = Join-Path $scriptDir "qa"

# Ensure directories exist
foreach ($dir in @($stateDir, $logsDir, $qaDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  [FIX] Created missing directory: $dir" -ForegroundColor Yellow
    }
}

# Clean stale lock files
$lockFile = Join-Path $stateDir "lock.pid"
if (Test-Path $lockFile) {
    $lockContent = Get-Content $lockFile -Raw -ErrorAction SilentlyContinue
    Write-Warning "[init] Stale lock file found: $lockContent"
    Remove-Item $lockFile -Force
    Write-Host "  [FIX] Removed stale lock file" -ForegroundColor Green
}

# Check required harness files
$requiredFiles = @(
    (Join-Path $scriptDir "feature_list.json"),
    (Join-Path $scriptDir "qa_report_template.md"),
    (Join-Path $scriptDir "sim_regressions.json")
)
foreach ($f in $requiredFiles) {
    if (-not (Test-Path $f)) {
        Write-Warning "  [init] Missing harness file: $f"
    }
}
Write-Host "[init] Harness state OK" -ForegroundColor Green
Write-Host ""

# 0.5 -- Show subproject status
$wsName = "PUF_dataTransFreq_v60_capture"
$rtlCnt = (Get-ChildItem (Join-Path $subProjectRoot "rtl") -Filter "*.v").Count
$bit = Join-Path (Join-Path $subProjectRoot "build") "transient_puf_v60_top.bit"
$hasBit = Test-Path $bit
Write-Host "[init] Project: $wsName | rtl: $rtlCnt | bit: $(if ($hasBit) { 'yes' } else { 'no' })" -ForegroundColor Cyan
Write-Host ""

# 1. Read AGENTS.md (map)
$agentsFile = Join-Path $projectRoot "AGENTS.md"
if (Test-Path $agentsFile) {
    Write-Host "[init] AGENTS.md found." -ForegroundColor Green
} else {
    Write-Warning "[init] AGENTS.md not found!"
}

# 2. Read feature_list.json (now lives in .harness/)
$featureFile = Join-Path $scriptDir "feature_list.json"
if (Test-Path $featureFile) {
    $features = Get-Content $featureFile -Encoding UTF8 | ConvertFrom-Json
    $done = ($features.features | Where-Object { $_.status -eq "done" }).Count
    $inProgress = ($features.features | Where-Object { $_.status -eq "in-progress" }).Count
    $pending = ($features.features | Where-Object { $_.status -eq "pending" }).Count
    Write-Host "[init] Features: $done done, $inProgress in-progress, $pending pending" -ForegroundColor Green
} else {
    Write-Warning "[init] feature_list.json not found!"
}

# 3. Read PROGRESS.md
$progressFile = Join-Path $subProjectRoot "PROGRESS.md"
if (Test-Path $progressFile) {
    $content = Get-Content $progressFile -Raw
    if ($content -match "## 当前任务\s*\n(.+)") {
        Write-Host "[init] Current task: $($matches[1].Trim())" -ForegroundColor Cyan
    }
    if ($content -match "## 阻塞\s*\n(.+)") {
        $blocker = $matches[1].Trim()
        if ($blocker -ne "none" -and $blocker -ne "") {
            Write-Warning "[init] Blocker: $blocker"
        }
    }
}

# 4. Environment check
Write-Host ""
Write-Host "[init] Running env check..." -ForegroundColor Cyan
$envScript = Join-Path $subProjectRoot "scripts\env_check.ps1"
if (Test-Path $envScript) {
    & $envScript
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[init] Env check failed. Fix before proceeding."
        exit 1
    }
} else {
    Write-Warning "[init] env_check.ps1 not found!"
}

# 5. Last check result
$checkFile = Join-Path (Join-Path (Join-Path $projectRoot ".harness") "state") "last_check.json"
if (Test-Path $checkFile) {
    $lastCheck = Get-Content $checkFile | ConvertFrom-Json
    Write-Host ""
    Write-Host "[init] Last check result ($($lastCheck.timestamp)):" -ForegroundColor Cyan
    $color = if ($lastCheck.overall) { "Green" } else { "Red" }
    Write-Host "  overall: $($lastCheck.overall) | rtl_hash: $($lastCheck.rtl_hash)" -ForegroundColor $color
}

# 6. Git branch check -- remind user to checkout feature branch
Write-Host ""
try {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $uncommitted = git status --short 2>$null
    if ($branch -eq "main" -or $branch -eq "master") {
        if ($uncommitted) {
            Write-Warning "[init] You are on '$branch' with UNCOMMITTED changes."
            Write-Warning "[init] STRONGLY RECOMMENDED: create a feature branch BEFORE making changes!"
            Write-Host "      git checkout -b feat/<your-task>" -ForegroundColor Yellow
        } else {
            Write-Host "[init] On '$branch' branch. Clean working tree." -ForegroundColor Green
        }
    } else {
        Write-Host "[init] On feature branch: $branch" -ForegroundColor Green
    }
} catch {
    Write-Host "[init] Git not available, skipping branch check" -ForegroundColor Cyan
}

# 7. PROGRESS.md freshness check
$progressFile = Join-Path $subProjectRoot "PROGRESS.md"
if (Test-Path $progressFile) {
    $progressInfo = Get-Item $progressFile
    $daysOld = [math]::Round(((Get-Date) - $progressInfo.LastWriteTime).TotalDays, 1)
    if ($daysOld -gt 1) {
        Write-Warning "[init] PROGRESS.md is $daysOld days old. Update before coding!"
        Write-Host "      Read it → do work → update '最后更新/当前任务/阻塞/下一步' → say '收工'" -ForegroundColor Yellow
    } else {
        Write-Host "[init] PROGRESS.md is up to date ($daysOld days old)." -ForegroundColor Green
    }
}

# 8. Bitstream status
Write-Host ""
Write-Host "[init] Bitstream status:" -ForegroundColor Cyan
$bit = Join-Path (Join-Path $subProjectRoot "build") "transient_puf_v60_top.bit"
if (Test-Path $bit) {
    $info = Get-Item $bit
    Write-Host ("  ${wsName}: $($info.LastWriteTime) ($([math]::Round($info.Length/1024,1)) KB)" ) -ForegroundColor Green
} else {
    Write-Host "  ${wsName}: no bitstream yet" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "[init] ⚠️ MANDATORY: Read .harness/lessons.md (27 rules) before coding" -ForegroundColor Yellow
Write-Host ""
Write-Host "[init] Ready. Use '.\.harness\tasks.ps1 check' before making changes." -ForegroundColor Green
