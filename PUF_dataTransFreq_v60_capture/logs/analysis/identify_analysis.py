#!/usr/bin/env python3
"""
V6.0 10-sensor PUF fingerprint identification analysis.

Approach:
1. Load all 10 sensors (B2-1 .. B2-10), each with 200 frames (100 MODE=08 + 100 MODE=64)
2. Separate by mode, treat each 256-sample frame as a fingerprint vector
3. Time-domain + FFT-spectrum feature extraction
4. Intra/Inter-sensor distance analysis (contrastive-learning principle:
   intra-class << inter-class)
5. Dimensionality reduction (PCA, t-SNE) for visual separation
6. KNN classification to quantify separability
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.metrics import confusion_matrix, classification_report, silhouette_score
from scipy.fft import fft
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.stats import describe
import warnings, json, sys

warnings.filterwarnings("ignore")
np.random.seed(42)

# ============================================================
# Config
# ============================================================
DATA_DIR = Path(r"d:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq_v60_capture\logs\10sensors")
OUT_DIR = Path(r"d:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq_v60_capture\logs\analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SENSOR_IDS = [f"B2-{i}" for i in range(1, 11)]
N_SAMPLES = 128  # samples per channel
N_CH1 = 128
N_CH2 = 128
N_TOTAL = 256  # ch1 + ch2 combined


def hex_to_signed16(val_hex: str) -> int:
    """Convert 4-char hex string to signed 16-bit integer."""
    v = int(val_hex, 16)
    return v - 0x10000 if v >= 0x8000 else v


def load_sensor_data(sensor_id: str) -> pd.DataFrame:
    """Load a single sensor's CSV, parse hex values to signed int."""
    files = list(DATA_DIR.glob(f"v60_{sensor_id}_*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV found for {sensor_id}")
    fpath = files[0]  # take newest/only

    # Force ALL columns as str to preserve hex formatting
    df = pd.read_csv(fpath, dtype=str)

    # Convert hex sample columns to signed 16-bit int
    sample_cols = [c for c in df.columns if c.startswith("CH1_") or c.startswith("CH2_")]
    for col in sample_cols:
        df[col] = df[col].apply(hex_to_signed16)

    # Reconstruct numeric columns
    df["txn"] = df["txn"].apply(lambda x: int(str(x), 16))
    df["spwr"] = df["spwr"].astype(int)

    # Add sensor label
    df["sensor"] = sensor_id
    df["sensor_idx"] = SENSOR_IDS.index(sensor_id)
    return df


def load_all_sensors():
    """Load all 10 sensors, return concatenated DataFrame."""
    all_dfs = []
    for sid in SENSOR_IDS:
        df = load_sensor_data(sid)
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)


# ============================================================
# Feature extraction helpers
# ============================================================

def extract_time_features(samples: np.ndarray) -> np.ndarray:
    """
    Extract statistical features from a 256-sample vector.
    Returns 24 features: 12 per channel (mean, std, min, max, p25, p50, p75,
    skew, kurtosis, range, energy, rms)
    """
    ch1 = samples[:128]
    ch2 = samples[128:]
    feats = []
    for ch in [ch1, ch2]:
        feats.extend([
            np.mean(ch), np.std(ch), np.min(ch), np.max(ch),
            np.percentile(ch, 25), np.percentile(ch, 50), np.percentile(ch, 75),
            np.mean((ch - np.mean(ch))**3) / (np.std(ch)**3 + 1e-10),
            np.mean((ch - np.mean(ch))**4) / (np.std(ch)**4 + 1e-10) - 3,
            np.max(ch) - np.min(ch),
            np.sum(ch**2),
            np.sqrt(np.mean(ch**2)),
        ])
    return np.array(feats)


