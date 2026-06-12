from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import pairwise_distances, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

RESULT_DIR = Path(__file__).resolve().parent
ROOT = RESULT_DIR.parents[1]
DATA_DIR = ROOT / "PUF_dataTransFreq_v60_capture" / "logs" / "0611_4state_10sensers"
FIG_DIR = RESULT_DIR / "figures"

SENSOR_ORDER = [f"B2-{i}" for i in range(1, 11)]
CONDITIONS_MAP = {"NTNP": "normal", "NTHP": "highPressure", "HTNP": "highTemp", "HTHP": "highTempHighPressure"}
COND_ORDER = ["NTNP", "NTHP", "HTNP", "HTHP"]


def hex_to_signed16(v):
    v = int(str(v), 16)
    return v - 0x10000 if v >= 0x8000 else v


def read_adc_frames(csv_path: Path, mode: str = "NCUT") -> dict[str, list[np.ndarray]]:
    """
    Read ADC frames for a specific mode.
    Returns dict with keys 'CH1' and 'CH2', each containing list of 128-point arrays.
    """
    import csv
    buckets: dict[str, list[np.ndarray]] = {"CH1": [], "CH2": []}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["mode"] != mode:
                continue
            ch1 = np.array([hex_to_signed16(row[f"CH1_{i:03d}"]) for i in range(128)], dtype=np.float64)
            ch2 = np.array([hex_to_signed16(row[f"CH2_{i:03d}"]) for i in range(128)], dtype=np.float64)
            buckets["CH1"].append(ch1)
            buckets["CH2"].append(ch2)
    return buckets


def spectrum(arr: np.ndarray) -> np.ndarray:
    """128-bin FFT magnitude spectrum (skip DC, keep 1..128)."""
    from scipy.fft import fft
    f = np.abs(fft(arr))
    return f  # 128 bins including DC


def normalize_rows(arr: np.ndarray) -> np.ndarray:
    return arr / (arr.sum(axis=1, keepdims=True) + 1e-12)


def frame_feature(ch1: np.ndarray, ch2: np.ndarray) -> np.ndarray:
    """
    Extract feature vector from a single frame, following the reference pattern.
    Features:
    - CH1 normalized spectrum (128)
    - CH2 normalized spectrum (128)
    - CH1 spectrum std (across the frame - here single frame so use 0)
    - CH2 spectrum std
    - Low-freq energy ratios (5 bands)
    - CH1/CH2 differential
    - Time-domain stats
    """
    s1 = spectrum(ch1)       # 128 bins (including DC)
    s2 = spectrum(ch2)

    n1 = normalize_rows(s1.reshape(1, -1)).ravel()  # (128,)
    n2 = normalize_rows(s2.reshape(1, -1)).ravel()

    features: list[float] = list(n1) + list(n2)

    # Low-freq energy ratios from normalized spectra
    for band in [(1, 8), (8, 16), (16, 32), (32, 64), (64, 128)]:
        lo, hi = band
        features.append(float(n1[lo:hi].sum()))
        features.append(float(n2[lo:hi].sum()))

    # CH1/CH2 differential of normalized spectra
    diff = n1 - n2
    features.extend(diff.tolist())
    features.extend([
        float(np.linalg.norm(diff)),
        float(np.mean(np.abs(diff[1:16]))),
    ])

    # Time-domain features
    cmr = ch1 - ch2
    features.extend([
        float(ch1.mean()), float(ch1.std()), float(ch1.max() - ch1.min()),
        float(ch2.mean()), float(ch2.std()), float(ch2.max() - ch2.min()),
        float(cmr.mean()), float(cmr.std()),
        float(np.sqrt(np.mean(ch1**2))), float(np.sqrt(np.mean(ch2**2))),
    ])

    return np.array(features, dtype=np.float64)


