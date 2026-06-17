# PROGRESS

## Last Updated
2026-06-16

## Roadmap

| 版本 | 范围 | 状态 |
|:---|:---|:---|
| V6.5 | UART 帧加 SID/MID（cycle-aware）；PC 端数据格式重构（sensor/condition 入列、丢半截、ADC 饱和、session 元数据、ADC binary 存储等 13 项） | 🚧 进行中 |
| **V6.6** | **UART 传输 binary 化**（动 RTL 帧格式，去 ASCII hex，~5x 提速到 ~290 fps） | 📅 已规划 |

## Current State

V6.5 cycle-format patch prepared: UART header carries sample_id/mode_idx so each FULL→PCUT→NCUT→EXTR→FCYC group is explicit.

### Latest: 10-sensor × 4-condition dataset (0612)
- **40 CSV files, 8000 frames** (10 sensors × 4 conditions × 200 frames × 5 modes)
- B2-1 ~ B2-10 collected under NTNP/NTHP/HTNP/HTHP conditions
- NCUT confirmed as golden mode (best SNR for sensor identification)
- Key hardware findings: B2-4 CH2 channel unstable, B2-10 NTNP/HTNP baseline ~21000 (sensor characteristic)
- Analysis pipeline established: CMR→FFT→LDA with condition normalization
- Silhouette ~0.62 (file-level), Ratio ~26x (NCUT mode)

### Collection workflow refined
- Per-capture stability check (frmVar < 10, peak ~11000)
- Per-sensor full validation before switching
- Background subagent validation
- Power cable quality monitoring

## 会话记录

| 日期 | 目标 | 完成内容 | 验证 | 提交 |
|:---|:---|:---|:---|:---|
| 2026-06-11 | 0611旧数据集采集 | 10传感器×4条件×50帧 | 部分数据因电源线问题异常 | -- |
| 2026-06-12 | 0612新数据集采集+分析 | 10传感器×4条件×200帧+质量工具+参考风格分析 | 40文件8000帧, B2-4 CH2硬件问题 | 6127098 / 28700f7 |

## Key Files

| File | Description |
|:---|:---|
| `rtl/transient_puf_v60_top.v` | Top-level, V6.5, 5-mode state machine + sample_id/mode_idx |
| `rtl/sensor_power_control.v` | 5-mode power sequencing |
| `rtl/capture_uart_streamer.v` | ASCII UART frame output |
| `rtl/transient_capture.v` | 128-point dual-channel capture |
| `scripts/build_v60.tcl` | Vivado build script |
| `scripts/capture_ascii_v60.py` | UART capture parser |
| `.harness/tasks.ps1` | Harness entry point |
| `logs/0612_4state_10sensers/` | Current valid dataset (40 CSVs, 8000 frames) |
| `scripts/reproduce_reference.py` | Reference-style LDA analysis |
| `scripts/check_all_stability.py` | Data quality checker |
