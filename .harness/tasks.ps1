#Requires -Version 5.1
# encoding: utf-8
<#
.SYNOPSIS
    Unified harness for FPGA_transDATA V6.6.
.DESCRIPTION
    All dev operations go through this script.
    Usage: .\.harness\tasks.ps1 <command> [options]

.NOTES
    LESSON: PowerShell 5.1 on GBK systems (Chinese Windows) mis-parses UTF-8
    files containing full-width/CJK chars inside executable strings. ALL
    executable strings must use ASCII only. Chinese allowed only in # comments.
#>
param(
    [Parameter(Position=0)]
    [ValidateSet("env","lint","sim","check","build","program","capture","clean","status","done","help")]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$RemainingArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$subProjectRoot = Join-Path $projectRoot "PUF_dataTransFreq_v60_capture"
$logsDir = Join-Path $scriptDir "logs"
$stateDir = Join-Path $scriptDir "state"
$scriptsDir = Join-Path $subProjectRoot "scripts"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logsDir "$Command-$timestamp.log"

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Msg"
    Write-Host $line
    try { Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction Stop } catch {}
}

function Invoke-Hook {
    param([string]$Name, [string[]]$Args = @())
    $hookPath = Join-Path (Join-Path $scriptDir "hooks") "$Name.ps1"
    if (-not (Test-Path $hookPath)) { return 0 }
    try {
        $ec = Run-SubScript $hookPath $Args
        if ($ec -ne 0) { Write-Log "Hook $Name exited with code $ec (non-blocking)" "WARN" }
        return $ec
    } catch {
        Write-Log "Hook $Name failed: $_ (non-blocking)" "WARN"
        return 1
    }
}

function Run-SubScript {
    param([string]$Path, [string[]]$ExtraArgs = @(), [string]$WorkingDirectory = $null)
    if (-not (Test-Path $Path)) {
        Write-Log "Script not found: $Path" "ERROR"
        return 1
    }
    $ext = [System.IO.Path]::GetExtension($Path)
    if ($ext -eq '.py') {
        $pythonPath = "C:/Users/lenovo/AppData/Local/Programs/Python/Python313/python.exe"
        if (-not (Test-Path $pythonPath)) { $pythonPath = "python" }
        & $pythonPath $Path $ExtraArgs
    } else {
        # powershell.exe not always in PATH on all systems; use full system path
        $psExe = if (Get-Command "powershell.exe" -ErrorAction SilentlyContinue) { "powershell.exe" }
                 else { "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" }
        & $psExe -ExecutionPolicy Bypass -File $Path $ExtraArgs
    }
    $ec = $LASTEXITCODE
    if ($ec -ne 0) { Write-Log "$([IO.Path]::GetFileName($Path)) exited with code $ec" "ERROR" }
    return $ec
}

function Get-RtlHash {
    $rtlDir = Join-Path $subProjectRoot "rtl"
    $files = @(Get-ChildItem -Path $rtlDir -Filter "*.v" -ErrorAction Stop | Sort-Object Name)
    if ($files.Count -eq 0) { throw "Get-RtlHash: no .v files under $rtlDir" }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        foreach ($f in $files) {
            $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
            [void]$sha.TransformBlock($bytes, 0, $bytes.Length, $null, 0)
        }
        [void]$sha.TransformFinalBlock([byte[]]@(), 0, 0)
        return ([BitConverter]::ToString($sha.Hash) -replace '-', '').Substring(0, 8)
    } finally { $sha.Dispose() }
}

function Get-Version {
    $topFile = Join-Path (Join-Path $subProjectRoot "rtl") "transient_puf_v60_top.v"
    if (-not (Test-Path $topFile)) { return "unknown" }
    $content = Get-Content $topFile -Raw
    $major = if ($content -match "VERSION_MAJOR\s*=\s*\d+'d(\d+)") { $matches[1] } else { "?" }
    $minor = if ($content -match "VERSION_MINOR\s*=\s*\d+'d(\d+)") { $matches[1] } else { "?" }
    return "V$major.$minor"
}