def load_dataset(mode: str = "NCUT") -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Load data: each FRAME is one sample."""
    features = []
    sensor_ids = []
    conditions = []
    files = []

    for fp in sorted(DATA_DIR.glob("v60_*.csv")):
        parts = fp.stem.split("_")
        sensor_tag, cond = parts[1], parts[2]
        if cond not in CONDITIONS_MAP:
            continue

        buckets = read_adc_frames(fp, mode=mode)
        if not buckets["CH1"]:
            continue

        for i in range(len(buckets["CH1"])):
            features.append(frame_feature(buckets["CH1"][i], buckets["CH2"][i]))
            sensor_ids.append(sensor_tag)
            conditions.append(CONDITIONS_MAP[cond])
            files.append(str(fp))

    return np.vstack(features), np.array(sensor_ids), np.array(conditions), files


def nearest_centroid_accuracy(z: np.ndarray, labels: np.ndarray) -> float:
    centroids = {sid: z[labels == sid].mean(axis=0) for sid in SENSOR_ORDER}
    preds = []
    for row in z:
        preds.append(min(centroids.items(), key=lambda item: np.linalg.norm(row - item[1]))[0])
    return float(np.mean(np.array(preds) == labels))


def best_lda_plane(x: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    lda = LinearDiscriminantAnalysis(n_components=len(SENSOR_ORDER) - 1)
    full_z = lda.fit_transform(x, labels)

    best_pair = (0, 1)
    best_score = -np.inf
    best_z = full_z[:, :2]
    for i in range(full_z.shape[1]):
        for j in range(i + 1, full_z.shape[1]):
            candidate = StandardScaler().fit_transform(full_z[:, [i, j]])
            score = silhouette_score(candidate, labels, metric="euclidean")
            if score > best_score:
                best_score = float(score)
                best_pair = (i, j)
                best_z = candidate
    return best_z, best_pair


def distance_summary(z: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    same = []
    different = []
    distances = pairwise_distances(z, metric="euclidean")
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            if labels[i] == labels[j]:
                same.append(distances[i, j])
            else:
                different.append(distances[i, j])

    same_arr = np.array(same)
    different_arr = np.array(different)
    return {
        "same_mean_distance": float(same_arr.mean()),
        "different_mean_distance": float(different_arr.mean()),
        "distance_ratio": float(different_arr.mean() / (same_arr.mean() + 1e-12)),
    }


def plot_embedding(z: np.ndarray, labels: np.ndarray, conditions: np.ndarray, summary: dict[str, float]) -> None:
    colors = {
        "B2-1": "#d7191c",
        "B2-2": "#2c7bb6",
        "B2-3": "#1a9641",
        "B2-4": "#fdae61",
        "B2-5": "#984ea3",
        "B2-6": "#8c510a",
        "B2-7": "#f781bf",
        "B2-8": "#4d4d4d",
        "B2-9": "#a6d96a",
        "B2-10": "#00a6a6",
    }
    markers = {"normal": "o", "highPressure": "s", "highTemp": "^", "highTempHighPressure": "D"}

    plt.figure(figsize=(11, 8), dpi=220)
    ax = plt.gca()

    # Circles and centroids
    for sid in SENSOR_ORDER:
        mask = labels == sid
        center = z[mask].mean(axis=0)
        radius = np.percentile(np.linalg.norm(z[mask] - center, axis=1), 85)
        ax.add_patch(plt.Circle(center, radius, color=colors[sid], fill=False, lw=1.4, alpha=0.38))
        plt.scatter(center[0], center[1], marker="x", s=90, c=colors[sid], linewidths=2.2, zorder=4)

    # Points
    for sid in SENSOR_ORDER:
        sid_mask = labels == sid
        for condition in sorted(set(conditions[sid_mask])):
            mask = sid_mask & (conditions == condition)
            if not np.any(mask):
                continue
            plt.scatter(
                z[mask, 0], z[mask, 1],
                s=52 if sid != "B2-1" else 70,
                c=colors[sid],
                marker=markers.get(condition, "o"),
                alpha=0.64 if sid != "B2-1" else 0.9,
                edgecolors="white",
                linewidths=0.45,
                zorder=3 if sid == "B2-1" else 2,
            )

    # B2-1 condition centroids (large markers + connecting line)
    b21_centers = []
    for condition in ["normal", "highPressure", "highTemp", "highTempHighPressure"]:
        mask = (labels == "B2-1") & (conditions == condition)
        if np.any(mask):
            center = z[mask].mean(axis=0)
            b21_centers.append(center)
            plt.scatter(
                center[0], center[1],
                marker=markers[condition],
                s=165, c="#d7191c",
                edgecolors="black", linewidths=1.2, zorder=5,
            )
    if len(b21_centers) > 1:
        plt.plot(
            np.vstack(b21_centers)[:, 0],
            np.vstack(b21_centers)[:, 1],
            color="#d7191c", lw=2.2, alpha=0.75, zorder=4,
        )

    # Legends
    sensor_handles = [
        mlines.Line2D([], [], color=colors[sid], marker="o", linestyle="None", markersize=7, label=sid)
        for sid in SENSOR_ORDER
    ]
    condition_handles = [
        mlines.Line2D([], [], color="black", marker=marker, linestyle="None", markersize=8, label=label)
        for label, marker in [("normal", "o"), ("highPressure", "s"), ("highTemp", "^"), ("highTempHighPressure", "D")]
    ]
    leg1 = plt.legend(handles=sensor_handles, title="Sensor", loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)
    plt.legend(handles=condition_handles, title="B2-1 condition", loc="upper left", bbox_to_anchor=(1.02, 0.42), frameon=False)
    ax.add_artist(leg1)

    ax.set_title("NCUT: CMR→FFT→LDA — same sensor pulled together, different pushed apart", fontsize=13)
    ax.set_xlabel(f"LDA dimension {int(summary['lda_dim_x']) + 1}")
    ax.set_ylabel(f"LDA dimension {int(summary['lda_dim_y']) + 1}")
    ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.65)
    ax.text(
        0.02, 0.02,
        f"silhouette={summary['silhouette']:.3f}  centroid_acc={summary['centroid_acc']:.3f}",
        transform=ax.transAxes, fontsize=10,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.92},
    )
    plt.tight_layout()
    plt.savefig(FIG_DIR / "our_embedding_ncut.png", bbox_inches="tight")
    plt.close()


def plot_distance_boxplot(z: np.ndarray, labels: np.ndarray) -> None:
    same = []
    different = []
    distances = pairwise_distances(z, metric="euclidean")
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            if labels[i] == labels[j]:
                same.append(distances[i, j])
            else:
                different.append(distances[i, j])

    plt.figure(figsize=(8.5, 5.2), dpi=220)
    plt.boxplot([np.array(same), np.array(different)], tick_labels=["Same sensor", "Different sensors"], showfliers=False)
    plt.ylabel("Euclidean distance in embedding")
    plt.title("Distance after contrastive-style projection")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "our_distance_boxplot.png", bbox_inches="tight")
    plt.close()


def plot_centroid_similarity(z: np.ndarray, labels: np.ndarray) -> None:
    centroids = np.vstack([z[labels == sid].mean(axis=0) for sid in SENSOR_ORDER])
    sim = cosine_similarity(centroids)
    plt.figure(figsize=(8.5, 7), dpi=220)
    image = plt.imshow(sim, cmap="viridis", vmin=-1, vmax=1)
    plt.xticks(range(len(SENSOR_ORDER)), SENSOR_ORDER, rotation=45, ha="right")
    plt.yticks(range(len(SENSOR_ORDER)), SENSOR_ORDER)
    plt.colorbar(image, label="Centroid cosine similarity")
    plt.title("Sensor centroid similarity after projection")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "our_centroid_similarity.png", bbox_inches="tight")
    plt.close()


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # Use NCUT golden mode
    x, labels, conditions, files = load_dataset(mode="NCUT")
    print(f"Loaded {len(files)} frames, {len(np.unique(labels))} sensors, {len(np.unique(conditions))} conditions")
    print(f"Feature dim: {x.shape[1]}")

    x = StandardScaler().fit_transform(x)
    z, lda_pair = best_lda_plane(x, labels)

    summary: dict[str, float | int] = {
        "n_files": int(len(files)),
        "n_features": int(x.shape[1]),
        "lda_dim_x": float(lda_pair[0]),
        "lda_dim_y": float(lda_pair[1]),
        "silhouette": float(silhouette_score(z, labels, metric="euclidean")),
        "centroid_acc": nearest_centroid_accuracy(z, labels),
    }
    summary.update(distance_summary(z, labels))

    print(f"Silhouette={summary['silhouette']:.4f} Acc={summary['centroid_acc']:.4f} Ratio={summary['distance_ratio']:.2f}x")
    print(f"LDA dims: {lda_pair}")

    plot_embedding(z, labels, conditions, summary)
    plot_distance_boxplot(z, labels)
    plot_centroid_similarity(z, labels)

    (RESULT_DIR / "our_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
