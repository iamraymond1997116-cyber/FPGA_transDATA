# CAPTURE_PROTOCOL — V6.5 采集行为规范

> 怎么采才靠谱、怎么验、怎么分析。**采集时**和**分析时**都先读这里。
>
> 字段含义/文件结构 → [DATA_FORMAT.md](DATA_FORMAT.md)
> 历史一次性实施记录 → [../V65_CYCLE_FORMAT_HANDOFF.md](../V65_CYCLE_FORMAT_HANDOFF.md)

---

## 1. 标准采集流程

### 1.1 单次采集命令

```powershell
python scripts/capture_ascii_v60.py ^
    --port COM5 ^
    --sensor B2-1 ^
    --condition NTNP ^
    --samples 100 ^
    --out-dir logs/<dataset_name>
```

四件套自动产出（详见 DATA_FORMAT.md §1）：
```
<stem>.csv / <stem>.npy / <stem>_samples.csv / <stem>_session.json
```

### 1.2 采集顺序（每个传感器固定）

```
NTNP → NTHP → HTNP → HTHP
```

不跳序、不漏条件。换条件要等温压稳定后再开采。

### 1.3 采集计划（标准数据集）

| 维度 | 取值 |
|:---|:---|
| 传感器 | B2-1 ~ B2-10 |
| 条件 | NTNP / NTHP / HTNP / HTHP |
| 每文件 sample 数 | 100（推荐）/ 40（最低）|
| 模式 | 5 种自动循环（FULL/PCUT/NCUT/EXTR/FCYC）|

**总数据量**：10 × 4 × 100 = 4000 sample = 20000 帧。
**纯采集时间**：~5.4 分钟（V6.5 ASCII，~62 fps）。

---

## 2. 采集质量校验

### 2.1 每采一次必须校验（采完那条命令立即看终端）

V6.6 采集脚本采完会直接打印这些数字。**任何一个非零都意味着这个 CSV 不能用，立刻重采。**

| 指标 | 正常值 | 异常值 | 含义 / 触发条件 |
|:---|---:|---:|:---|
| `parse_errors` | 0 | > 0 | UART 行 **CRC8 不匹配**（V6.6 R1）或字段格式错。原始字节进 `_errors.log` |
| `sample_errors` | 0 | > 0 | sample 不完整 / 顺序错（V6.6 R3 `txn_gap_ok` / `mid_strict_order` / `sid_monotonic` 任一失败）|
| `saturated` | 0 ~ 5 | > 50 | ADC 落在 ±0x7FFF 边界次数（饱和）|
| `samples kept` | ≈ `--samples` | 显著少 | `boundary_dropped + sample_errors` 太多 |
| 帧间波动 frmVar | < 10 | > 10 | 信号不稳（电源虚接 / 温压未稳）|
| CH1/CH2 峰值 | ~11000 | < 1000 | 传感器无供电 / 断路 |
| CH1/CH2 峰值 | ~11000 | > 22000 | 电源虚接 / 接触不良（异常翻倍）|

如果 `parse_errors > 0`：打开 `<stem>_errors.log` 看具体哪几行 CRC 出错；通常是 UART 物理层问题，重接线或重启板子再试。
如果 `sample_errors > 0`：打开 `<stem>_samples.csv`，看哪几行 `valid=0`，三列 `txn_gap_ok` / `mid_strict_order` / `sid_monotonic` 哪个是 0 就知道根因。

### 2.2 整轮采完做完整性扫描

10 传感器 × 4 条件采完后，跑一次全量扫描确认没漏：

```powershell
python scripts/check_all_stability.py     # 全量稳定性扫描
python scripts/find_bad_data.py           # 定位异常文件
```

或者直接看 `processed/manifest.json`（`post_process.py --glob` 产出）：

```powershell
python scripts/post_process.py --glob "logs/<dataset>/v66_*.csv" --out-dir logs/<dataset>/processed
```

`manifest.json` 字段：

| 字段 | 含义 |
|:---|:---|
| `total_samples` | 整轮 sample 总数 |
| `total_valid` | 通过 V6.6 全部校验的 sample 数 |
| `files[].valid / .samples` | 每个文件单独的有效率 |
| `files[].saturated` | 每个文件 ADC 饱和总数 |

**理想状态**：`total_valid == total_samples`，每个文件 `valid == samples`。
**异常状态**：任何 `valid < samples` → 看对应的 `_samples.csv` 找根因 → 决定重采还是丢弃。

### 2.3 异常处理决策表

| 现象 | 可能根因 | 动作 |
|:---|:---|:---|
| FLAT（峰值 < 1000） | 传感器未供电 | 检查电源线，重采 |
| UNSTABLE（frmVar > 10） | 电源线虚接 / 接触不良 | 重接电源线，重采 |
| 单通道异常（CH1 OK / CH2 不稳） | 通道硬件问题 | 标记后分析仅用正常通道（如 B2-4 仅 CH1）|
| `parse_errors > 0` 持续出现 | UART 物理层（接线 / 干扰）| 检查 USB 线、重启板子 |
| `parse_errors` 偶发 1~2 次 | 单次电平干扰 | V6.6 CRC 已挡住该帧，无须重采 |
| `sample_errors > 0`（mid_strict_order=0）| FPGA 状态机异常 | 检查 RTL 是否被改坏，重新 program |
| `sample_errors > 0`（txn_gap_ok=0）| UART 丢字节 / 缓冲溢出 | 重启板子，看是否 PC 端 buffer 太小 |
| `sample_errors > 0`（sid_monotonic=0）| 多次 capture 帧混合 | 应该不会发生；若发生上报 |
| `boundary_dropped_samples > 5` | 采集起停时间偏差大 | 不影响分析（自动 trim），无须重采 |
| `saturated_total > 50` | ADC 饱和频繁 | 检查信号链路、传感器接线 |

