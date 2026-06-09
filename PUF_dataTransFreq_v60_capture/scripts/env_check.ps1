#Requires -Version 5.1
<#
.SYNOPSIS
    Hard-assert environment before any build/sim/lint.
.DESCRIPTION
    Checks tool versions, paths, deps. Any failure = exit 1.
    Use --skip-env to bypass (emergency only).
    All checks print [PASS] or [FAIL] with detail.
#>
param([switch]$SkipEnv)

$ErrorActionPreference = "Stop"

if ($SkipEnv) {
    Write-Host "[env] SKIPPED (emergency bypass)" -ForegroundColor Yellow
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootProject = Split-Path -Parent $scriptDir
# Single project at root -- rtl/ is directly under $rootProject
$allWorkspaces = @(if (Test-Path (Join-Path $rootProject "rtl")) { Get-Item $rootProject } else { @() })

# State directory (for persisting env results)
$stateDir = Join-Path $rootProject ".harness\state"
New-Item -ItemType Directory -Path $stateDir -Force -ErrorAction SilentlyContinue | Out-Null

$checks = @()
$allPass = $true

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $script:checks += [PSCustomObject]@{ Name = $Name; Passed = $Passed; Detail = $Detail }
    if (-not $Passed) { $script:allPass = $false }
}

# 1. ASCII path
$pathOk = ($rootProject -match '^[\w\d\\:/\-_\.]+$')
Add-Check "ASCII path" $pathOk "Project path: $rootProject"

# 2. Vivado version
$vivadoVer = $null
$vivadoBin = $null

# Try PATH first, then common install locations
try {
    $verOutput = (vivado -version 2>&1) | Out-String
    if ($verOutput -match 'v(\d{4}\.\d+)') {
        $vivadoVer = $matches[1]
        $vivadoBin = (Get-Command vivado).Source
    }
} catch { }