def extract_spectral_features(samples: np.ndarray, n_fft: int = 64) -> np.ndarray:
    """
    FFT-based spectral features: magnitude spectrum (first n_fft/2 bins)
    for each channel, plus spectral centroid, spread, and roll-off.
    Returns ~68 features (2 * n_fft/2 + 6).
    """
    ch1 = samples[:128]
    ch2 = samples[128:]
    feats = []
    for ch in [ch1, ch2]:
        spectrum = np.abs(fft(ch))[:n_fft // 2]
        feats.extend(spectrum)
        # Spectral centroid
        freqs = np.arange(len(spectrum))
        centroid = np.sum(freqs * spectrum) / (np.sum(spectrum) + 1e-10)
        feats.append(centroid)
        # Spectral spread
        spread = np.sqrt(np.sum(((freqs - centroid)**2) * spectrum) / (np.sum(spectrum) + 1e-10))
        feats.append(spread)
        # Spectral roll-off (frequency below which 85% energy)
        cum_energy = np.cumsum(spectrum)
        total_energy = cum_energy[-1] + 1e-10
        rolloff = np.searchsorted(cum_energy, 0.85 * total_energy)
        feats.append(rolloff)
    return np.array(feats)


def build_feature_matrix(df: pd.DataFrame, mode: str, use_fft: bool = True):
    """
    Build feature matrix from a DataFrame filtered by mode.
    Each row = one frame. Returns (X, y_sensor_idx, y_sensor_name).
    """
    sub = df[df["mode"] == mode].copy()
    sample_cols = [c for c in sub.columns if c.startswith("CH1_") or c.startswith("CH2_")]
    raw = sub[sample_cols].values.astype(np.float64)
    y_idx = sub["sensor_idx"].values
    y_name = sub["sensor"].values

    # Time-domain features
    time_feats = np.array([extract_time_features(row) for row in raw])
    # Spectral features
    if use_fft:
        spec_feats = np.array([extract_spectral_features(row) for row in raw])
        X = np.hstack([time_feats, spec_feats])
    else:
        X = time_feats

    return X, y_idx, y_name, raw


# ============================================================
# Visualization helpers
# ============================================================

def plot_distance_matrix(dist_matrix, labels, title, fname, cmap="viridis"):
    """Plot a distance matrix (N x N where N = number of sensors)."""
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(dist_matrix, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.tick_params(axis="x", rotation=45)
    for i in range(len(labels)):
        for j in range(len(labels)):
            val = dist_matrix[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if val > dist_matrix.mean() else "black")
    ax.set_title(title, fontsize=12, fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_tsne(X, y_idx, y_names, title, fname):
    """t-SNE visualization colored by sensor."""
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, max_iter=1000)
    X_2d = tsne.fit_transform(X)
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.tab10(np.linspace(0, 1, len(SENSOR_IDS)))
    for i, sid in enumerate(SENSOR_IDS):
        mask = y_idx == i
        ax.scatter(X_2d[mask, 0], X_2d[mask, 1], c=[colors[i]], label=sid,
                   alpha=0.6, s=15, edgecolors="none")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, markerscale=2, loc="best")
    ax.set_xlabel("t-SNE dim 1")
    ax.set_ylabel("t-SNE dim 2")
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_pca(X, y_idx, title, fname):
    """PCA visualization."""
    pca = PCA(n_components=2)
    X_2d = pca.fit_transform(X)
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = plt.cm.tab10(np.linspace(0, 1, len(SENSOR_IDS)))
    for i, sid in enumerate(SENSOR_IDS):
        mask = y_idx == i
        ax.scatter(X_2d[mask, 0], X_2d[mask, 1], c=[colors[i]], label=sid,
                   alpha=0.5, s=15, edgecolors="none")
    var_explained = pca.explained_variance_ratio_
    ax.set_xlabel(f"PC1 ({var_explained[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({var_explained[1]*100:.1f}%)")
    ax.set_title(f"{title}\n(explained variance: {var_explained[0]*100:.1f}% + {var_explained[1]*100:.1f}% = {(var_explained[0]+var_explained[1])*100:.1f}%)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, markerscale=2, loc="best")
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_confusion_matrix(y_true, y_pred, labels, title, fname):
    """Plot normalized confusion matrix."""
    cm = confusion_matrix(y_true, y_pred, normalize="true")
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9, rotation=45)
    ax.set_yticklabels(labels, fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            val = cm[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if val > 0.5 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title, fontsize=12, fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_dendrogram(Z, labels, title, fname):
    """Hierarchical clustering dendrogram."""
    fig, ax = plt.subplots(figsize=(10, 6))
    dn = dendrogram(Z, labels=labels, ax=ax, leaf_font_size=9)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Distance")
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_inter_intra_bar(intra_mean, inter_mean, intra_std, inter_std, labels, title, fname):
    """Bar chart comparing intra-class vs inter-class distances per sensor."""
    x = np.arange(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width/2, intra_mean, width, yerr=intra_std, label="Intra-sensor",
           capsize=3, color="steelblue", alpha=0.8)
    ax.bar(x + width/2, inter_mean, width, yerr=inter_std, label="Inter-sensor",
           capsize=3, color="coral", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, rotation=45)
    ax.set_ylabel("Mean Euclidean Distance")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


# ============================================================
# Main analysis per mode
# ============================================================

def analyze_mode(df_all, mode, mode_label):
    """Full analysis pipeline for one mode (08 or 64)."""
    print(f"\n{'='*70}")
    print(f"  ANALYSIS: MODE={mode_label}")
    print(f"{'='*70}")

    # Build feature matrix
    X, y_idx, y_name, raw = build_feature_matrix(df_all, mode)
    print(f"  Frames: {X.shape[0]}, Features: {X.shape[1]}")
    print(f"  Sensors: {len(np.unique(y_idx))}")

    # ---- 1. Raw data distance matrix (sensor-level) ----
    print("\n  [1/8] Sensor-level distance matrix (raw data)...")
    sensor_means = []
    for i in range(len(SENSOR_IDS)):
        mask = y_idx == i
        sensor_means.append(np.mean(raw[mask], axis=0))
    sensor_means = np.array(sensor_means)
    dist_raw = squareform(pdist(sensor_means, metric="euclidean"))
    plot_distance_matrix(dist_raw, SENSOR_IDS,
                         f"MODE={mode_label} Sensor Mean Euclidean Distance (raw)",
                         f"dist_raw_{mode}.png")

    # ---- 2. Intra vs inter distance analysis ----
    print("  [2/8] Intra vs Inter-sensor distance analysis...")
    intra_dists = {sid: [] for sid in SENSOR_IDS}
    inter_dists = {sid: [] for sid in SENSOR_IDS}
    for i, sid in enumerate(SENSOR_IDS):
        mask_i = y_idx == i
        samples_i = raw[mask_i]
        # Intra: pairwise within same sensor
        if len(samples_i) > 1:
            intra = pdist(samples_i, metric="euclidean")
            intra_dists[sid].extend(intra.tolist())
        # Inter: to all other sensors
        for j in range(len(SENSOR_IDS)):
            if i == j:
                continue
            mask_j = y_idx == j
            samples_j = raw[mask_j]
            cross = pdist(np.vstack([samples_i, samples_j]), metric="euclidean")
            inter = cross[:len(samples_i) * len(samples_j)]
            inter_dists[sid].extend(inter.tolist())

    intra_means = np.array([np.mean(intra_dists[sid]) for sid in SENSOR_IDS])
    intra_stds = np.array([np.std(intra_dists[sid]) for sid in SENSOR_IDS])
    inter_means = np.array([np.mean(inter_dists[sid]) for sid in SENSOR_IDS])
    inter_stds = np.array([np.std(inter_dists[sid]) for sid in SENSOR_IDS])

    plot_inter_intra_bar(intra_means, inter_means, intra_stds, inter_stds,
                         SENSOR_IDS, f"MODE={mode_label} Intra vs Inter-sensor Distance",
                         f"intra_inter_{mode}.png")

    # Global ratio
    global_intra = np.concatenate(list(intra_dists.values()))
    global_inter = np.concatenate(list(inter_dists.values()))
    sep_ratio = np.mean(global_inter) / (np.mean(global_intra) + 1e-10)
    print(f"    Global intra mean: {np.mean(global_intra):.1f}")
    print(f"    Global inter mean: {np.mean(global_inter):.1f}")
    print(f"    Separation ratio (inter/intra): {sep_ratio:.3f}")

    # ---- 3. Feature-distance ----
    print("  [3/8] Sensor-level distance matrix (feature space)...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    sensor_feat_means = []
    for i in range(len(SENSOR_IDS)):
        mask = y_idx == i
        sensor_feat_means.append(np.mean(X_scaled[mask], axis=0))
    sensor_feat_means = np.array(sensor_feat_means)
    dist_feat = squareform(pdist(sensor_feat_means, metric="euclidean"))
    plot_distance_matrix(dist_feat, SENSOR_IDS,
                         f"MODE={mode_label} Sensor Mean Euclidean Distance (features)",
                         f"dist_feat_{mode}.png", cmap="plasma")

    # Feat-space intra/inter
    feat_intra_dists = [[] for _ in SENSOR_IDS]
    feat_inter_dists = [[] for _ in SENSOR_IDS]
    for i in range(len(SENSOR_IDS)):
        mask_i = y_idx == i
        feat_i = X_scaled[mask_i]
        if len(feat_i) > 1:
            feat_intra_dists[i].extend(pdist(feat_i, metric="euclidean").tolist())
        for j in range(len(SENSOR_IDS)):
            if i == j:
                continue
            mask_j = y_idx == j
            feat_j = X_scaled[mask_j]
            cross = pdist(np.vstack([feat_i, feat_j]), metric="euclidean")
            feat_inter_dists[i].extend(cross[:len(feat_i)*len(feat_j)].tolist())
    f_intra_all = np.concatenate(feat_intra_dists) if any(feat_intra_dists) else np.array([0])
    f_inter_all = np.concatenate(feat_inter_dists) if any(feat_inter_dists) else np.array([0])
    feat_sep = np.mean(f_inter_all) / (np.mean(f_intra_all) + 1e-10)
    print(f"    Feature-space intra: {np.mean(f_intra_all):.3f}")
    print(f"    Feature-space inter: {np.mean(f_inter_all):.3f}")
    print(f"    Feature separation ratio: {feat_sep:.3f}")

    # ---- 4. PCA ----
    print("  [4/8] PCA visualization...")
    plot_pca(X_scaled, y_idx, f"MODE={mode_label} PCA",
             f"pca_{mode}.png")

    # ---- 5. t-SNE ----
    print("  [5/8] t-SNE visualization...")
    plot_tsne(X_scaled, y_idx, y_name, f"MODE={mode_label} t-SNE",
              f"tsne_{mode}.png")

    # ---- 6. KNN classification ----
    print("  [6/8] KNN classification...")
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_idx, test_size=0.3, random_state=42, stratify=y_idx
    )
    for k in [1, 3, 5, 7]:
        knn = KNeighborsClassifier(n_neighbors=k, metric="euclidean")
        knn.fit(X_train, y_train)
        acc = knn.score(X_test, y_test)
        print(f"    KNN(k={k}) accuracy: {acc*100:.2f}%")
    best_knn = KNeighborsClassifier(n_neighbors=3, metric="euclidean")
    best_knn.fit(X_train, y_train)
    y_pred = best_knn.predict(X_test)
    plot_confusion_matrix(y_test, y_pred, SENSOR_IDS,
                          f"MODE={mode_label} KNN(k=3) Confusion Matrix",
                          f"cm_knn_{mode}.png")

    # Silhouette score
    sil = silhouette_score(X_scaled, y_idx)
    print(f"    Silhouette score: {sil:.4f}")

    # Cross-validation
    cv_knn = KNeighborsClassifier(n_neighbors=3, metric="euclidean")
    cv_scores = cross_val_score(cv_knn, X_scaled, y_idx, cv=5)
    print(f"    5-fold CV accuracy: {cv_scores.mean()*100:.2f}% ± {cv_scores.std()*100:.2f}%")

    # ---- 7. Hierarchical clustering ----
    print("  [7/8] Hierarchical clustering...")
    Z = linkage(sensor_feat_means, method="ward")
    plot_dendrogram(Z, SENSOR_IDS, f"MODE={mode_label} Hierarchical Clustering (feature space)",
                    f"dendrogram_{mode}.png")

    # ---- 8. Silhouette per sensor ----
    print("  [8/8] Per-sensor analysis...")
    sensor_results = {}
    for i, sid in enumerate(SENSOR_IDS):
        mask = y_idx == i
        samples = raw[mask]
        ch1_mean = np.mean(samples[:, :128], axis=0)
        ch2_mean = np.mean(samples[:, 128:], axis=0)
        sensor_results[sid] = {
            "ch1_mean": ch1_mean.tolist(),
            "ch2_mean": ch2_mean.tolist(),
            "intra_dist_mean": float(np.mean(intra_dists[sid])),
            "intra_dist_std": float(np.std(intra_dists[sid])),
            "inter_dist_mean": float(np.mean(inter_dists[sid])),
            "inter_dist_std": float(np.std(inter_dists[sid])),
            "separation_ratio": float(np.mean(inter_dists[sid]) / (np.mean(intra_dists[sid]) + 1e-10)),
        }

    results = {
        "mode": mode_label,
        "n_frames": int(X.shape[0]),
        "n_sensors": len(SENSOR_IDS),
        "n_features": int(X.shape[1]),
        "global_intra_dist_mean": float(np.mean(global_intra)),
        "global_inter_dist_mean": float(np.mean(global_inter)),
        "separation_ratio_raw": float(sep_ratio),
        "feat_intra_dist_mean": float(np.mean(f_intra_all)),
        "feat_inter_dist_mean": float(np.mean(f_inter_all)),
        "feat_separation_ratio": float(feat_sep),
        "silhouette_score": float(sil),
        "knn3_accuracy": float(best_knn.score(X_test, y_test)),
        "cv_mean": float(cv_scores.mean()),
        "cv_std": float(cv_scores.std()),
        "per_sensor": sensor_results,
    }
    return results, X_scaled, y_idx, raw


# ============================================================
# Cross-mode analysis
# ============================================================

def cross_mode_analysis(results_08, results_64):
    """Compare MODE=08 vs MODE=64 results."""
    print(f"\n{'='*70}")
    print("  CROSS-MODE COMPARISON")
    print(f"{'='*70}")

    metrics = ["separation_ratio_raw", "feat_separation_ratio",
               "silhouette_score", "knn3_accuracy"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes = axes.ravel()
    for idx, metric in enumerate(metrics):
        vals = [results_08[metric], results_64[metric]]
        axes[idx].bar(["MODE=08", "MODE=64"], vals, color=["steelblue", "coral"], alpha=0.8)
        axes[idx].set_title(metric.replace("_", " ").title(), fontsize=10, fontweight="bold")
        axes[idx].grid(axis="y", alpha=0.3)
        for i, v in enumerate(vals):
            axes[idx].text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=9)
    fig.suptitle("MODE=08 vs MODE=64 Performance Comparison", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cross_mode_comparison.png", dpi=150)
    plt.close(fig)
    print("  Saved cross_mode_comparison.png")

    # Per-sensor separation ratio comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(SENSOR_IDS))
    sep08 = [results_08["per_sensor"][s]["separation_ratio"] for s in SENSOR_IDS]
    sep64 = [results_64["per_sensor"][s]["separation_ratio"] for s in SENSOR_IDS]
    ax.plot(x, sep08, "o-", label="MODE=08", color="steelblue", linewidth=2)
    ax.plot(x, sep64, "s-", label="MODE=64", color="coral", linewidth=2)
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5, label="Sep=1 boundary")
    ax.set_xticks(x)
    ax.set_xticklabels(SENSOR_IDS, fontsize=9, rotation=45)
    ax.set_ylabel("Separation Ratio (inter/intra)")
    ax.set_title("Per-Sensor Separation Ratio: MODE=08 vs MODE=64", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cross_mode_separation.png", dpi=150)
    plt.close(fig)
    print("  Saved cross_mode_separation.png")

    # Combined feature space: does mode itself separate?
    comparison = {
        "08": results_08,
        "64": results_64,
    }
    return comparison


# ============================================================
# Summary report
# ============================================================

def generate_report(results_08, results_64, comparison):
    """Generate a markdown analysis report."""
    lines = []
    lines.append("# V6.0 10-Sensor PUF Fingerprint Identification Report")
    lines.append("")
    lines.append(f"Generated from {len(SENSOR_IDS)} sensors (B2-1 ~ B2-10), "
                 f"each with 100 MODE=08 + 100 MODE=64 frames.")
    lines.append("")

    for mode_label, res in [("08", results_08), ("64", results_64)]:
        lines.append(f"---")
        lines.append(f"## MODE={mode_label} Analysis")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Frames analyzed | {res['n_frames']} |")
        lines.append(f"| Features extracted | {res['n_features']} |")
        lines.append(f"| Raw-data intra-sensor distance (mean±std) | {res['global_intra_dist_mean']:.1f} ± ??? |")
        lines.append(f"| Raw-data inter-sensor distance (mean) | {res['global_inter_dist_mean']:.1f} |")
        lines.append(f"| **Raw separation ratio (inter/intra)** | **{res['separation_ratio_raw']:.3f}** |")
        lines.append(f"| Feature-space intra distance | {res['feat_intra_dist_mean']:.3f} |")
        lines.append(f"| Feature-space inter distance | {res['feat_inter_dist_mean']:.3f} |")
        lines.append(f"| **Feature separation ratio** | **{res['feat_separation_ratio']:.3f}** |")
        lines.append(f"| **Silhouette score** | **{res['silhouette_score']:.4f}** |")
        lines.append(f"| KNN-3 accuracy | {res['knn3_accuracy']*100:.2f}% |")
        lines.append(f"| 5-fold CV accuracy | {res['cv_mean']*100:.2f}% ± {res['cv_std']*100:.2f}% |")
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"## Cross-Mode Comparison")
    lines.append(f"")
    lines.append(f"| Metric | MODE=08 | MODE=64 | Better |")
    lines.append(f"|--------|---------|---------|--------|")
    for metric in ["separation_ratio_raw", "feat_separation_ratio",
                   "silhouette_score", "knn3_accuracy", "cv_mean"]:
        v08 = results_08[metric]
        v64 = results_64[metric]
        better = "MODE=08" if v08 > v64 else "MODE=64" if v64 > v08 else "Same"
        unit = "%" if "accuracy" in metric or "cv" in metric else ""
        lines.append(f"| {metric.replace('_', ' ').title()} | {v08:.4f}{unit} | {v64:.4f}{unit} | {better} |")

    lines.append(f"")
    lines.append(f"## Per-Sensor Detail")
    lines.append(f"")
    lines.append(f"| Sensor | MODE=08 Intra Mean | MODE=08 Inter Mean | MODE=08 Sep Ratio | "
                 f"MODE=64 Intra Mean | MODE=64 Inter Mean | MODE=64 Sep Ratio |")
    lines.append(f"|--------|-------------------|--------------------|-------------------|"
                 f"--------------------|--------------------|-------------------|")
    for sid in SENSOR_IDS:
        r08 = results_08["per_sensor"][sid]
        r64 = results_64["per_sensor"][sid]
        lines.append(f"| {sid} | {r08['intra_dist_mean']:.1f} | {r08['inter_dist_mean']:.1f} | "
                     f"{r08['separation_ratio']:.3f} | {r64['intra_dist_mean']:.1f} | "
                     f"{r64['inter_dist_mean']:.1f} | {r64['separation_ratio']:.3f} |")

    lines.append(f"")
    lines.append(f"## Conclusion")
    best_mode = "MODE=08" if results_08["feat_separation_ratio"] > results_64["feat_separation_ratio"] else "MODE=64"
    lines.append(f"- **Best performing mode**: {best_mode}")
    lines.append(f"- **Min separation ratio**: {min(results_08['feat_separation_ratio'], results_64['feat_separation_ratio']):.3f}")
    lines.append(f"- **Max KNN accuracy**: {max(results_08['knn3_accuracy'], results_64['knn3_accuracy'])*100:.2f}%")
    lines.append(f"- Silhouette score > 0.5 indicates well-separated clusters.")
    lines.append(f"- Separation ratio >> 1.0 means inter-sensor distance dominates intra-sensor variation.")

    report = "\n".join(lines)
    report_path = OUT_DIR / "identification_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved: {report_path}")
    return report


# ============================================================
# Entry point
# ============================================================

def main():
    print("=" * 70)
    print("  V6.0 10-Sensor PUF Fingerprint Identification Analysis")
    print("  Approach: Contrastive-learning-style distance maximization")
    print("=" * 70)

    # 1. Load data
    print("\n  Loading 10 sensors...")
    df_all = load_all_sensors()
    print(f"  Total frames: {len(df_all)}")
    print(f"  Columns: {len(df_all.columns)}")
    print(f"  Sensors found: {df_all['sensor'].unique()}")

    # 2. Analyze MODE=08 first
    results_08, X08, y08, raw08 = analyze_mode(df_all, "08", "08")

    # 3. Analyze MODE=64
    results_64, X64, y64, raw64 = analyze_mode(df_all, "64", "64")

    # 4. Cross-mode comparison
    comparison = cross_mode_analysis(results_08, results_64)

    # 5. Generate report
    report = generate_report(results_08, results_64, comparison)

    # 6. Save numerical results as JSON
    json_data = {
        "mode08": {k: v for k, v in results_08.items() if k != "per_sensor"},
        "mode64": {k: v for k, v in results_64.items() if k != "per_sensor"},
        "cross_mode": {
            "best_mode": "08" if results_08["feat_separation_ratio"] > results_64["feat_separation_ratio"] else "64",
        },
        "per_sensor_08": {s: results_08["per_sensor"][s] for s in SENSOR_IDS},
        "per_sensor_64": {s: results_64["per_sensor"][s] for s in SENSOR_IDS},
    }
    json_path = OUT_DIR / "results_numeric.json"
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)
    print(f"Numerical results: {json_path}")

    # 7 Print final summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  MODE=08: separation_ratio={results_08['separation_ratio_raw']:.3f} "
          f"feat_ratio={results_08['feat_separation_ratio']:.3f} "
          f"silhouette={results_08['silhouette_score']:.4f} "
          f"KNN={results_08['knn3_accuracy']*100:.1f}%")
    print(f"  MODE=64: separation_ratio={results_64['separation_ratio_raw']:.3f} "
          f"feat_ratio={results_64['feat_separation_ratio']:.3f} "
          f"silhouette={results_64['silhouette_score']:.4f} "
          f"KNN={results_64['knn3_accuracy']*100:.1f}%")
    print(f"  Output directory: {OUT_DIR}")
    print("  DONE.")


if __name__ == "__main__":
    main()
