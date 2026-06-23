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
| **CH1/CH2 基线 DC（NCUT 稳态段）** | **~10000** | **~20000（≈2×）** | **ADC 量程档位错误（RANGE 引脚被干扰，±5V→±10V）** |

### 2.1.1 基线直流电压对照（采集脚本自动执行）

**V6.6 采集脚本现在自带 NCUT 基线 DC 校验** —— 采完一个文件后会自动算 NCUT 第 30~127 点的 CH1/CH2 均值，并打印：

```
  baseline_NCUT: CH1=10643  CH2=10735  [OK]
```

**判定阈值**（脚本内置，见 `scripts/capture_ascii_v60.py` 顶部 `BASELINE_OK_LOW=5000` / `BASELINE_OK_HIGH=18000`）：

| Verdict | CH1 / CH2 范围 | 动作 |
|:---|---:|:---|
| `OK` | 5000 ~ 18000 | 通过 |
| `DOUBLED` | 任一 > 18000（≈2×）| **脚本自动删文件并重采**（默认 `--max-retries 2`）|
| `FLAT` | 任一 < 5000 | **脚本自动删文件并重采** |

正常值参考（11kΩ 电桥负载，AD7606 ±5V 量程）：

| 模式 | 稳态段索引 | CH1/CH2 基线 DC |
|:---|:---|---:|
| NCUT（黄金模式）| 第 30~127 点 | **~10000 ± 500** |
| FULL | 第 90~127 点 | ~10000 ± 500 |

#### 为什么必须做这一步

历史教训（0618 数据集）：3 个文件的 CH1/CH2 基线全部 ≈21000，其他 37 个正常 ~10000。**真相是 +13088 LSB ≈ +2V 的纯 DC 共模偏置**（不是 ×2 缩放）：

- CH1 + CH2 同步叠加同一共模电压（差值从正常 −86 LSB 塌缩到 −3 LSB）
- 多次出现的 baseline 数值精确到个位一致（21419 跨日期复现）→ 物理稳态

