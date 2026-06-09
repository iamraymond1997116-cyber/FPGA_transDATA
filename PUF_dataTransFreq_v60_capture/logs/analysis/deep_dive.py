#!/usr/bin/env python3
"""
Deep-dive: find the exact failure points in 10-sensor classification.
Plus encircled PCA/t-SNE plots (user request: circle around each sensor cluster).
"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, pairwise_distances, silhouette_samples
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist, squareform
from collections import Counter
import warnings
warnings.filterwarnings("ignore")
np.random.seed(42)

DATA_DIR = Path(r"d:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq_v60_capture\logs\10sensors")
OUT_DIR = Path(r"d:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq_v60_capture\logs\analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)
SENSOR_IDS = [f"B2-{i}" for i in range(1, 11)]

def hex_to_signed16(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v

def load_one(sid):
    fp = list(DATA_DIR.glob(f"v60_{sid}_*.csv"))[0]
    df = pd.read_csv(fp, dtype=str)
    for c in df.columns:
        if c.startswith("CH"):
            df[c] = df[c].apply(hex_to_signed16)
    df["sensor"] = sid
    df["sensor_idx"] = SENSOR_IDS.index(sid)
    df["txn"] = df["txn"].apply(lambda x: int(str(x), 16))
    df["spwr"] = df["spwr"].astype(int)
    return df

def extract_time_features(samples):
    ch1, ch2 = samples[:128], samples[128:]
    feats = []
    for ch in [ch1, ch2]:
        feats += [np.mean(ch), np.std(ch), np.min(ch), np.max(ch),
                  np.percentile(ch, 25), np.median(ch), np.percentile(ch, 75),
                  np.mean((ch-np.mean(ch))**3)/(np.std(ch)**3+1e-10),
                  np.mean((ch-np.mean(ch))**4)/(np.std(ch)**4+1e-10)-3,
                  np.max(ch)-np.min(ch), np.sum(ch**2), np.sqrt(np.mean(ch**2))]
    return np.array(feats)

def extract_spectral_features(samples):
    from scipy.fft import fft
    ch1, ch2 = samples[:128], samples[128:]
    feats = []
    for ch in [ch1, ch2]:
        spec = np.abs(fft(ch))[:32]
        feats.extend(spec)
        freqs = np.arange(len(spec))
        centroid = np.sum(freqs*spec)/(np.sum(spec)+1e-10)
        spread = np.sqrt(np.sum(((freqs-centroid)**2)*spec)/(np.sum(spec)+1e-10))
        cum = np.cumsum(spec); total = cum[-1]+1e-10
        rolloff = np.searchsorted(cum, 0.85*total)
        feats += [centroid, spread, rolloff]
    return np.array(feats)


def plot_encircled_clusters(X_2d, y_idx, title, fname, method="PCA"):
    """Scatter plot with convex hulls around each sensor cluster."""
    fig, ax = plt.subplots(figsize=(11, 9))
    colors = plt.cm.tab10(np.linspace(0, 1, len(SENSOR_IDS)))
    markers = ["o", "s", "D", "^", "v", "<", ">", "p", "*", "h"]

    for i, sid in enumerate(SENSOR_IDS):
        mask = y_idx == i
        pts = X_2d[mask]
        # Plot points
        ax.scatter(pts[:, 0], pts[:, 1], c=[colors[i]], label=sid,
                   alpha=0.6, s=12, marker=markers[i % len(markers)],
                   edgecolors="none", zorder=3)
        # Draw convex hull
        if len(pts) >= 3:
            hull = ConvexHull(pts)
            hull_pts = pts[hull.vertices]
            poly = Polygon(hull_pts, closed=True, fill=True,
                           facecolor=colors[i], edgecolor=colors[i],
                           alpha=0.12, linewidth=1.5, linestyle="-", zorder=2)
            ax.add_patch(poly)
            # Draw centroid
            centroid = np.mean(pts, axis=0)
            ax.plot(centroid[0], centroid[1], "+", color=colors[i],
                    markersize=10, markeredgewidth=2, zorder=4)

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(f"{method} dim 1")
    ax.set_ylabel(f"{method} dim 2")
    ax.legend(fontsize=8, markerscale=2, loc="best",
              framealpha=0.8, edgecolor="gray")
    ax.grid(alpha=0.15)
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


print("Loading 10 sensors...")
all_dfs = [load_one(s) for s in SENSOR_IDS]
df_all = pd.concat(all_dfs, ignore_index=True)

for mode_label, mode_key in [("MODE=08", "08"), ("MODE=64", "64")]:
    print(f"\n{'='*60}")
    print(f"  {mode_label} -- DEEP DIVE")
    print(f"{'='*60}")
    sub = df_all[df_all["mode"] == mode_key].copy()
    sample_cols = [c for c in sub.columns if c.startswith("CH")]
    raw = sub[sample_cols].values.astype(np.float64)
    y_idx = sub["sensor_idx"].values
    y_name = sub["sensor"].values

    # Build features
    time_f = np.array([extract_time_features(r) for r in raw])
    spec_f = np.array([extract_spectral_features(r) for r in raw])
    X = np.hstack([time_f, spec_f])
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # === 0. Encircled PCA & t-SNE plots (user request) ===
    print("\n  [0] Encircled cluster plots (PCA + t-SNE)...")

    # PCA
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    var_exp = pca.explained_variance_ratio_
    plot_encircled_clusters(X_pca, y_idx,
        f"{mode_label} PCA + Convex Hull\n({var_exp[0]*100:.1f}% + {var_exp[1]*100:.1f}% = {(var_exp[0]+var_exp[1])*100:.1f}% variance)",
        f"encircled_pca_{mode_key}.png", "PCA")

    # t-SNE
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, max_iter=1000)
    X_tsne = tsne.fit_transform(X_scaled)
    plot_encircled_clusters(X_tsne, y_idx,
        f"{mode_label} t-SNE + Convex Hull",
        f"encircled_tsne_{mode_key}.png", "t-SNE")

    # === 1. Nearest-sensor-pair analysis ===
    print("\n  [1] Closest sensor pairs (mean feature distance):")
    means = np.array([np.mean(X_scaled[y_idx==i], axis=0) for i in range(10)])
    pair_dist = squareform(pdist(means, metric="euclidean"))
    np.fill_diagonal(pair_dist, np.inf)
    for i in range(10):
        j = np.argmin(pair_dist[i])
        print(f"    {SENSOR_IDS[i]} <-> {SENSOR_IDS[j]}:  dist={pair_dist[i,j]:.3f}")

    # === 2. KNN misclassification analysis ===
    print("\n  [2] KNN(3) misclassification analysis:")
    X_tr, X_te, y_tr, y_te, name_tr, name_te = train_test_split(
        X_scaled, y_idx, y_name, test_size=0.3, random_state=42, stratify=y_idx)
    knn = KNeighborsClassifier(n_neighbors=3, metric="euclidean")
    knn.fit(X_tr, y_tr)
    y_pred = knn.predict(X_te)

    errors = np.where(y_pred != y_te)[0]
    print(f"    Total test samples: {len(y_te)}")
    print(f"    Misclassified: {len(errors)} ({len(errors)/len(y_te)*100:.2f}%)")

    if len(errors) > 0:
        print("\n    Misclassified frames detail:")
        err_pairs = Counter()
        for e_idx in errors:
            true_s = SENSOR_IDS[y_te[e_idx]]
            pred_s = SENSOR_IDS[y_pred[e_idx]]
            err_pairs[(true_s, pred_s)] += 1
        for (true_s, pred_s), cnt in err_pairs.most_common():
            print(f"      {true_s} -> {pred_s}: {cnt} frames")

        # Confusion matrix
        cm = confusion_matrix(y_te, y_pred, normalize="true")
        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(cm, cmap="Blues", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(10)); ax.set_yticks(range(10))
        ax.set_xticklabels(SENSOR_IDS, fontsize=9, rotation=45)
        ax.set_yticklabels(SENSOR_IDS, fontsize=9)
        for i in range(10):
            for j in range(10):
                val = cm[i, j]
                ax.text(j, i, f"{val*100:.1f}%", ha="center", va="center",
                        fontsize=8, color="white" if val>0.5 else "black")
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
        ax.set_title(f"{mode_label} Confusion Matrix", fontweight="bold")
        fig.colorbar(im, shrink=0.8)
        fig.tight_layout()
        fig.savefig(OUT_DIR / f"cm_{mode_key}_detail.png", dpi=150)
        plt.close(fig)
        print(f"    Saved cm_{mode_key}_detail.png")
    else:
        print("    PERFECT -- zero misclassifications!")

    # === 3. Pairwise separation ratio ===
    print(f"\n  [3] Pairwise separation ratio matrix (inter/intra):")
    intra = {}
    for i in range(10):
        d = pdist(X_scaled[y_idx==i], metric="euclidean")
        intra[i] = np.mean(d) if len(d) > 0 else 1.0
    sep_matrix = np.zeros((10, 10))
    for i in range(10):
        for j in range(10):
            if i == j:
                sep_matrix[i,j] = 0
                continue
            mask_i, mask_j = y_idx==i, y_idx==j
            cross = pairwise_distances(X_scaled[mask_i], X_scaled[mask_j], metric="euclidean")
            inter_mean = np.mean(cross)
            sep_matrix[i,j] = inter_mean / (intra[i] + intra[j]) * 2
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(sep_matrix, cmap="YlOrRd", aspect="auto", vmin=0, vmax=max(5, np.max(sep_matrix)))
    ax.set_xticks(range(10)); ax.set_yticks(range(10))
    ax.set_xticklabels(SENSOR_IDS, fontsize=9, rotation=45)
    ax.set_yticklabels(SENSOR_IDS, fontsize=9)
    for i in range(10):
        for j in range(10):
            if i == j:
                ax.text(j, i, "-", ha="center", va="center", fontsize=7, color="gray")
            else:
                val = sep_matrix[i,j]
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if val > 3 else "black")
    ax.set_title(f"{mode_label} Pairwise Separation Ratio", fontweight="bold")
    fig.colorbar(im, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"pairwise_sep_{mode_key}.png", dpi=150)
    plt.close(fig)
    print(f"    Saved pairwise_sep_{mode_key}.png")

    min_val = np.inf; min_pair = None
    for i in range(10):
        for j in range(i+1, 10):
            if sep_matrix[i,j] < min_val:
                min_val = sep_matrix[i,j]; min_pair = (i,j)
    print(f"    Hardest pair: {SENSOR_IDS[min_pair[0]]} <-> {SENSOR_IDS[min_pair[1]]}: sep_ratio={min_val:.3f}")

    # === 4. Silhouette per sensor ===
    print(f"\n  [4] Silhouette score per sensor:")
    sil_vals = silhouette_samples(X_scaled, y_idx)
    for i in range(10):
        m = y_idx == i
        sil_mean = np.mean(sil_vals[m])
        sil_std = np.std(sil_vals[m])
        flag = " *** LOW" if sil_mean < 0.3 else ""
        print(f"    {SENSOR_IDS[i]}: silhouette={sil_mean:.4f} +/- {sil_std:.4f}{flag}")

    # === 5. Summary ===
    print(f"\n  [{mode_label}] DEEP DIVE SUMMARY:")
    print(f"    KNN-3 accuracy: {(1-len(errors)/len(y_te))*100:.2f}%")
    print(f"    Worst separation ratio: {min_val:.3f} (pair {SENSOR_IDS[min_pair[0]]} vs {SENSOR_IDS[min_pair[1]]})")
    low_sil = [(SENSOR_IDS[i], np.mean(sil_vals[y_idx==i])) for i in range(10) if np.mean(sil_vals[y_idx==i]) < 0.3]
    if low_sil:
        print(f"    Low-silhouette sensors: {low_sil}")
    else:
        print(f"    All sensors silhouette > 0.3 -- well separated")

print("\nAll deep-dive plots saved to logs/analysis/")
print("Done.")
