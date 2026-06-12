"""
文件级LDA训练 + 400帧投影 + 参考风格画图
NCUT黄金模式：CMR→FFT→条件归一化→LDA
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import fft
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import pairwise_distances, silhouette_score
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "logs" / "0611_4state_10sensers"
FIG_DIR = BASE / "logs" / "analysis_4state" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
SENSOR_ORDER = [f"B2-{i}" for i in range(1, 11)]
COND_MAP = {"NTNP": "normal", "NTHP": "highPressure", "HTNP": "highTemp", "HTHP": "highTempHighPressure"}

def h2s(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

def extract_features(ch1, ch2):
    """CMR→FFT 64-bin，单帧特征"""
    cmr = np.array(ch1, dtype=np.float64) - np.array(ch2, dtype=np.float64)
    f = np.abs(fft(cmr))[:64]
    return f / (f.sum() + 1e-10)

# ===== 文件级数据（训练LDA）=====
print("Building file-level features...")
X_file, y_file, c_file = [], [], []
for fp in sorted(DATA_DIR.glob("v60_*.csv")):
    parts = fp.stem.split("_")
    tag, cond = parts[1], parts[2]
    if cond not in COND_MAP: continue
    import csv
    feats = []
    with fp.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["mode"] != "NCUT": continue
            ch1 = [h2s(row[f"CH1_{i:03d}"]) for i in range(128)]
            ch2 = [h2s(row[f"CH2_{i:03d}"]) for i in range(128)]
            feats.append(extract_features(ch1, ch2))
    if feats:
        avg = np.mean(feats, axis=0)
        X_file.append(avg)
        y_file.append(tag)
        c_file.append(COND_MAP[cond])

Xf = np.array(X_file); yf = np.array(y_file); cf = np.array(c_file)
print(f"  File-level: {len(Xf)} samples")

# 条件归一化
Xfn = Xf.copy()
for c in np.unique(cf):
    m = cf == c
    Xfn[m] -= Xf[m].mean(axis=0)
Xfs = StandardScaler().fit_transform(np.hstack([Xf, Xfn]))

# 训练LDA（文件级）
lda = LinearDiscriminantAnalysis(n_components=len(SENSOR_ORDER) - 1)
lda.fit(Xfs, yf)

# ===== 帧级数据（投影）=====
print("Projecting all frames...")
X_all, y_all, c_all = [], [], []
for fp in sorted(DATA_DIR.glob("v60_*.csv")):
    parts = fp.stem.split("_")
    tag, cond = parts[1], parts[2]
    if cond not in COND_MAP: continue
    import csv
    with fp.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["mode"] != "NCUT": continue
            ch1 = [h2s(row[f"CH1_{i:03d}"]) for i in range(128)]
            ch2 = [h2s(row[f"CH2_{i:03d}"]) for i in range(128)]
            X_all.append(extract_features(ch1, ch2))
            y_all.append(tag)
            c_all.append(COND_MAP[cond])

Xa = np.array(X_all); ya = np.array(y_all); ca = np.array(c_all)
print(f"  Frame-level: {len(Xa)} frames")

# 用文件级的条件均值做归一化
Xan = Xa.copy()
for c in np.unique(cf):
    mask = ca == c
    Xan[mask] -= Xf[cf == c].mean(axis=0)
Xas = StandardScaler().fit_transform(np.hstack([Xa, Xan]))

# 通过文件级LDA投影
Z = lda.transform(Xas)

# 用LDA全空间（9维）选最佳2D
best_pair, best_score, best_z = (0, 1), -np.inf, Z[:, :2]
for i in range(Z.shape[1]):
    for j in range(i + 1, Z.shape[1]):
        c = StandardScaler().fit_transform(Z[:, [i, j]])
        s = silhouette_score(c, ya, metric="euclidean")
        if s > best_score:
            best_score, best_pair, best_z = float(s), (i, j), c

# 质心准确率
centroids = {sid: best_z[ya == sid].mean(axis=0) for sid in SENSOR_ORDER}
preds = [min(centroids.items(), key=lambda x: np.linalg.norm(row - x[1]))[0] for row in best_z]
acc = float(np.mean(np.array(preds) == ya))

# 距离
d = pairwise_distances(best_z, metric="euclidean")
same, diff = [], []
for i in range(len(ya)):
    for j in range(i + 1, len(ya)):
        (same if ya[i] == ya[j] else diff).append(d[i, j])
ratio = float(np.mean(diff) / (np.mean(same) + 1e-12))

print(f"\n  Silhouette={best_score:.4f} Acc={acc:.4f} Ratio={ratio:.2f}x  Points={len(best_z)}")

# ===== 画图（参考风格）=====
colors = {"B2-1": "#d7191c", "B2-2": "#2c7bb6", "B2-3": "#1a9641", "B2-4": "#fdae61",
          "B2-5": "#984ea3", "B2-6": "#8c510a", "B2-7": "#f781bf", "B2-8": "#4d4d4d",
          "B2-9": "#a6d96a", "B2-10": "#00a6a6"}
markers = {"normal": "o", "highPressure": "s", "highTemp": "^", "highTempHighPressure": "D"}

plt.figure(figsize=(11, 8), dpi=220)
ax = plt.gca()

# 85%圈 + 质心
for sid in SENSOR_ORDER:
    mask = ya == sid
    center = best_z[mask].mean(axis=0)
    radius = np.percentile(np.linalg.norm(best_z[mask] - center, axis=1), 85)
    ax.add_patch(plt.Circle(center, radius, color=colors[sid], fill=False, lw=1.4, alpha=0.35))
    plt.scatter(center[0], center[1], marker="x", s=90, c=colors[sid], linewidths=2.2, zorder=4)

# 点
for sid in SENSOR_ORDER:
    for condition in sorted(set(ca[ya == sid])):
        mask = (ya == sid) & (ca == condition)
        if not np.any(mask): continue
        plt.scatter(best_z[mask, 0], best_z[mask, 1],
                    s=35 if sid != "B2-1" else 45,
                    c=colors[sid], marker=markers.get(condition, "o"),
                    alpha=0.5 if sid != "B2-1" else 0.7,
                    edgecolors="white", linewidths=0.3,
                    zorder=3 if sid == "B2-1" else 2)

# B2-1条件质心 + 连线
b21_centers = []
for c in ["normal", "highPressure", "highTemp", "highTempHighPressure"]:
    mask = (ya == "B2-1") & (ca == c)
    if np.any(mask):
        center = best_z[mask].mean(axis=0)
        b21_centers.append(center)
        plt.scatter(center[0], center[1], marker=markers[c],
                    s=180, c="#d7191c", edgecolors="black", linewidths=1.2, zorder=5)

if len(b21_centers) > 1:
    arr = np.vstack(b21_centers)
    plt.plot(arr[:, 0], arr[:, 1], color="#d7191c", lw=2.2, alpha=0.75, zorder=4)

# 图例
h1 = [mlines.Line2D([], [], color=colors[s], marker="o", linestyle="None", markersize=7, label=s) for s in SENSOR_ORDER]
h2 = [mlines.Line2D([], [], color="black", marker=m, linestyle="None", markersize=8, label=l)
      for l, m in [("normal", "o"), ("highPressure", "s"), ("highTemp", "^"), ("highTempHighPressure", "D")]]
leg1 = plt.legend(handles=h1, title="Sensor", loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)
plt.legend(handles=h2, title="B2-1 condition", loc="upper left", bbox_to_anchor=(1.02, 0.42), frameon=False)
ax.add_artist(leg1)

ax.set_title(f"NCUT: {len(best_z)} frames — same sensor pulled, different pushed", fontsize=13)
ax.set_xlabel(f"LDA dimension {int(best_pair[0]) + 1}")
ax.set_ylabel(f"LDA dimension {int(best_pair[1]) + 1}")
ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.65)
ax.text(0.02, 0.02, f"silhouette={best_score:.3f}  centroid_acc={acc:.3f}",
        transform=ax.transAxes, fontsize=10,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.92})
plt.tight_layout()
plt.savefig(FIG_DIR / "final_dense_ncut.png", bbox_inches="tight")
plt.close()
print(f"\nSaved final_dense_ncut.png")
print(f"DONE: {len(best_z)} points, {len(np.unique(ya))} classes")
