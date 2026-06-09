# FFT重放计划

> **更新**: 2026-06-02 — V5.8 固件已验证，xsim 重放链路已跑通，Python FFT 复现已验证。

## 目标

给定任意 raw 数据（256 个 ADC 采样值）+ SCALE_SCH 索引 → 输出 FPGA 会产生的 128 bin 频谱，实现离线 SCALE_SCH 参数扫描。

## 已实现

### 1. 固件：V5.8 ASCII RAW 输出 ✅

- `mode_fast_scan = 0`，禁用二进制快扫模式
- 每 SCH 步输出完整 ASCII 数据：STATUS → RAW_CH1(256值) → RAW_CH2(256值) → PEAKS → SPECTRUM_CH1(128bin) → SPECTRUM_CH2(128bin) → OFF_STABLE → OFF_RAW_CH1 → OFF_RAW_CH2 → OFF_SPECTRUM_CH1 → OFF_SPECTRUM_CH2
- 2602-06-02 采集数据：`PUF_dataTransFreq/logs/0602RAW/B2-1_V58_ascii_SCH0_255.csv` — 256 SCH 全覆盖，RAW + SPECTRUM 完整

### 2. xsim 重放链路 ✅

绕过 Vivado 项目模式 `launch_simulation`（该命令在 Windows 上有 Broken pipe 问题），直接用命令行跑通：

```powershell
# 编译
xvlog -sv fft_256.v xfft_0_sim_netlist.v tb_fft_256_raw_replay.sv
xelab -debug typical -top tb_fft_256_raw_replay -snapshot replay_snap -L secureip -L unisims_ver -L unimacro_ver work.glbl

# 仿真 (输入 raw → 输出 256 SCH 频谱)
xsim replay_snap -R
# 耗时: ~8 分钟/256 SCH (~2 秒/SCH)
```

输出格式: `sch_index,sch_hex,bin_0,bin_1,...,bin_127`

### 3. Python FFT 复现 ✅

```python
from scipy.fft import fft
raw_ac = raw - raw.mean()           # 去直流
spectrum = fft(raw_ac, n=256)
mags = np.sqrt(spectrum.real**2 + spectrum.imag**2)[:128]
```

- 与 FPGA 实测频谱对比：cosine 均值 0.76（形状匹配）
- 最优 SCH（256-bin 对齐后）：cosine 0.88~0.92

### 4. 后综合仿真 ✅

用 `synth_design -mode out_of_context` 生成门级网表，xsim 可编译运行，速度与行为级仿真相近。

## 已知限制

- **xfft_0 是加密 IP**：行为级仿真模型 `xfft_0_sim_netlist.v` 与 FPGA 硅上实现在低 SCALE_SCH 缩放值下有溢出行为差异
- 高缩放 SCH (0x074, 0x0FF 等)：xsim 与 FPGA 高度一致 (cosine > 0.95)
- 低缩放 SCH (0x013, 0x032 等)：xsim 仿真模型溢出行为与硬件不同，偏差较大
- 后综合 funcsim 网表与行为级仿真模型结果一致（加密 IP 未暴露内部实现）

## 文件索引

| 文件 | 作用 |
|:---|:---|
| `PUF_dataTransFreq/sim/tb_fft_256_raw_replay.sv` | FFT 重放 testbench（标记 SIM_SKIP，需手动运行） |
| `PUF_dataTransFreq/scripts/run_fft_raw_replay.tcl` | Vivado 项目模式重放脚本（Broken pipe 待修复） |
| `PUF_dataTransFreq/scripts/synth_fft_for_replay.tcl` | OOC 综合导出 funcsim 网表 |
| `PUF_dataTransFreq/build/raw_replay/direct_sim/` | 命令行 xsim 工作目录（已验证可跑通） |
| `PUF_dataTransFreq/build/fft_postsynth/` | 后综合网表 `fft_256_postsynth.v` |

## 使用流程

### 快速复现（Python FFT，cosine ~0.76）

```python
from scipy.fft import fft
import numpy as np
raw = np.loadtxt("input_raw.mem")      # 256 signed int16
spec = np.sqrt(np.abs(fft(raw - raw.mean(), n=256))**2)[:128]
```

### 精确复现（xsim 重放，cosine ~0.95 for high-SCH）

```powershell
cd PUF_dataTransFreq/build/raw_replay/direct_sim
cp <your_raw.mem> build/raw_replay/input_raw.mem
xsim replay_snap -R
# 输出: build/raw_replay/fft_replay_output.csv
```

### 首次搭建

```powershell
# 1. 编译 funcsim 网表 (需先跑综合)
vivado -mode batch -source PUF_dataTransFreq/scripts/synth_fft_for_replay.tcl

# 2. 编译仿真快照
cd PUF_dataTransFreq/build/raw_replay/direct_sim
xvlog -sv ../../fft_postsynth/fft_256_postsynth.v ../../../sim/tb_fft_256_raw_replay.sv
xelab -debug typical -top tb_fft_256_raw_replay -snapshot replay_snap -L secureip -L unisims_ver -L unimacro_ver work.glbl
```

## 下一步

- [ ] 修复 xsim `launch_simulation` Broken pipe 问题（可能需要 Vivado 升级或环境调整）
- [ ] 尝试 post-implementation 时序仿真（需完整 place & route）
- [ ] 为 Python FFT 模型加入定点溢出建模以提高低 SCH 精度
- [ ] 扩展到多传感器校准
