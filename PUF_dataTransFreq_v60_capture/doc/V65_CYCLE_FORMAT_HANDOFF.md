# V6.5 Cycle-Format Patch Handoff

## 目的

本 patch 将 V6.4 的自由循环帧格式升级为 **V6.5 cycle-aware 格式**。

核心目标：让一次完整的 5-mode 采样天然成为一个数据点。

```text
一个 sample = FULL + PCUT + NCUT + EXTR + FCYC
每个 mode = CH1[128] + CH2[128]
最终分析形状 = [N, 5, 2, 128]
```

V6.4 里 PC 端只能靠“每 5 行一组”推断 sample 边界。一旦 UART 丢帧或起点错位，后处理会整体错位。V6.5 在 UART header 中加入 `SID` 和 `MID`，使 sample 边界显式化。

---

## 新 UART 帧格式

### 旧格式 V6.4

```text
V6.4,MODE=FULL,SPWR=0,TXN=01
CH1,RAW,128,<128×4-hex>
CH2,RAW,128,<128×4-hex>
```

### 新格式 V6.5

```text
V6.5,SID=00000,MID=0,FULL,SPWR=0,TXN=01
CH1,RAW,128,<128×4-hex>
CH2,RAW,128,<128×4-hex>
```

字段说明：

| 字段 | 含义 |
|---|---|
| `V6.5` | 协议版本 |
| `SID=00000` | `sample_id`，5 位十进制，0-99999 |
| `MID=0` | `mode_idx`，sample 内模式序号 0-4 |
| `FULL` | mode 名称 |
| `SPWR=0` | sensor power 状态，保持旧语义 |
| `TXN=01` | transaction id，保持旧语义 |

`MID` 映射：

| MID | Mode |
|---:|---|
| 0 | FULL |
| 1 | PCUT |
| 2 | NCUT |
| 3 | EXTR |
| 4 | FCYC |

同一个 `SID` 下必须有完整 5 帧：

```text
SID=k,MID=0,FULL
SID=k,MID=1,PCUT
SID=k,MID=2,NCUT
SID=k,MID=3,EXTR
SID=k,MID=4,FCYC
```

完成 `FCYC` 后，下一轮 `FULL` 使用 `SID=k+1`。

---

## RTL 改动

### `rtl/transient_puf_v60_top.v`

改动：

1. 版本号从 V6.4 改为 V6.5：

```verilog
localparam [7:0] VERSION_MINOR = 8'd5;
```

2. 新增 `sample_id`：

```verilog
reg [15:0] sample_id = 16'd0;
```

3. 新增 `mode_idx`：

```verilog
wire [2:0] mode_idx = capture_mode;
```

4. 将 `sample_id` / `mode_idx` 传入 `capture_uart_streamer`。

5. `sample_id` 只在完成 `MODE_FULL_CYCLE` / `FCYC` 后 +1：

```verilog
if (capture_mode == MODE_FULL_CYCLE)
    sample_id <= sample_id + 16'd1;
```

设计意图：

- `mode_select` 已经固定按 `FULL → PCUT → NCUT → EXTR → FCYC → FULL` 循环。
- 不改变原有采样顺序。
- 不改变 ADC、BRAM、sensor power timing。
- 只增加 sample 分组信息。

---

### `rtl/capture_uart_streamer.v`

改动：

1. 新增输入端口：

```verilog
input wire [15:0] sample_id,
input wire [2:0]  mode_idx,
```

2. 新增 5 位十进制输出函数 `dec_digit5()`，用于把 `sample_id` 输出为固定宽度：

```text
00000
00001
00012
00123
```

3. Header 从旧格式：

```text
V6.4,MODE=FULL,SPWR=0,TXN=01
```

改成新格式：

```text
V6.5,SID=00000,MID=0,FULL,SPWR=0,TXN=01
```

4. CH1/CH2 数据行格式不变：

```text
CH1,RAW,128,...
CH2,RAW,128,...
```

注意：

- UART payload 只增加 header 字节，不改变数据体。
- 保持一帧一个 mode，没有改成一个大包。
- 符合 DeepSeek 方案里的“带 sample_id 的 1 mode = 1 frame”。

---

## PC 脚本改动

### `scripts/capture_ascii_v60.py`

虽然文件名仍叫 `capture_ascii_v60.py`，但已经支持 V6.5。

