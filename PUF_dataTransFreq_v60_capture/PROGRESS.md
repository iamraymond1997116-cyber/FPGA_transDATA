# PROGRESS

## Last Updated
2026-06-18

## Roadmap

| 版本 | 范围 | 状态 |
|:---|:---|:---|
| V6.5 | UART 帧加 SID/MID（cycle-aware）+ PC 端 13 项数据格式重构 | ✅ 完成（上板验证通过）|
| **V6.6** | **ASCII 协议加固**：R1 行级 CRC8（RTL+PC）+ R3 帧序号校验（PC）| 📅 下一步 |
| V6.7+ | UART 传输 binary 化（动 RTL 帧格式，~5x 提速）| 🔮 待评估 |

> V6.6 决策依据：当前 8 秒/100 sample 已可接受，binary 化提速 4.7x 但**整体流程**只快 ~16%（人工换传感器是瓶颈）。优先做可靠性（CRC + 序号校验），binary 推迟到真有吞吐瓶颈再做。

## Current State

V6.5 cycle-aware capture + PC pipeline 完整就绪：
- RTL：UART 头加 `SID=NNNNN,MID=N`，sample_id 在 FCYC 完成后递增（pending flag 防 race）
- PC：CSV 元数据 + `.npy` 二进制 payload + `session.json` 元数据 + 边界 trim + ADC 饱和标记 + UUID 命名 + 批量 `--glob` 后处理 + `manifest.json`
- 文档：`doc/DATA_FORMAT.md` 权威字段参考（任何分析任务的入口）

### V6.5 验证记录

| 检查 | 结果 |
|:---|:---|
| `tasks.ps1 check`（env+lint+sim） | ✅ 0 Error |
| `tasks.ps1 build`（V6.5 bitstream） | ✅ WNS=3.155ns |
| `tasks.ps1 program`（JTAG SRAM） | ✅ |
| 采集 10/20/15 sample 多轮 | ✅ parse_errors=0 |
| 批量 post_process 14 sample | ✅ valid=14/14 |

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
