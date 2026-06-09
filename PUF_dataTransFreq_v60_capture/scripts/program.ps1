$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$artifactsDir = Join-Path $projectRoot ".artifacts"
$logsDir = Join-Path $artifactsDir "vivado_runs"
$logFile = Join-Path $logsDir "program.log"
$journalFile = Join-Path $logsDir "program.jou"
$runnerFile = Join-Path $logsDir "program_launch.cmd"

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

Push-Location $projectRoot
try {
    $vivadoPath = "D:\Xilinx\Vivado\2023.2\bin\vivado.bat"
    if (-not (Test-Path $vivadoPath)) {
        throw "Vivado not found at $vivadoPath"
    }

    $programTcl = Join-Path $scriptDir "program.tcl"
    $runnerContent = @"
@echo off
call "{0}" -mode batch -log "{1}" -journal "{2}" -source "{3}"
exit /b %errorlevel%
"@ -f $vivadoPath, $logFile, $journalFile, $programTcl

    Set-Content -LiteralPath $runnerFile -Value $runnerContent -Encoding ascii
    & "C:\Windows\System32\cmd.exe" /d /s /c "`"$runnerFile`""
    if ($LASTEXITCODE -ne 0) {
        throw "Vivado SRAM programming failed with exit code $LASTEXITCODE. See $logFile"
    }
}
finally {
    Pop-Location
}
