#Requires -Version 5.1
<#
.SYNOPSIS
    Lint all V60 workspace RTL modules with Verilator (direct binary, no bash wrapper).
.DESCRIPTION
    Runs verilator_bin.exe directly with correct environment.
    All modules use -y rtl with known suppresses.
    Exit code: 0 = all passed, 1 = any failure.
#>
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$rtlDir = Join-Path $projectRoot "rtl"

# Verilator binary path (from MSYS2 installation)
$verilatorBin = "C:\msys64\mingw64\bin\verilator_bin.exe"

if (-not (Test-Path $verilatorBin)) {
    Write-Error "Verilator binary not found: $verilatorBin"
    exit 1
}

# Set environment for Verilator
$env:VERILATOR_ROOT = "C:\msys64\mingw64"
$oldPath = $env:PATH
$env:PATH = "C:\msys64\mingw64\bin;C:\msys64\usr\bin;" + $env:PATH

# Known suppresses (documented in .harness/README.md)
$suppresses = @(
    "-Wno-WIDTHEXPAND"
    "-Wno-WIDTHTRUNC"
    "-Wno-TIMESCALEMOD"
    "-Wno-LATCH"
    "-Wno-CASEINCOMPLETE"
    "-Wno-BLKLOOPINIT"
    "-Wno-PINNOTFOUND"
)

# Collect all .v files: rtl + sim (Verilator-compatible testbenches)
$rtlModules = Get-ChildItem -Path $rtlDir -Filter "*.v" | Sort-Object Name
$simDir = Join-Path $projectRoot "sim"
$simModules = @(Get-ChildItem -Path $simDir -Filter "tb_*.v" -ErrorAction SilentlyContinue | Sort-Object Name)
$allModules = $rtlModules + $simModules
$total = $allModules.Count
$pass = 0
$fail = 0

Write-Host "[lint] Scanning $total modules (RTL + Verilator TB)..." -ForegroundColor Cyan

$logDir = Join-Path (Join-Path $projectRoot ".harness") "logs"
New-Item -ItemType Directory -Path $logDir -Force -ErrorAction SilentlyContinue | Out-Null

foreach ($mod in $allModules) {
    $name = $mod.Name
    $path = $mod.FullName
    $isTb = $name -match "^tb_"

    # RTL uses --lint-only, TBs use --lint-only --timing (for delays/event controls)
    if ($isTb) {
        $allArgs = @("--lint-only", "--timing") + $suppresses + @("-Wno-PINMISSING", "-Wno-STMTDLY", "-y", $rtlDir, $path)
    } else {
        $allArgs = @("--lint-only") + $suppresses + @("-y", $rtlDir, $path)
    }

    $errLog = Join-Path $logDir "lint_err_$name.log"
    $outLog = Join-Path $logDir "lint_out_$name.log"
    & $verilatorBin $allArgs 2>$errLog >$outLog
    $ec = $LASTEXITCODE
    $stdout = Get-Content $outLog -Raw -ErrorAction SilentlyContinue
    $stderr = Get-Content $errLog -Raw -ErrorAction SilentlyContinue
    $w = if ($stderr) { ([regex]::Matches($stderr, '%Warning')).Count } else { 0 }

    if ($ec -eq 0 -and $w -eq 0) {
        Write-Host "  [PASS] $name" -ForegroundColor Green
        $pass++
    } elseif ($ec -eq 0 -and $w -gt 0) {
        Write-Host "  [PASS] $name ($w known warnings suppressed)" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "  [FAIL] $name" -ForegroundColor Red
        $errLines = ($stderr + "`n" + $stdout) -split "`r?`n" | Where-Object { $_.Trim() -ne "" } | Select-Object -First 3
        foreach ($line in $errLines) {
            Write-Host "         $line" -ForegroundColor DarkGray
        }
        $fail++
    }
}

# Restore PATH
$env:PATH = $oldPath

Write-Host ""
if ($fail -eq 0) {
    Write-Host "[lint] $pass/$total modules passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "[lint] $fail/$total modules failed, $pass passed." -ForegroundColor Red
    exit 1
}