function Parse-VivadoReports {
    param([string]$BuildDir)
    $result = @{ wns_ns = $null; tns_ns = $null; utilization = @{} }
    $timingRpt = Join-Path $BuildDir "timing_summary.rpt"
    if (Test-Path $timingRpt) {
        $lines = Get-Content $timingRpt -Encoding UTF8
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match 'WNS\(ns\)\s+TNS\(ns\)') {
                $dataIdx = $i + 2
                if ($dataIdx -lt $lines.Count -and $lines[$dataIdx] -match '^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)') {
                    $result.wns_ns = [double]$matches[1]
                    $result.tns_ns = [double]$matches[2]
                }
                break
            }
        }
    }
    $utilRpt = Join-Path $BuildDir "utilization.rpt"
    if (Test-Path $utilRpt) {
        foreach ($line in (Get-Content $utilRpt -Encoding UTF8)) {
            if ($line -match '\|\s*(Slice LUTs|Slice Registers|Block RAM Tile|DSPs|Bonded IOB)\s*\|\s*(\d+)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*([\d\.]+)') {
                $result.utilization[$matches[1] -replace ' ', '_'] = @{ used = [int]$matches[2]; pct = [double]$matches[3] }
            }
        }
    }
    return $result
}

# ---- Lock ----
$lockFile = Join-Path $stateDir "lock.pid"
function Acquire-Lock {
    if (Test-Path $lockFile) {
        Write-Log "Lock held by: $(Get-Content $lockFile -Raw). Delete $lockFile if stale." "ERROR"
        return $false
    }
    "PID=$PID | $Command | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Set-Content $lockFile -Encoding UTF8
    return $true
}
function Release-Lock {
    if (Test-Path $lockFile) { Remove-Item $lockFile -Force -ErrorAction SilentlyContinue }
}

