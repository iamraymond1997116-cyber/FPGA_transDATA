#Requires -Version 5.1
<#
.SYNOPSIS
    Compile and run tb_trigger_chain.v with full UART chain via Verilator.
.DESCRIPTION
    Compiles: tb_trigger_chain.v + all RTL (sensor_power_control, transient_capture,
    capture_uart_streamer, uart_tx) + sim_main.cpp.
    Runs the resulting executable and reports PASS/FAIL.
#>
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$rtlDir = Join-Path $projectRoot "rtl"
$simDir = Join-Path $projectRoot "sim"

$verilatorBin = "C:\msys64\mingw64\bin\verilator_bin.exe"

if (-not (Test-Path $verilatorBin)) {
    Write-Error "Verilator binary not found: $verilatorBin"
    exit 1
}

# Set Verilator environment
$env:VERILATOR_ROOT = "C:\msys64\mingw64"
$oldPath = $env:PATH
$env:PATH = "C:\msys64\mingw64\bin;C:\msys64\usr\bin;$env:PATH"

# Enter sim directory
Push-Location $simDir
try {
    # Clean previous build
    Write-Host "[clean] Removing obj_dir..." -ForegroundColor Cyan
    if (Test-Path obj_dir) {
        Remove-Item -Recurse -Force obj_dir -ErrorAction Stop
    }

    # Verilator compile
    Write-Host "[verilator] Compiling tb_trigger_chain with full UART chain..." -ForegroundColor Cyan
    $verilatorArgs = @(
        "--cc",
        "--exe",
        "--build",
        "-j",
        "-y", $rtlDir,
        "-Wall",
        "-Wno-WIDTHEXPAND",
        "-Wno-WIDTHTRUNC",
        "-Wno-TIMESCALEMOD",
        "-Wno-LATCH",
        "-Wno-CASEINCOMPLETE",
        "-Wno-BLKLOOPINIT",
        "-Wno-PINNOTFOUND",
        "-Wno-PINMISSING",
        "-Wno-UNOPTFLAT",
        "-Wno-UNUSEDSIGNAL",
        "--top-module", "tb_trigger_chain",
        "tb_trigger_chain.v",
        "sim_main.cpp"
    )

    $verilatorOutput = & $verilatorBin @verilatorArgs 2>&1
    $verilatorExitCode = $LASTEXITCODE

    if ($verilatorExitCode -ne 0) {
        Write-Host ""
        Write-Host "[FAIL] Verilator compilation failed (exit code $verilatorExitCode)" -ForegroundColor Red
        Write-Host $verilatorOutput
        exit 1
    }

    Write-Host "[verilator] Compilation OK" -ForegroundColor Green

    # Run simulation
    Write-Host "[sim] Running Vtb_trigger_chain.exe..." -ForegroundColor Cyan
    $exePath = Join-Path obj_dir "Vtb_trigger_chain.exe"

    if (-not (Test-Path $exePath)) {
        Write-Error "Executable not found: $exePath"
        exit 1
    }

    $simOutput = & $exePath 2>&1
    $simExitCode = $LASTEXITCODE

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "SIMULATION OUTPUT" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host $simOutput
    Write-Host "========================================" -ForegroundColor Cyan

    # Check for PASS/FAIL in output
    if ($simOutput -match "ALL CHECKS PASSED" -or $simOutput -match "^PASS$") {
        Write-Host ""
        Write-Host "[PASS] All checks passed!" -ForegroundColor Green
        exit 0
    } elseif ($simOutput -match "^FAIL") {
        Write-Host ""
        Write-Host "[FAIL] Simulation reported FAILURE" -ForegroundColor Red
        exit 1
    } else {
        Write-Host ""
        Write-Host "[UNKNOWN] Could not determine PASS/FAIL from output (exit code: $simExitCode)" -ForegroundColor Yellow
        exit $simExitCode
    }
} finally {
    Pop-Location
    $env:PATH = $oldPath
}
