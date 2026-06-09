# PROGRESS

## Last Updated
2026-06-09

## Migration Note
This is a clean repository migrated from `FPGA_DATAtransFreq_0514`.
Only the V6.3 capture project was ported — old V5.x FFT/classification code was left behind.

## Current State

V6.3 Multi-Mode Transient Capture, built and verified on hardware:

- **5 capture modes** (auto-cycling): FULL → PCUT → NCUT → EXTR → FCYC
- 128-point dual-channel raw capture
- UART 1 Mbps ASCII frame output
- LCD: version + mode display only
- Bitstream generated and hardware-tested (multiple capture logs)

### Verified capture runs (v63_*):
- `v63_preactive` / `v63_safe` / `v63_nodiscard` — latest hardware captures
- `v62_verify` / `v62_7pt` — V6.2 verification
- Analysis: contrastive learning, t-SNE, PCA visualizations in `logs/analysis/`

## Next Steps

1. Re-run `build_v60.tcl` in this new workspace to regenerate bitstream
2. Program board and verify UART ASCII frames
3. Continue capture experiments and analysis

## 会话记录

| 日期 | 目标 | 完成内容 | 验证 | 提交 |
|:---|:---|:---|:---|:---|
| | | | | |

## Key Files

| File | Description |
|:---|:---|
| `rtl/transient_puf_v60_top.v` | Top-level, V6.3, 5-mode state machine |
| `rtl/sensor_power_control.v` | 5-mode power sequencing |
| `rtl/capture_uart_streamer.v` | ASCII UART frame output |
| `rtl/transient_capture.v` | 128-point dual-channel capture |
| `scripts/build_v60.tcl` | Vivado build script |
| `scripts/capture_ascii_v60.py` | UART capture parser |
| `.harness/tasks.ps1` | Harness entry point |
