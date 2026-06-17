# FPGA_transDATA V6.5

Multi-Mode Transient Capture for sensor PUF fingerprinting (Artix-7 XC7A200T).

## Overview

Pure capture-only FPGA project — 5 power-cycling modes for capturing sensor transient responses:

| Mode | Pattern | Description |
|:---|:---|:---|
| FULL | ON@0, OFF@64 | Full window |
| PCUT | ON@0, OFF@8 | Positive-cut (early off) |
| NCUT | OFF@0, ON@9 | Negative-cut (late on) |
| EXTR | ON(8)/OFF(9) alternating | Extrema cycling |
| FCYC | ON→OFF@32, ON@64, OFF@96 | Full-cycle switching |

- Dual-channel, 128 samples per capture
- UART 1 Mbps ASCII frames for PC-side parsing
- LCD shows version and current mode only
- Auto-cycling through all 5 modes

## Directory Structure

```
rtl/              — Verilog RTL sources
sim/              — Testbenches (Vivado xsim)
scripts/          — Build, program, capture scripts
constraints/      — XDC pin/timing constraints
doc/              — Project documentation
logs/analysis/    — Capture analysis results (research)
.harness/         — Development workflow harness
```

## Toolchain

- Vivado 2023.2
- Verilator (lint only)
- Python 3 + pyserial (capture parsing)

## Commands

```powershell
.\.harness\tasks.ps1 check      # env → lint → sim → style
.\.harness\tasks.ps1 build      # Full Vivado build
.\.harness\tasks.ps1 program    # JTAG SRAM program
.\.harness\tasks.ps1 capture    # UART capture
```

## Research

- `研究报告/` — Research reports (contrastive learning, entropy, SCH optimization, etc.)
- `专利/` — Patent disclosure documents
- `research_reports/` — Enrollment/verification results
- `logs/analysis/` — Capture analysis scripts and visualizations

## Migration History

Migrated from `FPGA_DATAtransFreq_0514` on 2026-06-09.
Old V5.x FFT/spectrum/classification code was archived and not ported.