if (-not $vivadoVer) {
    $candidates = @(
        "C:\Xilinx\Vivado\2023.2\bin\vivado.bat",
        "D:\Xilinx\Vivado\2023.2\bin\vivado.bat"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $verOutput = (& "C:\Windows\System32\cmd.exe" /c "call `"$c`" -version" 2>&1) | Out-String
            if ($verOutput -match 'v(\d{4}\.\d+)') {
                $vivadoVer = $matches[1]
                $vivadoBin = $c
                break
            }
        }
    }
}

if (-not $vivadoVer) {
    foreach ($c in @(
        "C:\Xilinx\Vivado\2023.2\bin\vivado.bat",
        "D:\Xilinx\Vivado\2023.2\bin\vivado.bat"
    )) {
        $xsimBat = Join-Path (Split-Path -Parent $c) "xsim.bat"
        if ((Test-Path $c) -and (Test-Path $xsimBat)) {
            # Fall back to filesystem evidence when batch wrappers exist but do
            # not emit version text cleanly under nested PowerShell/cmd launch.
            $vivadoVer = "2023.2"
            $vivadoBin = $c
            break
        }
    }
}

$vivadoOk = ($vivadoVer -eq "2023.2")
$vivadoDetail = if ($vivadoVer) { "Found $vivadoVer at $vivadoBin" } else { "Not found" }
Add-Check "Vivado 2023.2" $vivadoOk $vivadoDetail

# 3. Verilator binary (MSYS2)
$verilatorBin = "C:\msys64\mingw64\bin\verilator_bin.exe"
$verilatorRoot = "C:\msys64\mingw64"
$verilatorOk = $false
$verilatorVer = "unknown"
$verilatorDetail = "Not found"

if (Test-Path $verilatorBin) {
    try {
        $oldPath = $env:PATH
        $env:VERILATOR_ROOT = $verilatorRoot
        $env:PATH = "C:\msys64\mingw64\bin;C:\msys64\usr\bin;" + $env:PATH
        $verOut = & $verilatorBin --version 2>&1
        $env:PATH = $oldPath
        if ($verOut -match 'Verilator (\d+\.\d+)') {
            $verilatorVer = $matches[1]
            $verilatorOk = $true
            $verilatorDetail = "Verilator $verilatorVer at $verilatorBin"
        } else {
            $verilatorDetail = "Binary found but version check failed"
        }
    } catch {
        $env:PATH = $oldPath
        $verilatorDetail = "Binary found but execution failed: $_"
    }
} else {
    # Fallback: check for wrapper script
    $wrapper = Join-Path $scriptDir "verilator_wrapper.sh"
    if (Test-Path $wrapper) {
        $verilatorDetail = "Wrapper exists but verilator_bin.exe not found at $verilatorBin"
    }
}
Add-Check "Verilator" $verilatorOk $verilatorDetail

# 4. GCC (MSYS2)
$gccBin = "C:\msys64\mingw64\bin\gcc.exe"
$gccOk = $false
$gccVer = "unknown"
$gccDetail = "Not found"

if (Test-Path $gccBin) {
    try {
        $oldPath2 = $env:PATH
        $env:PATH = "C:\msys64\mingw64\bin;C:\msys64\usr\bin;" + $env:PATH
        $gccOut = & $gccBin --version 2>&1 | Select-Object -First 1
        $env:PATH = $oldPath2
        if ($gccOut -match '(\d+\.\d+\.\d+)') {
            $gccVer = $matches[1]
            $gccOk = $true
            $gccDetail = "GCC $gccVer at $gccBin"
        } else {
            $gccDetail = "Binary found but version check failed: $gccOut"
        }
    } catch {
        $env:PATH = $oldPath2
        $gccDetail = "Binary found but execution failed: $_"
    }
}
Add-Check "GCC (MSYS2)" $gccOk $gccDetail

# 5. Python (py or python)
$pyCmd = $null
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pyCmd = "py"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pyCmd = "python"
}
$pythonOk = ($null -ne $pyCmd)
$pyDetail = if ($pyCmd) { "Using '$pyCmd'" } else { "Neither 'py' nor 'python' found" }
Add-Check "Python launcher" $pythonOk $pyDetail

# 6. Python version
$pythonVerOk = $false
$pythonVer = "unknown"
if ($pyCmd) {
    try {
        $v = & $pyCmd --version 2>&1
        if ($v -match '(\d+)\.(\d+)') {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            $pythonVer = "$major.$minor"
            $pythonVerOk = ($major -gt 3) -or ($major -eq 3 -and $minor -ge 10)
        }
    } catch { }
}
Add-Check "Python >= 3.10" $pythonVerOk "Found $pythonVer"

# 7. pip deps
$depsOk = $false
if ($pyCmd) {
    try {
        & $pyCmd -c "import serial, numpy, matplotlib" 2>&1 | Out-Null
        $depsOk = ($LASTEXITCODE -eq 0)
    } catch { }
}
Add-Check "Python deps" $depsOk "serial, numpy, matplotlib"

# 8. COM ports
$ports = [System.IO.Ports.SerialPort]::GetPortNames()
$comOk = ($ports.Count -gt 0)
Add-Check "COM ports" $comOk ($ports -join ', ')

# 9. xsim availability
$xsimOk = $false
if ($vivadoBin) {
    $vivadoBinDir = Split-Path -Parent $vivadoBin
    $xsimOk = (Test-Path (Join-Path $vivadoBinDir "xsim.exe")) -or (Test-Path (Join-Path $vivadoBinDir "xsim.bat"))
}
$xsimDetail = if ($xsimOk) { "Available" } else { "Not found" }
Add-Check "Vivado Simulator" $xsimOk $xsimDetail

# 10. RTL directories (all workspaces)
$allRtlOk = ($allWorkspaces.Count -gt 0)
$rtlDetails = @()
foreach ($ws in $allWorkspaces) {
    $r = Join-Path $ws.FullName "rtl"
    $cnt = (Get-ChildItem $r -Filter "*.v").Count
    $rtlDetails += "$($ws.Name) ($cnt .v files)"
}
if (-not $allRtlOk) {
    $rtlDetails = @("No FPGA workspace found with rtl/*.v files")
}
Add-Check "RTL directories" $allRtlOk ($rtlDetails -join ' | ')

# Print results
Write-Host "[env] Environment check" -ForegroundColor Cyan
foreach ($c in $checks) {
    $color = if ($c.Passed) { "Green" } else { "Red" }
    $status = if ($c.Passed) { "PASS" } else { "FAIL" }
    Write-Host "  [$status] $($c.Name) : $($c.Detail)" -ForegroundColor $color
}

Write-Host ""
if ($allPass) {
    Write-Host "[env] All checks passed." -ForegroundColor Green
    # Persist env state for other sessions/scripts
    $envState = @{
        timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        vivado_bin = $vivadoBin
        vivado_version = $vivadoVer
        python_cmd = $pyCmd
        python_version = $pythonVer
        verilator_bin = $verilatorBin
        verilator_version = $verilatorVer
        gcc_bin = $gccBin
        gcc_version = $gccVer
        project_root = $rootProject
        workspaces = @($allWorkspaces | ForEach-Object { $_.Name })
    } | ConvertTo-Json
    $envState | Set-Content (Join-Path $stateDir "env.json") -Encoding UTF8
    exit 0
} else {
    Write-Host "[env] $($checks | Where-Object { -not $_.Passed } | Measure-Object | Select-Object -ExpandProperty Count) check(s) failed." -ForegroundColor Red
    Write-Host "[env] Fix issues or use --skip-env to bypass (not recommended)." -ForegroundColor DarkYellow
    exit 1
}