改动：

1. 新增 V6.5 header parser：

```python
^V6\.5,SID=(\d{5}),MID=([0-4]),(FULL|PCUT|NCUT|EXTR|FCYC),SPWR=([01]),TXN=([0-9A-F]{2})$
```

2. 保留 V6.0-V6.4 legacy parser：

```text
V6.x,MODE=FULL,SPWR=0,TXN=01
```

legacy 模式下会按 `frame_index // 5` 推断 `sample_id`，用于旧数据兼容。

3. CSV 输出新增列：

```text
pc_time_iso,type,sample_id,mode_idx,txn,mode,spwr,CH1_000..CH1_127,CH2_000..CH2_127
```

4. 新增 `--samples` 参数：

```powershell
python scripts/capture_ascii_v60.py --port COM5 --samples 40
```

内部等价于：

```text
frames = samples × 5
```

5. 新增 `--condition` 参数，用于输出文件名标记：

```powershell
python scripts/capture_ascii_v60.py --sensor B2-1 --condition NTNP --samples 40
```

6. 新增 `--test` 自测：

```powershell
python scripts/capture_ascii_v60.py --test
```

自测内容：

- 构造 2 个 sample，共 10 帧。
- 检查 V6.5 header 解析。
- 检查每个 sample 都有 MID 0-4。

7. 采集结束后生成 sample metadata：

```text
v65_B2-1_NTNP_YYYYMMDD_HHMMSS_samples.csv
```

其中包含：

```text
sample_id,valid,order_ok,frame_count,missing_mode_idx,duplicate_mode_idx,modes,txns
```

---

### `scripts/post_process.py`

新增后处理脚本。

用途：把 V6.5 CSV 转换为 analysis-ready numpy 数据。

使用：

```powershell
python scripts/post_process.py logs/v65_B2-1_NTNP_20260616_120000.csv
```

输出：

```text
processed/v65_B2-1_NTNP_20260616_120000_X_cycles.npz
processed/v65_B2-1_NTNP_20260616_120000_metadata_cycles.csv
```

`X_cycles.npz` 内部主要字段：

```python
X.shape == [N, 5, 2, 128]
mode_names == ["FULL", "PCUT", "NCUT", "EXTR", "FCYC"]
channel_names == ["CH1", "CH2"]
sample_id
sensor_id
condition
valid
```

这就是后续对比学习 / LDA / FULL-only / NCUT-only 分析的推荐入口。

---

## Testbench 改动

### `sim/tb_uart_ascii_stream.sv`

改动：

- streamer 实例补入：

```verilog
.sample_id(sample_id)
.mode_idx(mode_idx)
```

- `VERSION_MINOR` 改为 `8'd5`。
- header 断言改为检查：

```text
V6.5,SID=00012,MID=0,FULL,SPWR=1,TXN=3C
```

---

### `sim/tb_trigger_chain.sv`

改动：

- top FSM mirror 中加入 `sample_id` 和 `mode_idx`。
- mode 从旧的 toggle 测试改为 5-mode 递增：

```verilog
mode_select <= (mode_select == 3'd4) ? 3'd0 : mode_select + 3'd1;
```

- 测试目标改为跑 6 次 capture：
  - 第 1-5 次覆盖一个完整 sample。
  - 第 6 次进入下一个 sample 的 FULL。
- 验证：

```text
sample_id == 1
```

即完成一次 FCYC 后正好 +1。

---

### `sim/tb_v60_top_test.v`

该文件标记 `SIM_SKIP`，但为了避免直接使用时端口不匹配，也补了：

```verilog
.sample_id(16'd0)
.mode_idx(3'd0)
```

---

## 文档改动

更新文件：

```text
doc/ARCHITECTURE.md
doc/README.md
CLAUDE.md
README.md
PROGRESS.md
```

主要更新：

- 项目版本 V6.4 → V6.5。
- UART frame format 更新为 `SID/MID` 格式。
- 说明 `SID` 是 sample 分组，`MID` 是 sample 内模式序号。

---

## QA 文件

新增：

```text
.harness/qa/QA_REPORT_20260616_v65_cycle_format.md
```

里面记录了：

- 改动范围
- 在 sandbox 已完成的验证
- 未在 sandbox 执行的 harness check 原因
- 本地后续验证步骤

---

## 已在 sandbox 完成的验证