# ---- Commands ----
switch ($Command) {
    "env" {
        Write-Log "Running env check..."
        $ec = Run-SubScript (Join-Path $scriptsDir "env_check.ps1")
        exit $ec
    }

    "lint" {
        Write-Log "Running lint..."
        $ec = Run-SubScript (Join-Path $scriptsDir "lint_all.ps1")
        exit $ec
    }

    "sim" {
        Write-Log "Running simulation..."
        $ec = Run-SubScript (Join-Path $scriptsDir "sim_all.ps1")
        exit $ec
    }

    "check" {
        Write-Log "Running full check: env + lint + sim..."
        Invoke-Hook "pre-check"
        if (-not (Acquire-Lock "check")) { exit 1 }

        $ec = 0
        $ec = Run-SubScript (Join-Path $scriptsDir "env_check.ps1")
        if ($ec -eq 0) { $ec = Run-SubScript (Join-Path $scriptsDir "lint_all.ps1") }
        if ($ec -eq 0) { $ec = Run-SubScript (Join-Path $scriptsDir "sim_all.ps1") }

        if ($ec -eq 0) {
            $currentHash = Get-RtlHash
            $version = Get-Version
            $checkFile = Join-Path $stateDir "last_check.json"
            @{ timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss"); rtl_hash = $currentHash; overall = $true } |
                ConvertTo-Json | Set-Content $checkFile -Encoding UTF8
            Write-Log "Check PASSED ($version, rtl=$currentHash)" "INFO"
            Write-Host "`n[ACID] Check passed -- creating git snapshot..." -ForegroundColor Cyan
            git -C $projectRoot add -A 2>&1 | Out-Null
            git -C $projectRoot commit -m "check-pass: $version rtl=$currentHash" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Log "Auto-committed: check-pass $version" "INFO" }
        }

        Release-Lock
        Invoke-Hook "post-check" @($ec)
        exit $ec
    }

    "build" {
        if (-not (Acquire-Lock "build")) { exit 1 }
        Invoke-Hook "pre-build"

        # Double-check env first
        $ec = Run-SubScript (Join-Path $scriptsDir "env_check.ps1")
        if ($ec -ne 0) { Release-Lock; exit 1 }

        Write-Log "Running build..."
        $currentHash = Get-RtlHash
        $version = Get-Version
        Write-Host "Building $version (rtl=$currentHash)" -ForegroundColor Cyan

        $ec = Run-SubScript (Join-Path $scriptsDir "build.ps1")

        if ($ec -eq 0) {
            $bitFile = Join-Path (Join-Path $subProjectRoot "build") "transient_puf_v60_top.bit"
            if (-not (Test-Path $bitFile)) {
                Write-Log "Build ok but bitstream missing: $bitFile" "ERROR"
                Release-Lock; exit 1
            }
            # Archive bitstream
            $archiveDir = Join-Path (Join-Path $subProjectRoot "build") "archive"
            New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
            $gitHash = git -C $projectRoot rev-parse --short HEAD 2>$null
            if (-not $gitHash) { $gitHash = "nogit" }
            $prefix = "$timestamp-$version-$gitHash-$currentHash"
            Copy-Item $bitFile (Join-Path $archiveDir "$prefix.bit")

            $reports = Parse-VivadoReports -BuildDir (Join-Path $subProjectRoot "build")
            $manifest = @{ timestamp = $timestamp; version = $version; rtl_hash = $currentHash;
                bitstream = "$prefix.bit"; wns_ns = $reports.wns_ns; tns_ns = $reports.tns_ns;
                utilization = $reports.utilization } | ConvertTo-Json -Depth 5
            $manifest | Set-Content (Join-Path $archiveDir "$prefix.manifest.json") -Encoding UTF8
            Write-Log "Archived: build/archive/$prefix.bit" "INFO"

            # WNS warning
            if ($null -ne $reports.wns_ns -and $reports.wns_ns -lt 0.5) {
                Write-Log "WNS=$($reports.wns_ns)ns < 0.5ns -- timing tight!" "WARN"
            }
        } else {
            # Save fail context
            $vivadoLog = Join-Path (Join-Path $subProjectRoot ".artifacts") "vivado_runs\build.log"
            if (Test-Path $vivadoLog) {
                $tail = Get-Content $vivadoLog -Tail 50
                $errors = $vivadoLog | Get-Content | Where-Object { $_ -match '(?i)(ERROR|CRITICAL WARNING)' }
                $failFile = Join-Path $stateDir "fail_context_$timestamp.log"
                "=== FAIL CONTEXT @ $timestamp ===`nVivado log: $vivadoLog`n" +
                "=== ERROR / CRITICAL WARNING ===`n$($errors -join "`n")`n=== Last 50 lines ===`n$($tail -join "`n")" |
                    Set-Content $failFile -Encoding UTF8
                Write-Log "Fail context saved: $failFile" "WARN"
            }
        }

        Invoke-Hook "post-build" @($ec)
        Release-Lock
        exit $ec
    }

    "program" {
        Write-Log "Running program (SRAM)..."
        $ec = Run-SubScript (Join-Path $scriptsDir "program.ps1")
        exit $ec
    }

    "capture" {
        $port = "COM5"
        foreach ($a in $RemainingArgs) {
            if ($a -match "^-Port=(.+)$") { $port = $matches[1] }
        }
        Write-Log "Running capture on $port..."
        Invoke-Hook "pre-capture"
        $ec = Run-SubScript (Join-Path $scriptsDir "capture_ascii_v60.py") @("--port", $port)
        Invoke-Hook "post-capture" @($ec)
        exit $ec
    }

    "clean" {
        Write-Log "Cleaning generated files..."
        $xilDir = Join-Path $subProjectRoot ".Xil"
        if (Test-Path $xilDir) { Remove-Item -Recurse -Force $xilDir; Write-Log "Removed .Xil/" }
        $artifactsDir = Join-Path $subProjectRoot ".artifacts"
        if (Test-Path $artifactsDir) {
            Get-ChildItem $artifactsDir -Recurse -Filter "*.backup.*" | Remove-Item -Force
            Write-Log "Cleaned .artifacts/ backup logs"
        }
        if ($RemainingArgs -contains "-Hard") {
            $buildDir = Join-Path $subProjectRoot "build"
            if (Test-Path $buildDir) {
                Get-ChildItem $buildDir | Where-Object { $_.Name -ne "archive" } | Remove-Item -Recurse -Force
                Write-Log "Hard clean: removed build/ (kept archive/)"
            }
        }
        Write-Log "Clean done."
        exit 0
    }

    "status" {
        Write-Host "--- FPGA_transDATA V6.6 ---" -ForegroundColor Cyan
        Write-Host ("  Version:  " + (Get-Version))
        Write-Host ("  RTL hash: " + (Get-RtlHash))
        $rtlCnt = (Get-ChildItem (Join-Path $subProjectRoot "rtl") -Filter "*.v").Count
        Write-Host ("  RTL files: $rtlCnt")
        $bitFile = Join-Path (Join-Path $subProjectRoot "build") "transient_puf_v60_top.bit"
        if (Test-Path $bitFile) {
            $info = Get-Item $bitFile
            Write-Host ("  Bitstream: {0} ({1} KB, {2})" -f $info.Name, [math]::Round($info.Length/1KB,1), $info.LastWriteTime)
        }
        $archiveDir = Join-Path (Join-Path $subProjectRoot "build") "archive"
        if (Test-Path $archiveDir) { Write-Host ("  Archive:   {0} bitstream(s)" -f (Get-ChildItem $archiveDir -Filter "*.bit").Count) }
        Write-Host ""
        Write-Host "--- PROGRESS ---" -ForegroundColor Cyan
        $progressFile = Join-Path $subProjectRoot "PROGRESS.md"
        if (Test-Path $progressFile) { Get-Content $progressFile -Encoding UTF8 | Select-Object -First 20 }
        exit 0
    }

    "done" {
        Write-Log "Session-end checklist..."
        $exitCode = 0
        $progressFile = Join-Path $subProjectRoot "PROGRESS.md"
        if (Test-Path $progressFile) {
            $hoursOld = [math]::Round(((Get-Date) - (Get-Item $progressFile).LastWriteTime).TotalHours, 1)
            if ($hoursOld -gt 24) { Write-Host "  [WARN] PROGRESS.md $hoursOld hours old" -ForegroundColor Yellow; $exitCode = 1 }
            else { Write-Host "  [PASS] PROGRESS.md fresh ($hoursOld hrs)" -ForegroundColor Green }
        }
        try {
            $gitStatus = git -C $projectRoot status --short 2>$null
            if ($gitStatus) {
                $lines = @($gitStatus -split "`n" | Where-Object { $_ -ne "" })
                Write-Host "  [WARN] $($lines.Count) uncommitted file(s)" -ForegroundColor Yellow
                $lines | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
                $exitCode = 1
            } else { Write-Host "  [PASS] Git clean" -ForegroundColor Green }
        } catch { Write-Host "  [INFO] Git not available" -ForegroundColor Cyan }
        if (Test-Path $lockFile) { Write-Host "  [WARN] Stale lock present" -ForegroundColor Yellow; $exitCode = 1 }
        else { Write-Host "  [PASS] No stale locks" -ForegroundColor Green }
        Write-Host "  [INFO] Fill .harness/session-handoff.md if multi-session work" -ForegroundColor Cyan
        if ($exitCode -eq 0) { Write-Host "`nChecklist PASSED." -ForegroundColor Green }
        else { Write-Host "`nChecklist FAILED. Fix items above." -ForegroundColor Red }
        exit $exitCode
    }

    default {
        Write-Host @"
FPGA_transDATA V6.6 Harness

Usage: .\.harness\tasks.ps1 <command>

Verification:
  env              Toolchain check (Vivado/Verilator/Python)
  lint             Verilator lint all RTL
  sim              Run all testbenches
  check            env + lint + sim (full pipeline, auto-commit on pass)

Build & Deploy:
  build            Vivado full build (synth + impl + bitstream)
  program          JTAG program SRAM

Runtime:
  capture -Port=COM5  UART ASCII capture
  clean [-Hard]    Clean .Xil/ / .artifacts/ (hard also cleans build/)

Session:
  status           Project status summary
  done             Session-end checklist
  help             This help

See CLAUDE.md and .harness/lessons.md for full dev workflow.
"@
        exit 0
    }
}
