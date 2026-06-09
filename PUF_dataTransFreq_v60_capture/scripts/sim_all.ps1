#Requires -Version 5.1
<#
.SYNOPSIS
    Run all (or a filtered subset of) testbenches with Vivado Simulator (xsim).
.DESCRIPTION
    Detects xvlog/xelab/xsim from Vivado installation and runs each sim/tb_*.sv.
    Expects tb to output "passed" or "[PASS]" on success, or use $fatal on failure.
    Exit code: 0 = all passed, 1 = any failure.
.PARAMETER Tests
    Optional comma-separated list of testbench base names (e.g. "tb_sensor_power_control,tb_transient_capture")
    to filter by. Empty (default) runs every tb_*.sv in sim/.
#>
param(
    [string]$Tests = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Optional load_env -- skip if missing (fallback handles it)
$loadEnv = Join-Path $scriptDir "load_env.ps1"
if (Test-Path $loadEnv) { . $loadEnv }

$projectRoot = Split-Path -Parent $scriptDir
$simDir = Join-Path $projectRoot "sim"
$rtlDir = Join-Path $projectRoot "rtl"

# Parse `// SIM_DEPS: a.v b.v` from tb header (first 20 lines).
# Returns full paths of declared RTL dependencies, or $null if none declared.
function Get-TbDeps {
    param([string]$TbPath, [string]$RtlDir)
    $header = Get-Content -Path $TbPath -TotalCount 20 -Encoding UTF8 -ErrorAction SilentlyContinue
    foreach ($line in $header) {
        if ($line -match '^\s*//\s*SIM_DEPS\s*:\s*(.+?)\s*$') {
            $depsList = $matches[1] -split '[,\s]+' | Where-Object { $_ -match '\.v$' }
            $depsFull = @()
            foreach ($dep in $depsList) {
                $path = Join-Path $RtlDir $dep
                if (Test-Path $path) {
                    $depsFull += $path
                } else {
                    Write-Host "  [WARN] SIM_DEPS file not found in rtl/: $dep" -ForegroundColor Yellow
                }
            }
            return $depsFull
        }
    }
    return $null
}

# Find Vivado bin directory
$vivadoBin = $null
if ($env:VIVADO_BIN) {
    $vivadoBin = Split-Path -Parent $env:VIVADO_BIN
} else {
    $vivadoPath = (Get-Command "vivado" -ErrorAction SilentlyContinue).Source
    if ($vivadoPath) {
        $vivadoBin = Split-Path -Parent $vivadoPath
    } else {
        # Try common install paths
        $candidates = @(
            "C:\Xilinx\Vivado\2023.2\bin",
            "D:\Xilinx\Vivado\2023.2\bin",
            "C:\Xilinx\Vivado\2023.1\bin",
            "D:\Xilinx\Vivado\2023.1\bin"
        )
        foreach ($c in $candidates) {
            if ((Test-Path (Join-Path $c "xvlog.bat")) -or (Test-Path (Join-Path $c "xvlog.exe"))) {
                $vivadoBin = $c
                break
            }
        }
    }
}

if (-not $vivadoBin) {
    Write-Error "[sim] Vivado Simulator (xvlog) not found. Is Vivado 2023.2 installed?"
    exit 1
}

# Vivado on Windows uses .bat wrappers instead of .exe
$xvlog = Join-Path $vivadoBin "xvlog.bat"
$xelab = Join-Path $vivadoBin "xelab.bat"
$xsim = Join-Path $vivadoBin "xsim.bat"

# Fallback to .exe if .bat not found
foreach ($pair in @(@("xvlog", $xvlog), @("xelab", $xelab), @("xsim", $xsim))) {
    $name = $pair[0]
    $path = $pair[1]
    if (-not (Test-Path $path)) {
        $alt = Join-Path $vivadoBin "$name.exe"
        if (Test-Path $alt) {
            Set-Variable -Name $name -Value $alt
        } else {
            Write-Error "[sim] Tool not found: $path or $alt"
            exit 1
        }
    }
}

# Helper: check if tb has // SIM_SKIP comment in first 20 lines
function Test-SimSkip {
    param([string]$TbPath)
    $header = Get-Content -Path $TbPath -TotalCount 20 -Encoding UTF8 -ErrorAction SilentlyContinue
    foreach ($line in $header) {
        if ($line -match '^\s*//\s*SIM_SKIP\s*:') {
            return $true
        }
    }
    return $false
}

$tbFiles = Get-ChildItem -Path $simDir -Filter "tb_*.sv" | Sort-Object Name
$skipped = @()
$tbFiles = $tbFiles | Where-Object {
    if (Test-SimSkip $_.FullName) {
        $skipped += $_.BaseName
        $false
    } else {
        $true
    }
}
if ($skipped.Count -gt 0) {
    Write-Host "[sim] Skipping $($skipped.Count) testbench(es) marked SIM_SKIP: $($skipped -join ', ')" -ForegroundColor DarkGray
}

$testList = @()
if ($Tests) {
    $testList = $Tests -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
if ($testList.Count -gt 0) {
    $tbFiles = $tbFiles | Where-Object { $testList -contains $_.BaseName }
    $found = @($tbFiles | ForEach-Object { $_.BaseName })
    $missing = $testList | Where-Object { $_ -notin $found }
    if ($missing) {
        Write-Host "[sim] Requested tests not found: $($missing -join ', ')" -ForegroundColor Red
        exit 1
    }
}
if (-not $tbFiles) {
    Write-Host "[sim] No testbenches found in $simDir" -ForegroundColor Yellow
    exit 0
}

$total = $tbFiles.Count
$pass = 0
$fail = 0

Write-Host "[sim] Running $total testbench(es) with Vivado Simulator..." -ForegroundColor Cyan

function Invoke-Tool {
    param(
        [string]$ToolPath,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath
    )

    $toolExt = [System.IO.Path]::GetExtension($ToolPath).ToLowerInvariant()
    if ($toolExt -eq ".bat" -or $toolExt -eq ".cmd") {
        $joinedArgs = ($Arguments | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"', '""') + '"'
            } else {
                $_
            }
        }) -join ' '
        $runnerPath = Join-Path (Get-Location) "__run_tool.cmd"
        @(
            "@echo off"
            "call `"$ToolPath`" $joinedArgs"
            "exit /b %errorlevel%"
        ) | Set-Content -LiteralPath $runnerPath -Encoding ASCII
        & "C:\Windows\System32\cmd.exe" /c $runnerPath 1>$StdoutPath 2>$StderrPath
        Remove-Item -LiteralPath $runnerPath -Force -ErrorAction SilentlyContinue
    } else {
        & $ToolPath $Arguments 1>$StdoutPath 2>$StderrPath
    }
    return $LASTEXITCODE
}

foreach ($tb in $tbFiles) {
    $tbName = $tb.BaseName  # e.g., tb_sensor_power_control
    $tbPath = $tb.FullName
    $workDir = Join-Path (Join-Path (Join-Path $projectRoot ".artifacts") "sim_runs") $tbName
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null

    Push-Location $workDir
    try {
        # Clean previous run
        Remove-Item -Recurse -Force "xsim.dir" -ErrorAction SilentlyContinue
        Remove-Item -Force "*.log" -ErrorAction SilentlyContinue
        Remove-Item -Force "*.jou" -ErrorAction SilentlyContinue
        Remove-Item -Force "*.wdb" -ErrorAction SilentlyContinue

        # Step 1: xvlog (compile)
        # If tb declares `// SIM_DEPS: foo.v bar.v`, only compile those.
        # Otherwise fall back to all rtl/*.v (legacy behavior).
        $tbDeps = Get-TbDeps -TbPath $tbPath -RtlDir $rtlDir
        if ($tbDeps) {
            $xvlogArgs = @("-sv", "-incr") + $tbDeps + @($tbPath)
            $depsLabel = ($tbDeps | ForEach-Object { Split-Path -Leaf $_ }) -join ', '
            Write-Host "  [deps] $tbName -> $depsLabel" -ForegroundColor DarkGray
        } else {
            $xvlogArgs = @("-sv", "-incr") +
                         (Get-ChildItem -Path $rtlDir -Filter "*.v" | ForEach-Object { $_.FullName }) +
                         @($tbPath)
        }

        $ec = Invoke-Tool -ToolPath $xvlog -Arguments $xvlogArgs -StdoutPath "xvlog_stdout.log" -StderrPath "xvlog_stderr.log"
        if ($ec -ne 0) {
            Write-Host "  [FAIL] $tbName : xvlog compilation failed" -ForegroundColor Red
            $err = Get-Content "xvlog_stderr.log" -ErrorAction SilentlyContinue | Select-Object -First 3
            $err | ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }
            $fail++
            continue
        }

        # Step 2: xelab (elaborate)
        $topModule = $tbName  # tb file name = top module name
        $elabArgs = @("-debug", "typical", "-top", $topModule, "-snapshot", "$($topModule)_snap")
        $ec = Invoke-Tool -ToolPath $xelab -Arguments $elabArgs -StdoutPath "xelab_stdout.log" -StderrPath "xelab_stderr.log"
        if ($ec -ne 0) {
            Write-Host "  [FAIL] $tbName : xelab elaboration failed" -ForegroundColor Red
            $err = Get-Content "xelab_stderr.log" -ErrorAction SilentlyContinue | Select-Object -First 3
            $err | ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }
            $fail++
            continue
        }

        # Step 3: xsim (simulate)
        $ec = Invoke-Tool -ToolPath $xsim -Arguments @("$($topModule)_snap", "-runall") -StdoutPath "xsim_stdout.log" -StderrPath "xsim_stderr.log"

        $logContent = ""
        if (Test-Path "xsim.log") {
            $logContent = Get-Content "xsim.log" -ErrorAction SilentlyContinue -Raw
        } elseif (Test-Path "xsim_stdout.log") {
            $logContent = Get-Content "xsim_stdout.log" -ErrorAction SilentlyContinue -Raw
        }
        $hasPass = $logContent -match "passed|PASS|\[PASS\]"
        $hasFatal = $logContent -match 'FATAL|ERROR|\$fatal'

        if ($ec -eq 0 -and $hasPass -and -not $hasFatal) {
            Write-Host "  [PASS] $tbName" -ForegroundColor Green
            $pass++
        } else {
            Write-Host "  [FAIL] $tbName (exit=$ec)" -ForegroundColor Red
            $lines = $logContent -split "`r?`n" | Where-Object { $_ -match "FATAL|ERROR|Assertion" } | Select-Object -First 3
            $lines | ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }
            $fail++
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
if ($fail -eq 0) {
    Write-Host "[sim] $pass/$total testbench(es) passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "[sim] $fail/$total testbench(es) failed, $pass passed." -ForegroundColor Red
    exit 1
}
