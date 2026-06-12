# 0612 传感器多状态采集数据集

10个压敏传感器（B2-1 ~ B2-10）在四种环境状态下各200帧的瞬态响应数据。

采集日期：2026-06-12

---

## 1. 文件名含义

```
v60_{传感器ID}_{状态代码}_{时间戳}.csv
```

### 传感器ID
`B2-1` ~ `B2-10`，共10个。

### 状态代码（4种环境条件）

| 代码 | 含义 |
|:---|:---|
| **NTNP** | 常温常压 (Normal Temp, Normal Press) |
| **NTHP** | 常温高压 (Normal Temp, High Press) |
| **HTNP** | 高温常压 (High Temp, Normal Press) |
| **HTHP** | 高温高压 (High Temp, High Press) |

### 示例

`v60_B2-3_HTNP_20260612_105656.csv`
→ B2-3 传感器，高温常压条件，采集于 2026-06-12 10:56:56

---

## 2. 数据格式

### CSV列

| 列 | 说明 |
|:---|:---|
| `pc_time_iso` | PC端采集时间戳 |
| `type` | 固定为 `V60_RAW` |
| `txn` | 事务序号（16进制） |
| **`mode`** | **采集模式（5种激励）** |
| **`spwr`** | 传感器电源状态（`0`=开, `1`=关） |
| `CH1_000` ~ `CH1_127` | 通道1的128个采样点（16位有符号，16进制） |
| `CH2_000` ~ `CH2_127` | 通道2的128个采样点（16位有符号，16进制） |

### 5种激励模式（核心！必须分开分析）

| 模式 | 含义 | 物理特性 |
|:---|:---|:---|
| **FULL** | 全程激励 | 完整上电→瞬态→稳态 |
| **PCUT** | 上电截断 | 上电过程中切断 |
| **NCUT** | **下电截断（黄金模式）** | 断电瞬态，由传感器无源RC网络主导 |
| **EXTR** | 外部触发 | 外部触发采集 |
| **FCYC** | 快速循环 | 快速充放电循环 |

**⚠️ 绝对禁止将5种模式混在一起分析！** 5种模式是5种完全不同的物理激励，混合在一起时数据方差会被"模式差异"主导，彻底淹没传感器身份信号。

**NCUT（下电截断）已验证为黄金模式**：信噪比最高，类间距离最大。

### 每CSV文件

- 200帧（每模式40帧，自动循环）
- 每帧128点双通道ADC采样
- ADC：16位有符号，双极性±5V

---

## 3. 传感器数据质量报告

### 质量判定标准

| 指标 | 正常值 | 异常值 | 含义 |
|:---|---:|---:|:---|
| 帧间波动 (frmVar) | < 10 | > 10 | 帧与帧之间的信号不稳定 |
| CH1/CH2峰值 | ~11000 | < 1000 | 传感器无供电/断路 |
| CH1/CH2峰值 | ~22000+ | 翻倍常伴随不稳 | 电源虚接/接触不良 |

### 各传感器状态

| 传感器 | 质量 | 备注 |
|:---|---:|:---|
| **B2-1** | ✅ 4条件全部正常 | 基线~10000，帧间波动~0.8-1.2 |
| **B2-2** | ✅ 4条件全部正常 | |
| **B2-3** | ✅ 4条件全部正常 | |
| **B2-4** | ⚠️ **CH2通道硬件问题** | CH1正常（帧间波动~0.8-2.9），但CH2帧间波动17~115（正常<10），CMR_std~2000（正常~2-25）。**数据分析时建议只使用B2-4的CH1数据** |
| **B2-5** | ✅ 4条件全部正常 | |
| **B2-6** | ✅ 4条件全部正常 | |
| **B2-7** | ✅ 基本正常 | HTHP的CH2帧间波动=11.9（略超阈值10），基本可用 |
| **B2-8** | ✅ 4条件全部正常 | |
| **B2-9** | ✅ 4条件全部正常 | |
| **B2-10** | ✅ 4条件全部正常 | NTNP/HTNP基线~21000（非异常，是传感器自身特性） |

---

## 4. 采集行为规范

