# 0618 数据集分析说明书 — 对比学习可视化

> 给分析 AI 的任务书。输入两个文件，产出对比学习点云图 + 关键指标。

---

## 1. 输入文件（在同一个目录下）

| 文件 | 说明 |
|:---|:---|
| `all_dataset.npz` | 全部数据，shape=(3967, 5, 2, 128)，附带传感器 ID、条件、校验标记等元数据 |
| `manifest.json` | 数据集汇总清单（每个文件的 sample 数、有效性、饱和数） |

## 2. 数据形状

```python
import numpy as np
d = np.load("all_dataset.npz")
X = d["X"]                       # (3967, 5, 2, 128)  int16
#   dim0: sample（每个 sample = 一个传感器的完整 5 模式数据）
#   dim1: mode（0=FULL, 1=PCUT, 2=NCUT, 3=EXTR, 4=FCYC）
#   dim2: channel（0=CH1, 1=CH2）
#   dim3: 128 个 ADC 采样点（16-bit 有符号, ±5V）
```

元数据：
```python
d["sensor_id"]   # (3967,) str  — B2-1~B2-10
d["condition"]   # (3967,) str  — NTNP / NTHP / HTNP / HTHP
d["valid"]       # (3967,) int8 — 全 1（此数据集 100% 校验通过）
d["sample_id"]   # (3967,) int32
d["timestamp"]   # (3967,) str  — 采集时 PC 时间
d["mode_names"]  # ['FULL' 'PCUT' 'NCUT' 'EXTR' 'FCYC']
d["channel_names"]  # ['CH1' 'CH2']
```

## 3. 分析目标

**对比学习的核心目标**：同一个传感器在不同环境条件（温度、压力）下的样本应该被拉近聚成一簇，不同传感器的样本应该被推开。

提取特征 → 降维投影 → 画出点云图，验证这个目标是否达成。

关键指标：
- **轮廓系数 (silhouette score)** — 越高越好（参考值：~0.85+ 表示很好的分离）
- **最近质心分类准确率** — 每个传感器到自己的质心最近就是对的（参考值：1.0000）
- **异类/同类距离比** — 越大越好（参考值：> 10x）

## 4. 数据预处理（必须做）

### 4.1 只取黄金模式

**NCUT（mode_idx=2）已验证为黄金模式**——信噪比最高，类间距离最大。**不要混用 5 种模式。**

```python
ncut = X[:, 2, :, :]  # (3967, 2, 128)
```

### 4.2 CH1-CH2 共模抑制（CMR）

消除温度和压力变化带来的共模扰动：
```python
cmr = ncut[:, 0, :] - ncut[:, 1, :]  # (3967, 128)
```

### 4.3 条件归一化（关键步骤）

不同环境条件下所有传感器的整体偏移要消除，否则环境差异会压倒传感器身份差异：

```python
cmr_normalized = cmr.copy().astype('f8')
for cond in ['NTNP', 'NTHP', 'HTNP', 'HTHP']:
    mask = d['condition'] == cond
    cmr_normalized[mask] -= cmr[mask].mean(axis=0)
```

## 5. 特征提取

### 5.1 推荐的特征组合（已验证有效）

```python
from scipy.fft import fft
import numpy as np
from sklearn.preprocessing import StandardScaler

def extract_features(cmr_signal, nbins=64):
    """
    cmr_signal: (N, 128) CH1-CH2 差分
    返回: (N, nbins) FFT 低频幅值
    """
    f = np.abs(fft(cmr_signal, axis=1))[:, 1:nbins+1]  # 跳 DC
    # 归一化每帧总能量
    return f / (f.sum(axis=1, keepdims=True) + 1e-10)

features = extract_features(cmr_normalized)
```

这样从 128 维时域信号压到 64 维频域特征，**用谱形而不是绝对幅值**区分传感器。

### 5.2 LDA 投影

```python
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.preprocessing import StandardScaler

feat_scaled = StandardScaler().fit_transform(features)
lda = LDA(n_components=min(9, len(np.unique(d['sensor_id'])) - 1))
Z = lda.fit_transform(feat_scaled, d['sensor_id'])  # (3967, 9)
# 标签是 sensor_id（B2-1~B2-10），不是 condition
```

## 6. 选最佳二维展示面

9 个 LDA 维度中枚举所有组合，选 silhouette 最高的：

```python
from itertools import combinations
from sklearn.metrics import silhouette_score

best_sil, best_dims = -1, (0, 1)
for d1, d2 in combinations(range(Z.shape[1]), 2):
    sil = silhouette_score(Z[:, [d1, d2]], d['sensor_id'])
    if sil > best_sil:
        best_sil, best_dims = sil, (d1, d2)
Z_2d = Z[:, best_dims]
```

## 7. 必出图表

### 7.1 主图：对比学习嵌入点云

参考样式见 `D:\Project\FPGA_transDATA\研究报告\codex对比学习结果\figures\contrastive_embedding_lda.png`

要求：
- 每个传感器一个颜色，10 种
- B2-1 的四条件中心用大点标记并用线连接🔴
- 每个传感器画 85% 包络圆（红色虚线圆，半径 = 85% 分位距离）
- 图例标注传感器编号
- 网格半透灰
- 标题写 silhouette 值
- 输出：`figures/embedding_lda.png`

### 7.2 辅助图 1：同/异传感器距离箱线图

参考 `contrastive_distance_boxplot.png`
- 左侧箱线 = 同传感器不同条件的 CMR 信号欧氏距离
- 右侧箱线 = 不同传感器之间的 CMR 信号欧氏距离
- 输出：`figures/distance_boxplot.png`

### 7.3 辅助图 2：质心相似度矩阵

参考 `contrastive_centroid_similarity.png`
- 10×10 矩阵，热图显示每对传感器的 NCUT CMR 平均信号之间的皮尔逊相关系数
- 对角线（自相似）= 1.0；颜色区分
- 输出：`figures/centroid_similarity.png`

## 8. 必出指标指标表

| 指标 | 含义 | 期望 |
|:---|:---|:---|
| silhouette | 嵌入轮廓系数 | > 0.80 |
| centroid_acc | 最近质心分类准确率 | ~1.0 |
| same_mean_distance | 同传感器不同条件样本间平均距离 | 尽量小 |
| different_mean_distance | 不同传感器样本间平均距离 | 尽量大 |
| distance_ratio | 异类/同类距离比 | > 10x |

## 9. 输出清单

放到本目录下的 `results/` 文件夹：

```
processed/results/
├── embedding_lda.png
├── distance_boxplot.png
├── centroid_similarity.png
└── summary.json  （全部指标）
```

## 10. 已知数据质量说明

以下传感器**不是错误**，是传感器自身物理特性（已验证 frmVar < 3，帧间稳定）：

| 传感器 | 条件 | 现象 |
|:---|:---|:---|
| B2-2 NTHP | 常温高压 | peak ~21979（基线偏高，正常传感器的 2x）|
| B2-6 NTNP | 常温常压 | peak ~22005（同上）|
| B2-10 HTNP | 高温常压 | peak ~21987（同上）|

**不要因为这 3 个条件的高基线而排除数据。**

## 11. 环境依赖

```bash
pip install numpy scipy scikit-learn matplotlib
```
