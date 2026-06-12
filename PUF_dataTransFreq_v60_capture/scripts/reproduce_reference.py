"""
文件级 CMR→FFT + 条件归一化 + 参考代码画图风格
NCUT是黄金模式
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
from sklearn.metrics.pairwise import cosine_similarity
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

def load_file_features(mode="NCUT"):
    """每CSV=1样本: CMR→FFT, 10帧平均, 条件归一化"""
    raw_feats, norm_feats, sensor_ids, conditions = [], [], [], []
    for fp in sorted(DATA_DIR.glob("v60_*.csv")):
        parts = fp.stem.split("_")
        tag, cond = parts[1], parts[2]
        if cond not in COND_MAP:
            continue
        import csv
        frames_ch1, frames_ch2 = [], []
        with fp.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if row["mode"] != mode:
                    continue
                ch1 = np.array([h2s(row[f"CH1_{i:03d}"]) for i in range(128)], dtype=np.float64)
                ch2 = np.array([h2s(row[f"CH2_{i:03d}"]) for i in range(128)], dtype=np.float64)
                frames_ch1.append(ch1)
                frames_ch2.append(ch2)

        if not frames_ch1:
            continue

        # 每帧CMR→FFT，然后平均
        feats = []
        for i in range(len(frames_ch1)):
            cmr = frames_ch1[i] - frames_ch2[i]
            f_mag = np.abs(fft(cmr))[:64]
            f_mag = f_mag / (f_mag.sum() + 1e-10)
            feats.append(f_mag)
        avg_feat = np.mean(feats, axis=0)

        raw_feats.append(avg_feat)
        sensor_ids.append(tag)
        conditions.append(COND_MAP[cond])

    raw = np.array(raw_feats)
    sensors = np.array(sensor_ids)
    conds = np.array(conditions)

    # 条件归一化
    norm = raw.copy()
    for c in np.unique(conds):
        m = conds == c
        if m.sum() > 0:
            norm[m] -= raw[m].mean(axis=0)

    # 堆叠原始+归一化特征
    X = np.hstack([raw, norm])
    return X, sensors, conds


def nearest_centroid_accuracy(z, labels):
    centroids = {sid: z[labels == sid].mean(axis=0) for sid in SENSOR_ORDER}
    preds = [min(centroids.items(), key=lambda x: np.linalg.norm(row - x[1]))[0] for row in z]
    return float(np.mean(np.array(preds) == labels))


def best_lda_plane(x, labels):
    lda = LinearDiscriminantAnalysis(n_components=len(SENSOR_ORDER) - 1)
    full_z = lda.fit_transform(x, labels)
    best_pair, best_score, best_z = (0, 1), -np.inf, full_z[:, :2]
    for i in range(full_z.shape[1]):
        for j in range(i + 1, full_z.shape[1]):
            c = StandardScaler().fit_transform(full_z[:, [i, j]])
            s = silhouette_score(c, labels, metric="euclidean")
            if s > best_score:
                best_score, best_pair, best_z = float(s), (i, j), c
    return best_z, best_pair


def distance_summary(z, labels):
    d = pairwise_distances(z, metric="euclidean")
    same, diff = [], []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            (same if labels[i] == labels[j] else diff).append(d[i, j])
    return {"same_mean_distance": float(np.mean(same)), "different_mean_distance": float(np.mean(diff)),
            "distance_ratio": float(np.mean(diff) / (np.mean(same) + 1e-12))}


def plot_embedding(z, labels, conditions, summary, tag):
    colors = {"B2-1": "#d7191c", "B2-2": "#2c7bb6", "B2-3": "#1a9641", "B2-4": "#fdae61",
              "B2-5": "#984ea3", "B2-6": "#8c510a", "B2-7": "#f781bf", "B2-8": "#4d4d4d",
              "B2-9": "#a6d96a", "B2-10": "#00a6a6"}
    markers = {"normal": "o", "highPressure": "s", "highTemp": "^", "highTempHighPressure": "D"}

    plt.figure(figsize=(11, 8), dpi=220)
    ax = plt.gca()

    for sid in SENSOR_ORDER:
        mask = labels == sid
        center = z[mask].mean(axis=0)
        radius = np.percentile(np.linalg.norm(z[mask] - center, axis=1), 85)
        ax.add_patch(plt.Circle(center, radius, color=colors[sid], fill=False, lw=1.4, alpha=0.38))
        plt.scatter(center[0], center[1], marker="x", s=90, c=colors[sid], linewidths=2.2, zorder=4)

    for sid in SENSOR_ORDER:
        sid_mask = labels == sid
        for condition in sorted(set(conditions[sid_mask])):
            mask = sid_mask & (conditions == condition)
            if not np.any(mask): continue
            plt.scatter(z[mask, 0], z[mask, 1], s=80, c=colors[sid], alpha=0.85,
                        marker=markers.get(condition, "o"),
                        edgecolors="white", linewidths=0.45, zorder=3)

    b21_centers = []
    for c in ["normal", "highPressure", "highTemp", "highTempHighPressure"]:
        mask = (labels == "B2-1") & (conditions == c)
        if np.any(mask):
            center = z[mask].mean(axis=0)
            b21_centers.append(center)
            plt.scatter(center[0], center[1], marker=markers[c],
                        s=200, c="#d7191c", edgecolors="black", linewidths=1.5, zorder=5)

    if len(b21_centers) > 1:
        arr = np.vstack(b21_centers)
        plt.plot(arr[:, 0], arr[:, 1], color="#d7191c", lw=2.2, alpha=0.75, zorder=4)

    h1 = [mlines.Line2D([], [], color=colors[s], marker="o", linestyle="None", markersize=7, label=s) for s in SENSOR_ORDER]
    h2 = [mlines.Line2D([], [], color="black", marker=m, linestyle="None", markersize=8, label=l)
          for l, m in [("normal", "o"), ("highPressure", "s"), ("highTemp", "^"), ("highTempHighPressure", "D")]]
    leg1 = plt.legend(handles=h1, title="Sensor", loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)
    plt.legend(handles=h2, title="B2-1 condition", loc="upper left", bbox_to_anchor=(1.02, 0.42), frameon=False)
    ax.add_artist(leg1)

    ax.set_title(f"{tag}: same sensor pulled, different pushed", fontsize=13)
    ax.set_xlabel(f"LDA dimension {int(summary['lda_dim_x']) + 1}")
    ax.set_ylabel(f"LDA dimension {int(summary['lda_dim_y']) + 1}")
    ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.65)
    ax.text(0.02, 0.02, f"silhouette={summary['silhouette']:.3f}  centroid_acc={summary['centroid_acc']:.3f}",
            transform=ax.transAxes, fontsize=10,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.92})
    plt.tight_layout()
    plt.savefig(FIG_DIR / f"final_{tag.lower()}.png", bbox_inches="tight")
    plt.close()


def run(mode, tag):
    print(f"\n{tag}...")
    x, labels, conditions = load_file_features(mode)
    print(f"  {len(labels)} samples, {x.shape[1]} features")
    x = StandardScaler().fit_transform(x)
    z, pair = best_lda_plane(x, labels)
    s = {"n_files": len(labels), "n_features": x.shape[1],
         "lda_dim_x": float(pair[0]), "lda_dim_y": float(pair[1]),
         "silhouette": float(silhouette_score(z, labels, metric="euclidean")),
         "centroid_acc": nearest_centroid_accuracy(z, labels)}
    s.update(distance_summary(z, labels))
    print(f"  Sil={s['silhouette']:.4f} Acc={s['centroid_acc']:.4f} Ratio={s['distance_ratio']:.2f}x")
    plot_embedding(z, labels, conditions, s, tag)
    return s

def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for mode, tag in [("NCUT", "NCUT"), ("PCUT", "PCUT"), ("FULL", "FULL")]:
        results[tag] = run(mode, tag)

    print(f"\n{'='*50}")
    for t, r in results.items():
        print(f"  {t}: Sil={r['silhouette']:.4f} Acc={r['centroid_acc']:.4f} Ratio={r['distance_ratio']:.2f}x")

    (BASE / "logs" / "analysis_4state" / "final_metrics.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