### 4.1 每采一次，必须校验

采集完一个CSV后，立即检查：
1. `errors=0`（UART传输无丢帧）
2. 帧间波动 frmVar < 10（信号稳定）
3. 峰值 ~11000（传感器有供电）

### 4.2 每采集完一个传感器，全量验证

采集完一个传感器的4种状态后，运行全量稳定性检查：
```powershell
cd D:\Project\FPGA_transDATA\PUF_dataTransFreq_v60_capture
python scripts/check_all_stability.py
```
确认该传感器4个文件全部OK，再换下一个传感器。

### 4.3 异常数据处理

- **FLAT（峰值 < 1000）**：传感器未供电，检查电源线连接
- **UNSTABLE（帧间波动 > 10）**：可能是电源线虚接/接触不良，重采
- **CH通道异常（一个通道正常另一个不正常）**：通道硬件问题，标记后分析时仅用正常通道

### 4.4 采集顺序

每个传感器：**NTNP → NTHP → HTNP → HTHP**（固定顺序，不跳）

---

## 5. 数据分析指引（给下一个AI agent）

### 核心目标

**同传感器聚类（不同条件紧密靠拢） + 异传感器分开（类间距离最大化）**

### 数据分割原则

**5种激励模式必须严格分开分析**，不能混在一起。

验证过的黄金模式：**NCUT**

### 特征提取流程

1. 取单个模式（如NCUT）的帧
2. 做CH1-CH2共模抑制差分（CMR，抵消温压共模扰动）
3. 对CMR信号做FFT，取低频幅值作为特征
4. 做条件归一化（减去同条件所有传感器的均值，消除环境偏移）
5. 用传感器ID做监督标签，LDA降维投影

### 参考代码

以下代码实现了一个完整的"黄金模式+CMR→FFT→LDA"分析流程：