已执行：

```bash
python3 scripts/capture_ascii_v60.py --test
```

结果：

```text
SELFTEST PASS: V6.5 header parse + sample completeness validation
```

已执行：

```bash
python3 -m py_compile scripts/capture_ascii_v60.py scripts/post_process.py
```

结果：通过。

未执行：

```powershell
.\.harness\tasks.ps1 check
```

原因：当前 sandbox 是 Linux，没有本仓库 harness 依赖的 Windows PowerShell / Vivado / Verilator 路径。

---

## 本地 Claude Code 下一步建议

请本地 Claude Code 按以下顺序继续。

### 1. 应用 patch

在仓库根目录执行：

```bash
git apply v65_cycle_format.patch
```

如果遇到换行问题，可尝试：

```bash
git apply --ignore-whitespace v65_cycle_format.patch
```

### 2. 先跑 Python parser 自测

```powershell
python PUF_dataTransFreq_v60_capture/scripts/capture_ascii_v60.py --test
```

期望：

```text
SELFTEST PASS: V6.5 header parse + sample completeness validation
```

### 3. 跑 harness check

```powershell
.\.harness\tasks.ps1 check
```

如果失败，优先检查：

- `capture_uart_streamer.v` 的 Verilog-2001 兼容性。
- `dec_digit5()` 中除法/取模是否被当前综合/仿真工具接受。
- testbench 端口是否还有遗漏。

### 4. build / program

check 通过后：

```powershell
.\.harness\tasks.ps1 build
.\.harness\tasks.ps1 program
```

### 5. 上板小样本验证

```powershell
.\.harness\tasks.ps1 capture -Port COM5 --samples 10
```

或者直接：

```powershell
python PUF_dataTransFreq_v60_capture/scripts/capture_ascii_v60.py --port COM5 --sensor B2-1 --condition NTNP --samples 10
```

检查 CSV header 是否包含：

```text
sample_id,mode_idx
```

检查每个 sample：

```text
SID=k,MID=0,FULL
SID=k,MID=1,PCUT
SID=k,MID=2,NCUT
SID=k,MID=3,EXTR
SID=k,MID=4,FCYC
```

### 6. 生成 analysis-ready 数据

```powershell
python PUF_dataTransFreq_v60_capture/scripts/post_process.py <new_csv_path>
```

确认：

```python
X.shape == [samples, 5, 2, 128]
```

---

## 注意事项 / 风险点

### 1. `sample_id` 固定 5 位十进制

当前 header 使用：

```text
SID=00000
```

`sample_id` 是 16-bit，理论范围 0-65535。5 位十进制只能完整显示 0-99999，所以 16-bit 范围足够。

### 2. `dec_digit5()` 使用除法和取模

当前实现为了最小改动，直接在 Verilog function 中使用 `/` 和 `%` 对常数取位。

如果 Vivado 综合认为资源或时序不理想，本地 Claude Code 可以改为：

- BCD 计数器
- 或只输出 4 位 hex `SID=0000`
- 或 PC 端接受 hex SID

但根据 DeepSeek 方案，这版先按 5 位十进制实现。

### 3. `capture_ascii_v60.py` 文件名未改

为了减少 harness / 文档 / 脚本入口连锁改动，文件名仍保留：

```text
capture_ascii_v60.py
```

但功能已经支持 V6.5。

### 4. 没改 sensor_power_control

符合方案：

```text
sensor_power_control.v 无需改动
```

因为 mode 输入和电源时序逻辑不变。

### 5. 没改采样顺序

当前 FPGA 本来就是：

```text
FULL → PCUT → NCUT → EXTR → FCYC → FULL
```

本 patch 不改变顺序，只显式记录 sample 边界。

---

## 推荐 commit message

```text
feat: add V6.5 cycle-aware capture format
```

详细 commit body 可用：

```text
Add sample_id and mode_idx to V6.5 UART frames so every
FULL/PCUT/NCUT/EXTR/FCYC group is explicitly represented as one sample.

- Add sample_id counter in top-level FSM, incrementing after FCYC
- Add SID/MID fields to capture_uart_streamer header
- Update PC capture parser with --samples and sample completeness checks
- Add post_process.py to export X_cycles.npz as [N,5,2,128]
- Update UART and trigger-chain testbenches
- Update architecture docs and QA handoff
```