---

## 3. 协议级可靠性（V6.6 已实现）

> V6.6 帧头版本号 `V6.6`，每行尾部追加 `*XX` CRC8 trailer（**人类仍可读**）。
> 兼容：解析端检测无 `*` 自动走旧路径（V6.5 / V6.0~V6.4 / 0612 数据集）。

### 3.1 R1 — 行级 CRC8

每行 ASCII 末尾加 `*XX\n`，XX = 该行 payload（不含 `*XX\n`）的 CRC8：

```
V6.6,SID=00012,MID=0,FULL,SPWR=1,TXN=3C*33
CH1,RAW,128,1234,...,1234*E0
CH2,RAW,128,5678,...,5678*B6
```

- 算法：CRC-8/CCITT，poly=`0x07`，init=`0x00`，无反射、无 xor-out
- RTL 实现：`capture_uart_streamer.v` 内 `crc8_step()` 函数，行尾发 `*XX\n` 后重置
- PC 校验：解析时算 CRC，不匹配整帧丢弃 + 写 `_errors.log`
- 检测率：单字符翻转 100%，多字符翻转 ~99.6%
- Overhead：每行 +3 字节（`*XX`），每帧 +9 字节（约 0.7%）

### 3.2 R3 — 帧序号严格校验（纯 PC）

`_samples.csv` 多三列 + 一个汇总 `valid`：

| 列 | 校验内容 |
|:---|:---|
| `txn_gap_ok` | sample 内 5 帧 TXN 严格 +1（含 0xFF→0x00 滚转）|
| `mid_strict_order` | 5 帧 MID 严格 0→4 |
| `sid_monotonic` | 当前 sample_id 大于上一个 |

任一失败 → `valid=0`。无须 RTL/build/program。

### 3.3 现有内置防线（V6.5 已有，仍生效）

- 边界半截 sample 自动丢弃（`--no-trim` 关闭）
- ADC 饱和计数（`saturated` 列）
- session.json 含 git hash + RTL version + host
- `--test` 自测覆盖 parse + 完整性 + trim + saturation

---

## 4. 黄金分析路径

### 4.1 核心原则

**5 种激励模式必须严格分开分析**——不能混在一起。

5 种模式是 5 种完全不同的物理激励。混合时数据方差被"模式差异"主导，淹没传感器身份信号。

### 4.2 黄金模式

**NCUT（mode_idx=2，下电截断）**已验证为黄金模式：
- 信噪比最高
- 类间距离最大（Ratio ~26x，0612 数据集验证）
- 由传感器无源 RC 网络主导，受电源驱动扰动小

### 4.3 标准特征提取流程

```
1. 取单个模式（推荐 NCUT）的所有 sample
2. CH1-CH2 共模抑制差分（CMR）   ← 抵消温压共模扰动
3. 对 CMR 信号做 FFT，取低频幅值
4. 条件归一化                     ← 减去同条件所有传感器均值
5. 用 sensor_id 监督做 LDA 投影
```

### 4.4 参考代码

完整可复现的 LDA 流水线代码：
[../../logs/0612_4state_10sensers/README.md](../../logs/0612_4state_10sensers/README.md) 第 5 节。

### 4.5 推荐入口

```python
import numpy as np
d = np.load("logs/<dataset>/processed/all_dataset.npz")

# 黄金模式 + 完整性过滤
mask = (d["valid"] == 1)
ncut_ch1 = d["X"][mask, 2, 0, :]   # NCUT CH1
ncut_ch2 = d["X"][mask, 2, 1, :]   # NCUT CH2
cmr      = ncut_ch1 - ncut_ch2     # 共模抑制

# 监督标签
y_sensor = d["sensor_id"][mask]
y_cond   = d["condition"][mask]
```

---

## 5. 工具索引

| 工具 | 用途 |
|:---|:---|
| `scripts/capture_ascii_v60.py` | UART 采集（含 `--test` / `--no-trim`）|
| `scripts/post_process.py` | CSV/npy → npz；含 `--glob` 批量 + manifest |
| `scripts/check_all_stability.py` | 全量稳定性扫描 |
| `scripts/find_bad_data.py` | 定位异常文件 |
| `.harness/tasks.ps1 check` | env + lint + sim 整体健康检查 |

---

## 6. 快速决策树

**采前**：检查 COM5、温压稳定、电源线接好。
**采时**：每个 CSV 跑完看终端 `parse_errors=0` + `sample_errors=0`。任一非零→看 `_errors.log` / `_samples.csv` 找根因，重采。
**换传感器前**：跑 `check_all_stability.py --sensor <id>` 全 OK 再走。
**采完整批**：跑 `post_process.py --glob` 生成 `all_dataset.npz` + `manifest.json`，确认 `total_valid == total_samples`。
**整体异常扫描**：看 `manifest.json` 里有没有 `valid < samples` 的文件，对应 `_samples.csv` 里看 `txn_gap_ok` / `mid_strict_order` / `sid_monotonic` 哪列出问题。
**分析时**：先 `valid=1` 过滤 → 取 NCUT → CMR→FFT→LDA。