**根因**：AD7606 全局只在 FPGA 上电时 RESET 一次（[rtl/ad7606_if.v:53-63](../../rtl/ad7606_if.v#L53-L63)），异常 DC 稳态没有自恢复机制。仅依赖 sensor 功率序列偶发"摇"出来。

#### 自动重采机制

```powershell
# 默认行为：最多重试 2 次，每次重试前清串口缓冲
python scripts/capture_ascii_v60.py --port COM5 --sensor B2-1 --condition NTNP --samples 100

# 关闭基线校验（不推荐，调试用）
python scripts/capture_ascii_v60.py ... --no-baseline-check

# 调整重试次数
python scripts/capture_ascii_v60.py ... --max-retries 5
```

脚本逻辑：
1. 正常采集 N samples 写入 4 件套
2. `check_baseline_dc()` 读 `.npy`，算 NCUT[:, 30:].mean()
3. 若 DOUBLED/FLAT → 删除该次 4 件套 → 重新进入采集循环（新 stem）
4. 重试上限耗尽仍失败 → 退出码 2，提示用户按 key1 全局 reset 或断电

#### 兜底（脚本救不了时）

| 现象 | 动作 |
|:---|:---|
| 一次 DOUBLED 后自动重采变 OK | 正常，不用管，会话级偶发 |
| 连续 2~3 次都 DOUBLED（重试用完）| 按 FPGA 上 **key1（全局 reset）** → ADC 重 RESET，再跑采集 |
| 按了 key1 还 DOUBLED | 断电重新上电 |
| 断电也救不了 | RTL/硬件级问题，停下来查 RANGE 引脚走线 |

#### 决策表

| 现象 | 决策 | 动作 |
|:---|:---|:---|
| NCUT 基线 ~10000 | ✅ 通过 | 进入下一个工况 |
| NCUT 基线 > 18000（≈2×）| ❌ REJECT | 脚本自动重采（不需要人工干预）|
| NCUT 基线 < 5000 | ❌ REJECT | 脚本自动重采 + 检查传感器电源 |
| 重试用完仍异常 | 🚨 升级 | 按 key1 全局 reset / 断电重启 |

#### 根因（确认）

- 不是 ×2 量程切换（XDC 无 RANGE 引脚约束，AD7606 RANGE 硬接 ±5V）
- 是 +13088 LSB ≈ +2V DC 共模偏置稳态
- AD7606 全局只 RESET 一次（`ad7606_if.v:53-63`），异常稳态自身不会恢复
- 完整 tracer 报告见 git commit `chore: trace baseline doubling root cause`



如果 `parse_errors > 0`：打开 `<stem>_errors.log` 看具体哪几行 CRC 出错；通常是 UART 物理层问题，重接线或重启板子再试。
如果 `sample_errors > 0`：打开 `<stem>_samples.csv`，看哪几行 `valid=0`，三列 `txn_gap_ok` / `mid_strict_order` / `sid_monotonic` 哪个是 0 就知道根因。

### 2.2 整轮采完做完整性扫描

10 传感器 × 4 条件采完后，跑一次全量扫描确认没漏：

```powershell
# V6.6 专用：从 .npy 直接读 NCUT 稳定性（推荐，跳过 CSV 解析）
python scripts/check_v66_stability.py logs/<dataset>

# 通用：从 CSV hex 列读 NCUT 稳定性（兼容 V6.0~V6.5 old datasets）
python scripts/check_all_stability.py

# 独立异常定位
python scripts/find_bad_data.py
```

`check_v66_stability.py` **专为 V6.6 设计**：直接从 `<stem>.npy` 加载 int16 ADC 数据，无需 CSV hex 解析。
`check_all_stability.py` **兼容旧格式**（V6.0~V6.5），从 CSV 列 `CH1_xxx` / `CH2_xxx` 读数据。

两者判断标准一致：frmVar < 10、峰值 > 1000。

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
| **BASELINE_DOUBLED（NCUT 基线 > 18000，≈2×）** | **ADC RANGE 引脚被干扰，量程切到 ±10V** | **删除该文件 + 重启板子 + 重采**（详见 §2.1.1）|
| UNSTABLE（frmVar > 10） | 电源线虚接 / 接触不良 | 重接电源线，重采 |
| 单通道异常（CH1 OK / CH2 不稳） | 通道硬件问题 | 标记后分析仅用正常通道（如 B2-4 仅 CH1）|
| `parse_errors > 0` | UART 物理层（接线 / 干扰）| 检查 USB 线、重启板子，重采 |
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
| `scripts/capture_ascii_v60.py` | UART 采集（含 `--test` / `--no-trim`，V6.6 CRC+R3 校验）|
| `scripts/post_process.py` | CSV/npy → npz；含 `--glob` 批量 + manifest |
| `scripts/check_v66_stability.py` | V6.6 专用 NCUT 稳定性扫描（从 `.npy` 读，推荐）|
| `scripts/check_all_stability.py` | 通用 NCUT 稳定性扫描（从 CSV hex 列读，兼容 V6.0~V6.5）|
| `scripts/find_bad_data.py` | 定位异常文件 |
| `.harness/tasks.ps1 check` | env + lint + sim 整体健康检查 |

---

## 6. 快速决策树

**采前**：检查 COM5、温压稳定、电源线接好。
**采时**：每个 CSV 跑完看终端 `parse_errors=0` + `sample_errors=0`。任一非零→看 `_errors.log` / `_samples.csv` 找根因，重采。
**采完一个文件**：跑 §2.1.1 基线 DC 对照（NCUT 基线 ~10000；> 18000 或 < 5000 必须重采）——**这是最后一道防线**。
**换传感器前**：跑 `python scripts/check_v66_stability.py logs/<dataset> --sensor <id>` 全 OK 再走（已含 `NCUT_mean` 列）。
**采完整批**：跑 `check_v66_stability.py logs/<dataset>` 全量扫描 + `post_process.py --glob` 生成 `all_dataset.npz` + `manifest.json`，确认 `total_valid == total_samples`，并人工扫一遍所有 `NCUT_mean` 是否在 ~10000 范围内。
**整体异常扫描**：看 `manifest.json` 里有没有 `valid < samples` 的文件，对应 `_samples.csv` 里看 `txn_gap_ok` / `mid_strict_order` / `sid_monotonic` 哪列出问题。
**分析时**：先 `valid=1` 过滤 → 取 NCUT → CMR→FFT→LDA。
