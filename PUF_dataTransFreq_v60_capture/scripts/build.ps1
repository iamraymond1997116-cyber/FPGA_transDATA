$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$artifactsDir = Join-Path $projectRoot ".artifacts"
$logsDir = Join-Path $artifactsDir "vivado_runs"
$logFile = Join-Path $logsDir "build.log"
$journalFile = Join-Path $logsDir "build.jou"

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$vivadoPath = "D:\Xilinx\Vivado\2023.2\bin\vivado.bat"
if (-not (Test-Path $vivadoPath)) {
    throw "Vivado not found at $vivadoPath"
}

$env:XILINX_VIVADO = "D:\Xilinx\Vivado\2023.2"
$env:RDI_DATADIR = "D:\Xilinx\Vivado\2023.2\data"
$env:RDI_LIBDIR = "D:\Xilinx\Vivado\2023.2\lib\win64.o"
$env:RDI_BINDIR = "D:\Xilinx\Vivado\2023.2\bin\unwrapped\win64.o"
$env:RDI_PLATFORM = "win64"

$buildTcl = Join-Path $scriptDir "build_v60.tcl"
Push-Location $projectRoot
try {
    & $vivadoPath -mode batch -log $logFile -journal $journalFile -source $buildTcl
    if ($LASTEXITCODE -ne 0) {
        throw "Vivado build failed with exit code $LASTEXITCODE. See $logFile"
    }
}
finally {
    Pop-Location
}
