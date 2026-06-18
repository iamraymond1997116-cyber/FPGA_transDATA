# DATA_FORMAT — V6.5 数据格式权威参考

> 任何分析任务读这里。字段含义、文件结构、命名规范有疑问，先翻这里再动手。

---

## 1. 一图三层结构

```
FPGA UART 帧（ASCII）
        │
        ▼   capture_ascii_v60.py
四件套 per capture：
  <stem>.csv               — 元数据（每帧一行，无 ADC 数据）
  <stem>.npy               — ADC int16，shape [N_samples, 5, 2, 128]
  <stem>_samples.csv       — 每个 sample 的有效性
  <stem>_session.json      — 采集环境（git/RTL/host/Python）
  <stem>_errors.log        — 解析失败原始字节（仅在出错时生成）
        │
        ▼   post_process.py
分析就绪：
  <stem>_X_cycles.npz      — 单文件分析数组
  <stem>_metadata_cycles.csv — sample 级元数据
  manifest.json + all_dataset.npz — 批量合并（多文件场景）
```

---

## 2. UART 帧格式

每帧 3 行 ASCII，以 `\n` 分隔。

### V6.5（当前）

```
V6.5,SID=NNNNN,MID=N,MODE,SPWR=N,TXN=NN
CH1,RAW,128,XXXX,XXXX,...,XXXX
CH2,RAW,128,XXXX,XXXX,...,XXXX
```

### V6.6（当前）— 加 CRC8 行尾

```
V6.6,SID=NNNNN,MID=N,MODE,SPWR=N,TXN=NN*HH
CH1,RAW,128,XXXX,XXXX,...,XXXX*HH
CH2,RAW,128,XXXX,XXXX,...,XXXX*HH
```

