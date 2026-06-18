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

### 2.1 每采一次必须校验

采完一个 CSV 后立即检查：

| 指标 | 正常值 | 异常值 | 含义 |
|:---|---:|---:|:---|
| `parse_errors` | 0 | > 0 | UART 解析失败（丢字节/编码错）|
| `sample_errors` | 0 | > 0 | sample 不完整（缺 mode/重复/乱序）|
| `saturated_total` | 0~5 | > 50 | ADC 落在 ±0x7FFF 边界次数（饱和）|
| 帧间波动 frmVar | < 10 | > 10 | 帧与帧之间的信号不稳定 |
| CH1/CH2 峰值 | ~11000 | < 1000 | 传感器无供电/断路 |
| CH1/CH2 峰值 | ~11000 | > 22000 | 电源虚接/接触不良（异常翻倍）|

校验工具：
```powershell
python scripts/check_all_stability.py     # 全量稳定性扫描
python scripts/find_bad_data.py           # 定位异常文件
```

### 2.2 每个传感器 4 条件采完做完整性检查

```powershell
python scripts/check_all_stability.py --sensor B2-1
```

确认 4 个文件全部 OK 再换下一个传感器。

### 2.3 异常处理决策表

| 现象 | 含义 | 动作 |
|:---|:---|:---|
| FLAT（峰值 < 1000） | 传感器未供电 | 检查电源线，重采 |
| UNSTABLE（frmVar > 10） | 电源线虚接 / 接触不良 | 重接电源线，重采 |
| 单通道异常（CH1 OK / CH2 不稳） | 通道硬件问题 | 标记后分析仅用正常通道（如 B2-4 仅 CH1）|
| `boundary_dropped_samples > 5` | 采集起停时间偏差大 | 不影响分析（自动 trim），无须重采 |
| `saturated_total > 50` | ADC 饱和频繁 | 检查信号链路、传感器接线 |

---

## 3. 协议级可靠性（V6.5 加固项）

### 3.1 R1 — 行级 CRC8（计划中）

每行 ASCII 末尾加 `*XX\n`：
```
V6.5,SID=00012,MID=0,FULL,SPWR=1,TXN=3C*A4
CH1,RAW,128,1234,...,9ABC*B7
CH2,RAW,128,1234,...,9ABC*9D
```

- RTL 端：UART streamer 同步算 CRC8（~50 LUT）
- PC 端：解析时校验，错则丢帧并写 `_errors.log`
- 检测率：单字符 hex 翻转 100%，多字符翻转 ~99.6%

### 3.2 R3 — 帧序号严格校验（计划中）

PC 端在 `_samples.csv` 多三列：
- `txn_gap` — TXN 是否连续 +1（含 0xFF→0x00 滚转）
- `sid_monotonic` — SID 是否单调递增
- `mid_strict_order` — sample 内 5 帧 MID 是否严格 0→4

任一失败 → `valid=0`。

### 3.3 现有内置防线（V6.5 已有）

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
**采时**：每个 CSV 跑完看 `parse_errors=0` + `sample_errors=0`。
**换传感器前**：跑 `check_all_stability.py --sensor <id>` 全 OK 再走。
**采完整批**：跑 `post_process.py --glob` 生成 `all_dataset.npz` + `manifest.json`。
**分析时**：先 `valid=1` 过滤 → 取 NCUT → CMR→FFT→LDA。