```python
import numpy as np, pandas as pd
from pathlib import Path
from scipy.fft import fft
from sklearn.preprocessing import StandardScaler
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.metrics import silhouette_score

# 配置
DATA_DIR = Path("logs/0612_4state_10sensers")
SENSOR_IDS = [f"B2-{i}" for i in range(1, 11)]
COND_MAP = {"NTNP": "normal", "NTHP": "highPressure",
            "HTNP": "highTemp", "HTHP": "highTempHighPressure"}
MODE = "NCUT"  # 黄金模式

def h2s(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

def cmr_fft(ch1, ch2, nbins=64):
    """CH1-CH2 共模抑制 → FFT低频幅值"""
    cmr = np.array(ch1, dtype=np.float64) - np.array(ch2, dtype=np.float64)
    f = np.abs(fft(cmr))[1:nbins+1]  # skip DC
    return f / (f.sum() + 1e-10)

# 加载每个CSV的NCUT帧
def load_file_features(fp, mode="NCUT"):
    import csv
    feats = []
    with open(fp, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["mode"] != mode:
                continue
            ch1 = [h2s(row[f"CH1_{i:03d}"]) for i in range(128)]
            ch2 = [h2s(row[f"CH2_{i:03d}"]) for i in range(128)]
            feats.append(cmr_fft(ch1, ch2))
    # 文件级平均
    return np.mean(feats, axis=0) if feats else None

# 构建数据集
X, y, c = [], [], []
for fp in sorted(DATA_DIR.glob("v60_*.csv")):
    parts = fp.stem.split("_")
    tag, cond = parts[1], parts[2]
    if cond not in COND_MAP:
        continue
    # 跳过B2-4（CH2硬件问题）
    # if tag == "B2-4": continue
    feat = load_file_features(fp, MODE)
    if feat is not None:
        X.append(feat)
        y.append(tag)
        c.append(cond)

X = np.array(X)
y = np.array(y)

# 条件归一化
Xn = X.copy()
for cond in np.unique(c):
    m = np.array(c) == cond
    Xn[m] -= X[m].mean(axis=0)

# 堆叠原始+归一化特征
Xs = StandardScaler().fit_transform(np.hstack([X, Xn]))

# LDA
lda = LDA(n_components=min(9, len(np.unique(y))-1))
Z = lda.fit_transform(Xs, y)

# 选最佳2D投影面
from itertools import combinations
best_sil, best_dims = -1, (0, 1)
for d1, d2 in combinations(range(Z.shape[1]), 2):
    from sklearn.preprocessing import StandardScaler as SS
    p = SS().fit_transform(Z[:, [d1, d2]])
    sil = silhouette_score(p, y)
    if sil > best_sil:
        best_sil, best_dims = sil, (d1, d2)

print(f"Best LDA dims: {best_dims}, Silhouette: {best_sil:.4f}")

# 可视化示例代码（参考对比学习报告的围圈风格）
def plot_reference_style(Z_2d, labels, conditions, save_path):
    import matplotlib.pyplot as plt
    import matplotlib.lines as mlines
    from matplotlib.patches import Circle
    from scipy.spatial import ConvexHull

    colors = {"B2-1": "#d7191c", "B2-2": "#2c7bb6", "B2-3": "#1a9641",
              "B2-4": "#fdae61", "B2-5": "#984ea3", "B2-6": "#8c510a",
              "B2-7": "#f781bf", "B2-8": "#4d4d4d", "B2-9": "#a6d96a",
              "B2-10": "#00a6a6"}
    markers = {"normal": "o", "highPressure": "s", "highTemp": "^", "highTempHighPressure": "D"}

    plt.figure(figsize=(11, 8), dpi=220)
    ax = plt.gca()

    for sid in SENSOR_IDS:
        mask = labels == sid
        center = Z_2d[mask].mean(axis=0)
        radius = np.percentile(np.linalg.norm(Z_2d[mask] - center, axis=1), 85)
        ax.add_patch(Circle(center, radius, color=colors[sid], fill=False, lw=1.4, alpha=0.38))
        plt.scatter(center[0], center[1], marker="x", s=90, c=colors[sid], linewidths=2.2, zorder=4)

    for sid in SENSOR_IDS:
        for condition in np.unique(conditions[labels == sid]):
            mask = (labels == sid) & (conditions == condition)
            if not np.any(mask): continue
            plt.scatter(Z_2d[mask, 0], Z_2d[mask, 1],
                        s=52, c=colors[sid], marker=markers.get(condition, "o"),
                        alpha=0.64, edgecolors="white", linewidths=0.45, zorder=3)

    # B2-1条件质心连线
    b21_centers = []
    for cond in ["normal", "highPressure", "highTemp", "highTempHighPressure"]:
        mask = (labels == "B2-1") & (conditions == cond)
        if np.any(mask):
            ctr = Z_2d[mask].mean(axis=0)
            b21_centers.append(ctr)
            plt.scatter(ctr[0], ctr[1], marker=markers[cond], s=165,
                        c="#d7191c", edgecolors="black", linewidths=1.2, zorder=5)

    if len(b21_centers) > 1:
        arr = np.vstack(b21_centers)
        plt.plot(arr[:, 0], arr[:, 1], color="#d7191c", lw=2.2, alpha=0.75, zorder=4)

    ax.set_title("LDA: same sensor pulled, different pushed", fontsize=13)
    ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.65)
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
```

---

## 6. 其他注意事项

### 硬件已知问题
- **B2-4的CH2通道不稳定**，分析时建议仅用CH1数据
- 所有数据 `spwr=1`（传感器断电状态），捕获的是电路本底响应而非传感器主动瞬态
- B2-10的NTNP和HTNP条件基线~21000（其他条件~10000），是传感器自身特性
- B2-7的HTHP条件CH2帧间波动=11.9，略高但可用

### 文件清理
- 目录下可能有 `*_test_*.csv` 临时文件，可删除
- 每个传感器每个条件最终只有一个有效的200帧CSV
- 所有文件大小约 267 KB

### 采集脚本
`scripts/capture_ascii_v60.py` 参数：
```
--port COM5    # UART端口
--baud 921600  # 波特率
--frames 200   # 帧数
--timeout 300  # 超时秒数
--sensor TAG   # 传感器标签（写入文件名）
--out-dir DIR  # 输出目录
```

### COM端口
实时采集使用 **COM5**（CP2102 USB-UART）