每行末尾的 `*HH` 是该行 payload 的 **CRC8**（poly=0x07，init=0x00，无反射）。
解析端不匹配整帧丢弃。详见 [CAPTURE_PROTOCOL.md §3](CAPTURE_PROTOCOL.md#3-协议级可靠性v66-已实现)。

### V6.5（兼容）— 同 V6.6 但无 `*HH`

```
V6.5,SID=NNNNN,MID=N,MODE,SPWR=N,TXN=NN
```

| 字段 | 含义 | 取值 |
|:---|:---|:---|
| `V6.6` / `V6.5` | 协议版本 | 固定 |
| `SID=NNNNN` | sample_id，5 位十进制 | 0..65535 |
| `MID=N` | mode_idx，sample 内位置 | 0..4 |
| `MODE` | 模式名 | `FULL`/`PCUT`/`NCUT`/`EXTR`/`FCYC` |
| `SPWR=N` | sensor power 状态 | `0`=ON, `1`=OFF |
| `TXN=NN` | 全局事务号 | `00`..`FF` hex（8-bit 滚） |
| `*HH` | 行 CRC8（仅 V6.6+）| `00`..`FF` hex |
| `XXXX` | ADC 16-bit 有符号，4-hex 大写 | 例 `1A4F` / `FF3C` |

**MID ↔ Mode**：

| MID | Mode | 物理含义 |
|:---:|:---|:---|
| 0 | FULL | ON@0, OFF@64（完整 128 点窗口）|
| 1 | PCUT | ON@0, OFF@8（上电过冲附近截断）|
| 2 | NCUT | OFF@0, ON@8（**黄金模式**）|
| 3 | EXTR | 8/9 交替（极值循环）|
| 4 | FCYC | ON→OFF@32, ON@64, OFF@96（多周期）|

**关键约束**：同一 SID 必须含 5 帧，MID 严格 0→1→2→3→4。FCYC 完成后 SID 才递增。

### V6.0~V6.4（legacy，旧数据集）

```
V6.X,MODE=FULL,SPWR=N,TXN=NN
CH1,RAW,128,...
CH2,RAW,128,...
```

无 SID/MID。post_process 按 frame_index // 5 回填 sample_id。

---

## 3. CSV：`<stem>.csv`（元数据，每帧一行）

| 列 | 类型 | 含义 |
|:---|:---|:---|
| `pc_time_iso` | string | PC 接收时刻（含微秒）|
| `protocol` | string | `V66_RAW` / `V65_RAW` / `V60_RAW` |
| `sensor_id` | string | 采集时 `--sensor` 参数（例 `B2-1`）|
| `condition` | string | 采集时 `--condition` 参数（例 `NTNP`）|
| `sample_id` | int | 完整 sample 序号 |
| `mode_idx` | int | 0..4 |
| `mode` | string | 模式名（与 mode_idx 一致冗余，方便人读）|
| `saturated` | int | 该帧 256 个 ADC 值中落在 0x7FFE/7FFF/8000/8001 的个数 |

**注意**：V6.5+ 已**不再**有 `type`/`spwr`/`txn`/`CH1_xxx`/`CH2_xxx` 列（V6.0~V6.4 仍有）。ADC payload 在配套 `.npy`。

---

## 4. NPY：`<stem>.npy`（ADC payload）

```python
import numpy as np
X = np.load("v65_B2-1_NTNP_20260616_164326_a3f2b1.npy")
X.shape       # (N_samples, 5, 2, 128)
X.dtype       # int16
```

| 维度 | 含义 | 范围 |
|:---|:---|:---|
| 0 | sample（与 CSV `sample_id` 顺序对应）| `[0, N-1]` |
| 1 | mode | `0=FULL, 1=PCUT, 2=NCUT, 3=EXTR, 4=FCYC` |
| 2 | channel | `0=CH1, 1=CH2` |
| 3 | ADC 采样点 | `[0, 128)` |

**索引示例**：
```python
ncut_ch1_all = X[:, 2, 0, :]              # 所有 sample 的 NCUT CH1
full_diff = X[:, 0, 0, :] - X[:, 0, 1, :] # FULL 的 CH1-CH2 差分
```

---

## 5. samples CSV：`<stem>_samples.csv`（sample 级元数据）

| 列 | 含义 |
|:---|:---|
| `sample_id` | sample 序号 |
| `valid` | 1=通过所有校验 \| 0=任一校验失败 |
| `order_ok` | 1=MID 严格 0→4 \| 0=乱序（同 mid_strict_order）|
| `frame_count` | 实际帧数（应为 5）|
| `missing_mode_idx` | 缺失的 MID（管道分隔，如 `0\|1`）|
| `duplicate_mode_idx` | 重复的 MID |
| `saturated_total` | 该 sample 5 帧的 saturated 之和 |
| `txn_gap_ok` | **R3** — sample 内 5 帧 TXN 严格 +1 |
| `mid_strict_order` | **R3** — sample 内 MID 严格 0→4 |
| `sid_monotonic` | **R3** — 当前 sample_id > 上一个 |
| `modes` | 实际收到的模式名顺序（如 `FULL\|PCUT\|NCUT\|EXTR\|FCYC`）|

**`valid`** = 完整 5 帧 ∧ 无缺失 ∧ 无重复 ∧ MID 严格 ∧ TXN 连续 ∧ SID 单调。

**默认采集行为**：首尾半截 sample 已被 `--no-trim` 反向开关丢弃（`session.json` 的 `boundary_dropped_sample_ids` 记录被丢的 SID）。

---

## 6. session.json：`<stem>_session.json`（采集会话元数据）

```json
{
  "tool": "capture_ascii_v60.py",
  "tool_version": "v65-pc-revamp",
  "args": { "port": "COM5", "samples": 10, "sensor": "B2-1", ... },
  "env": {
    "captured_at": "2026-06-17T17:28:24.883458",
    "host": "WCW-Ylab",
    "python_version": "3.13.5",
    "platform": "Windows-11-10.0.26200-SP0",
    "git_hash": "fa7a4f6...",     // 仅当 git 在 PATH 时
    "git_branch": "feature/v6.5-cycle-format",
    "rtl_version": "V6.5"
  },
  "summary": {
    "raw_frames": 50, "kept_frames": 45, "samples_written": 9,
    "boundary_dropped_samples": 2, "boundary_dropped_sample_ids": [55032, 55042],
    "parse_errors": 0, "sample_errors": 0,
    "elapsed_seconds": 0.81, "fps": 61.6,
    "saturated_total": 0, "stem": "..."
  }
}
```

---

## 7. 分析就绪 npz：`<stem>_X_cycles.npz`

由 `post_process.py` 生成。优先从 `<stem>.npy` 加载 ADC（V6.5 快路径），否则解析 CSV hex 列（legacy 路径）。

| Key | shape / dtype | 含义 |
|:---|:---|:---|
| `X` | `(N, 5, 2, 128)` int16 | ADC payload |
| `mode_names` | `(5,)` str | `["FULL","PCUT","NCUT","EXTR","FCYC"]` |
| `channel_names` | `(2,)` str | `["CH1","CH2"]` |
| `sample_id` | `(N,)` int32 | 与 X 第 0 维对齐 |
| `sensor_id` | `(N,)` str | 每 sample 一份（同文件内通常全一致）|
| `condition` | `(N,)` str | 同上 |
| `timestamp` | `(N,)` str | 该 sample 第一帧的 PC 时间 |
| `saturated` | `(N,)` int32 | 该 sample 5 帧 saturated 之和 |
| `valid` | `(N,)` int8 | 完整性 |
| `source_csv` | `(N,)` str | 来源文件名 |
| `git_hash` / `git_branch` / `rtl_version` / `captured_at` / `host` | scalar str | 来自 session.json（V6.5 路径才有）|

**典型分析索引**：
```python
import numpy as np
d = np.load("processed/all_dataset.npz")
mask = (d["sensor_id"] == "B2-1") & (d["condition"] == "NTNP") & (d["valid"] == 1)
ncut_ch1 = d["X"][mask, 2, 0, :]   # 一行抽出黄金模式 CH1
```

---

## 8. 批量合并：`processed/manifest.json` + `all_dataset.npz`

`post_process.py --glob "logs/v65_*.csv"` 模式产出，覆盖整批：

- `all_dataset.npz`：合并所有输入文件的 X + 元数据，`source_csv` 列追溯每个 sample 来自哪个 CSV
- `manifest.json`：人类可读的批次清单，含 `total_samples` / `total_valid` 与每文件统计

---

## 9. 文件命名规范

```
v66_<sensor>_<condition>_<YYYYMMDD>_<HHMMSS>_<uuid6>.<ext>
```

例：`v66_B2-1_NTNP_20260618_092000_a3f2b1.csv`

- `uuid6`：6 字符随机后缀，防同秒级文件冲突
- 4 个产物（`.csv` / `.npy` / `_samples.csv` / `_session.json`）共享前缀
- 仅在出现解析失败时多一个 `_errors.log`

**历史前缀**：`v65_*`（V6.5 cycle-aware）/ `v60_*`（V6.0~V6.4 legacy）。post_process 全部支持。

---

## 10. 物理硬件约束

| 项 | 值 |
|:---|:---|
| FPGA | Artix-7 XC7A200T-2FBG484 |
| ADC | AD7606，16-bit 有符号，±5V 双极性，200 kSPS |
| 时钟 | 200 MHz 差分晶振 → 像素时钟 ~18.18 MHz |
| UART | 1 Mbps，8N1（PC 端 921600 baud 兼容）|
| 帧率 | ~62 fps（V6.6 ASCII + CRC8）|
| 1 帧字节 | ~1343 bytes（V6.6 含 9 字节 CRC trailer）|
| 1 sample 时间 | ~80 ms（5 帧）|

---

## 11. 分析路径

→ 详见 [CAPTURE_PROTOCOL.md §4](CAPTURE_PROTOCOL.md#4-黄金分析路径)（黄金模式 NCUT、CMR→FFT→LDA 流水线、推荐索引代码）。

---

## 12. 历史版本对照

| 版本 | UART 帧 | CSV schema | CRC | 分析就绪 |
|:---|:---|:---|:---|:---|
| V6.0~V6.4 | `V6.X,MODE=...,SPWR=,TXN=` | 含 type/txn/spwr + 256 hex 列 | ❌ | post_process 自动 legacy 识别 |
| V6.5 | `V6.5,SID=,MID=,...,SPWR=,TXN=` | sensor_id/condition 入列；payload 移到 .npy | ❌ | 快路径 |
| **V6.6** | `V6.6,SID=,MID=,...,SPWR=,TXN=*HH` | 同 V6.5 + 行尾 `*HH` CRC8 | ✅ | 快路径 |

**已知数据质量问题**：每批数据集自带 README 列出（如 `logs/0612_4state_10sensers/README.md`）。

---

## 13. 索引到代码

| 文件 | 角色 |
|:---|:---|
| `scripts/capture_ascii_v60.py` | 采集 + 写四件套；含 V6.6 CRC 校验 + R3 序号检查 + `--test` 自测 |
| `scripts/post_process.py` | CSV/npy → npz；含 `--glob` 批量 |
| `rtl/capture_uart_streamer.v` | FPGA 端 UART 帧组装 + 行级 CRC8 |
| `rtl/transient_puf_v60_top.v` | sample_id 计数 + mode_idx 输出 |
| `sim/tb_uart_ascii_stream.sv` | 帧格式 testbench（含 CRC 断言）|
| `doc/V65_CYCLE_FORMAT_HANDOFF.md` | V6.5 实施 handoff（历史快照）|

---

## 14. 路标

| 版本 | 范围 | 状态 |
|:---|:---|:---|
| V6.5 | cycle-aware（SID/MID）+ PC 13 项重构 | ✅ |
| **V6.6** | ASCII 协议加固：行级 CRC8 + 帧序号校验 | ✅ |
| V6.7+ | UART 传输 binary 化 | 🔮 待评估 |

详见 `PROGRESS.md` Roadmap 段。
