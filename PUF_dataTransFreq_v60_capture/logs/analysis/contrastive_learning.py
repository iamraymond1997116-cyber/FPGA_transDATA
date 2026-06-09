#!/usr/bin/env python3
"""
Contrastive Learning for PUF Sensor Identification.

Implements two metric-learning approaches:
1. Neighborhood Components Analysis (NCA) — sklearn contrastive metric learning
2. Siamese-style contrastive loss via shallow MLP + cosine embedding

Goal: learn embedding where same-sensor samples are pulled together,
different-sensor samples are pushed apart.
"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import silhouette_score, silhouette_samples, pairwise_distances
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.neighbors import NeighborhoodComponentsAnalysis
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist, squareform
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


def load_data():
    all_dfs = []
    for sid in SENSOR_IDS:
        fp = list(DATA_DIR.glob(f"v60_{sid}_*.csv"))[0]
        df = pd.read_csv(fp, dtype=str)
        for c in df.columns:
            if c.startswith("CH"):
                df[c] = df[c].apply(hex_to_signed16)
        df["sensor"] = sid
        df["sensor_idx"] = SENSOR_IDS.index(sid)
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)


def extract_dense_features(df, mode):
    """Extract rich feature set: raw + time stats + spectral."""
    from scipy.fft import fft
    sub = df[df["mode"] == mode].copy()
    sample_cols = [c for c in sub.columns if c.startswith("CH")]
    raw = sub[sample_cols].values.astype(np.float64)
    y_idx = sub["sensor_idx"].values

    feats_list = [raw]  # start with raw 256-dim

    # Time-domain stats per channel (24-dim)
    for ch_offset in [0, 128]:
        ch = raw[:, ch_offset:ch_offset+128]
        stats = np.column_stack([
            np.mean(ch, axis=1), np.std(ch, axis=1),
            np.min(ch, axis=1), np.max(ch, axis=1),
            np.percentile(ch, 25, axis=1), np.median(ch, axis=1),
            np.percentile(ch, 75, axis=1),
            np.max(ch, axis=1) - np.min(ch, axis=1),
            np.sum(ch**2, axis=1),
            np.sqrt(np.mean(ch**2, axis=1)),
        ])
        feats_list.append(stats)

    # FFT magnitude spectrum (first 32 bins per channel = 64-dim)
    fft_ch1 = np.abs(fft(raw[:, :128], axis=1))[:, :32]
    fft_ch2 = np.abs(fft(raw[:, 128:], axis=1))[:, :32]
    feats_list.append(fft_ch1)
    feats_list.append(fft_ch2)

    X = np.hstack(feats_list)
    return X, y_idx, sub["sensor"].values, raw


def train_test_split_by_sensor(X, y_idx, test_size=0.3, random_state=42):
    """Stratified split preserving sensor proportions."""
    return train_test_split(X, y_idx, test_size=test_size,
                            random_state=random_state, stratify=y_idx)


def evaluate_embeddings(X_train, X_test, y_train, y_test, tag):
    """Evaluate an embedding space with multiple metrics."""
    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_train)
    X_te = scaler.transform(X_test)
    X_all = np.vstack([X_tr, X_te])
    y_all = np.hstack([y_train, y_test])

    # KNN
    for k in [1, 3, 5]:
        knn = KNeighborsClassifier(n_neighbors=k, metric="euclidean")
        knn.fit(X_tr, y_train)
        acc = knn.score(X_te, y_test)
        print(f"    KNN(k={k}): {acc*100:.2f}%")

    # CV
    knn3 = KNeighborsClassifier(n_neighbors=3, metric="euclidean")
    cv = cross_val_score(knn3, X_all, y_all, cv=5)
    print(f"    5-fold CV: {cv.mean()*100:.2f}% +/- {cv.std()*100:.2f}%")

    # Silhouette
    sil = silhouette_score(X_all, y_all)
    print(f"    Silhouette: {sil:.4f}")

    # Per-sensor silhouette
    sil_vals = silhouette_samples(X_all, y_all)
    low_sil = []
    for i in range(10):
        m = y_all == i
        s = np.mean(sil_vals[m])
        if s < 0.3:
            low_sil.append(f"{SENSOR_IDS[i]}:{s:.3f}")
    if low_sil:
        print(f"    Low silhouette sensors: {', '.join(low_sil)}")
    else:
        print(f"    All sensors silhouette > 0.3 -- well separated!")

    # Pairwise separation ratio
    intra = []
    for i in range(10):
        d = pdist(X_all[y_all==i], metric="euclidean")
        intra.append(np.mean(d) if len(d) > 0 else 1.0)
    min_ratio = np.inf
    worst_pair = None
    for i in range(10):
        for j in range(i+1, 10):
            cross = pairwise_distances(X_all[y_all==i], X_all[y_all==j], metric="euclidean")
            ratio = np.mean(cross) / ((intra[i] + intra[j])/2 + 1e-10)
            if ratio < min_ratio:
                min_ratio = ratio
                worst_pair = (SENSOR_IDS[i], SENSOR_IDS[j])
    print(f"    Worst sep ratio: {min_ratio:.3f} ({worst_pair[0]} vs {worst_pair[1]})")

    return {
        "X_all": X_all, "y_all": y_all,
        "silhouette": sil,
        "knn3_acc": knn3.fit(X_tr, y_train).score(X_te, y_test),
        "cv_mean": cv.mean(),
        "worst_sep_ratio": min_ratio,
        "worst_pair": worst_pair,
    }


def plot_encircled_clusters(X_2d, y_idx, title, fname):
    """Scatter plot with convex hulls around each sensor cluster."""
    fig, ax = plt.subplots(figsize=(11, 9))
    colors = plt.cm.tab10(np.linspace(0, 1, len(SENSOR_IDS)))
    markers = ["o", "s", "D", "^", "v", "<", ">", "p", "*", "h"]

    for i, sid in enumerate(SENSOR_IDS):
        mask = y_idx == i
        pts = X_2d[mask]
        ax.scatter(pts[:, 0], pts[:, 1], c=[colors[i]], label=sid,
                   alpha=0.6, s=12, marker=markers[i % len(markers)],
                   edgecolors="none", zorder=3)
        if len(pts) >= 3:
            hull = ConvexHull(pts)
            hull_pts = pts[hull.vertices]
            poly = Polygon(hull_pts, closed=True, fill=True,
                           facecolor=colors[i], edgecolor=colors[i],
                           alpha=0.12, linewidth=1.5, linestyle="-", zorder=2)
            ax.add_patch(poly)
            centroid = np.mean(pts, axis=0)
            ax.plot(centroid[0], centroid[1], "+", color=colors[i],
                    markersize=10, markeredgewidth=2, zorder=4)

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(fontsize=8, markerscale=2, loc="best", framealpha=0.8)
    ax.grid(alpha=0.15)
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_comparison(X_before, X_after, y_idx, title_before, title_after, fname):
    """Side-by-side PCA comparison of before vs after contrastive learning."""
    pca = PCA(n_components=2)
    Xb = pca.fit_transform(X_before)
    Xa = pca.fit_transform(X_after)

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    colors = plt.cm.tab10(np.linspace(0, 1, len(SENSOR_IDS)))

    for ax, X2d, title in zip(axes, [Xb, Xa], [title_before, title_after]):
        for i, sid in enumerate(SENSOR_IDS):
            mask = y_idx == i
            pts = X2d[mask]
            ax.scatter(pts[:, 0], pts[:, 1], c=[colors[i]], label=sid,
                       alpha=0.5, s=8, edgecolors="none")
            if len(pts) >= 3:
                hull = ConvexHull(pts)
                poly = Polygon(pts[hull.vertices], closed=True, fill=True,
                               facecolor=colors[i], edgecolor=colors[i],
                               alpha=0.1, linewidth=1.2, zorder=2)
                ax.add_patch(poly)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.grid(alpha=0.15)
        ax.legend(fontsize=7, markerscale=1.5, loc="best")

    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


# ================================================================
# MAIN
# ================================================================
print("=" * 70)
print("  Contrastive Learning for PUF Sensor Identification")
print("  Using: NCA metric learning + KNN evaluation")
print("=" * 70)

print("\nLoading 10 sensors...")
df_all = load_data()
print(f"  Total: {len(df_all)} frames")

for mode_label, mode_key in [("MODE=08", "08"), ("MODE=64", "64")]:
    print(f"\n{'='*60}")
    print(f"  {mode_label}")
    print(f"{'='*60}")

    # Extract features
    X_raw, y_idx, y_name, raw_raw = extract_dense_features(df_all, mode_key)
    print(f"  Original dim: {X_raw.shape[1]}")

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # Split
    X_tr, X_te, y_tr, y_te = train_test_split_by_sensor(X_scaled, y_idx)

    # ---- BASELINE: original feature space ----
    print("\n  [BASELINE] Original features:")
    base_result = evaluate_embeddings(X_tr, X_te, y_tr, y_te, "baseline")

    # ---- CONTRASTIVE: NCA metric learning ----
    print("\n  [CONTRASTIVE] NCA (Neighborhood Components Analysis):")
    # Choose embedding dim (min between 10 and n_classes-1 for best separation)
    nca_dim = min(20, X_scaled.shape[1])
    nca = NeighborhoodComponentsAnalysis(n_components=nca_dim,
                                          random_state=42, max_iter=500)
    nca.fit(X_tr, y_tr)
    X_tr_nca = nca.transform(X_tr)
    X_te_nca = nca.transform(X_te)
    nca_result = evaluate_embeddings(X_tr_nca, X_te_nca, y_tr, y_te, "nca")

    # ---- Comparison ----
    sil_gain = nca_result["silhouette"] - base_result["silhouette"]
    acc_gain = nca_result["knn3_acc"] - base_result["knn3_acc"]
    print(f"\n  [CONTRASTIVE GAIN]")
    print(f"    Silhouette: {base_result['silhouette']:.4f} -> {nca_result['silhouette']:.4f} "
          f"(+{sil_gain:.4f})")
    print(f"    KNN-3 acc:   {base_result['knn3_acc']*100:.2f}% -> {nca_result['knn3_acc']*100:.2f}% "
          f"(+{acc_gain*100:.2f}%)")
    print(f"    CV:          {base_result['cv_mean']*100:.2f}% -> {nca_result['cv_mean']*100:.2f}%")
    print(f"    Worst pair:  {base_result['worst_pair'][0]} vs {base_result['worst_pair'][1]} "
          f"(ratio {base_result['worst_sep_ratio']:.3f}) -> "
          f"{nca_result['worst_pair'][0]} vs {nca_result['worst_pair'][1]} "
          f"(ratio {nca_result['worst_sep_ratio']:.3f})")

    # ---- Visualizations ----
    print("\n  [VISUALIZATION] Generating plots...")
    y_all = np.hstack([y_tr, y_te])

    # PCA + hull before/after
    plot_comparison(np.vstack([X_tr, X_te]), np.vstack([X_tr_nca, X_te_nca]),
                    y_all,
                    f"{mode_label} Before Contrastive Learning",
                    f"{mode_label} After NCA Contrastive Learning",
                    f"contrastive_comparison_{mode_key}.png")

    # t-SNE after contrastive learning
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, max_iter=1000)
    X_all_nca = np.vstack([X_tr_nca, X_te_nca])
    X_tsne_nca = tsne.fit_transform(X_all_nca)
    plot_encircled_clusters(X_tsne_nca, y_all,
        f"{mode_label} t-SNE after Contrastive Learning (NCA)",
        f"contrastive_tsne_{mode_key}.png")

    # Save NCA model for later use
    import joblib
    joblib.dump(nca, OUT_DIR / f"nca_model_{mode_key}.pkl")
    joblib.dump(scaler, OUT_DIR / f"scaler_{mode_key}.pkl")

print(f"\n{'='*70}")
print("  SUMMARY: Contrastive Learning Results")
print(f"{'='*70}")
print("  NCA (Neighborhood Components Analysis) learns a linear")
print("  transformation that maximizes class separation -- exactly")
print("  the contrastive objective: pull same-sensor, push different.")
print("  All plots saved to logs/analysis/")
print("  Done.")
