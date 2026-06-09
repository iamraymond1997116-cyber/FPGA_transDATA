from __future__ import annotations

import csv
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
LOG_ROOT = ROOT / "PUF_dataTransFreq" / "logs"
FIG_DIR = RESULT_DIR / "figures"

LINE_TYPES = ["SPECTRUM_CH1", "SPECTRUM_CH2", "OFF_SPECTRUM_CH1", "OFF_SPECTRUM_CH2"]
SENSOR_ORDER = [f"B2-{i}" for i in range(1, 11)]


def read_spectrum_rows(csv_path: Path) -> dict[str, list[np.ndarray]]:
    buckets: dict[str, list[np.ndarray]] = {line_type: [] for line_type in LINE_TYPES}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            line_type = row["line_type"]
            if line_type not in buckets:
                continue
            vec = np.array([float(row[f"bin_{i}"]) for i in range(128)], dtype=np.float64)
            buckets[line_type].append(vec)
    return buckets


def normalize_rows(arr: np.ndarray) -> np.ndarray:
    return arr / (arr.sum(axis=1, keepdims=True) + 1e-12)


def file_feature(csv_path: Path) -> np.ndarray:
    buckets = read_spectrum_rows(csv_path)
    features: list[float] = []

    for line_type in LINE_TYPES:
        arr = np.vstack(buckets[line_type])
        arr_norm = normalize_rows(arr)
        mean_shape = arr_norm.mean(axis=0)
        std_shape = arr_norm.std(axis=0)
        mean_abs = arr.mean(axis=0)

        features.extend(mean_shape.tolist())
        features.extend(std_shape.tolist())
        features.extend((mean_abs / (mean_abs.sum() + 1e-12)).tolist())
        features.extend(
            [
                float(arr_norm[:, :8].sum(axis=1).mean()),
                float(arr_norm[:, 8:16].sum(axis=1).mean()),
                float(arr_norm[:, 16:32].sum(axis=1).mean()),
                float(arr_norm[:, 32:64].sum(axis=1).mean()),
                float(arr_norm[:, 64:128].sum(axis=1).mean()),
                float(arr_norm[:, :16].std()),
                float(arr_norm[:, 16:64].std()),
                float(arr_norm[:, 64:128].std()),
            ]
        )

    on_ch1 = normalize_rows(np.vstack(buckets["SPECTRUM_CH1"])).mean(axis=0)
    off_ch1 = normalize_rows(np.vstack(buckets["OFF_SPECTRUM_CH1"])).mean(axis=0)
    on_ch2 = normalize_rows(np.vstack(buckets["SPECTRUM_CH2"])).mean(axis=0)

    diff_on_off = on_ch1 - off_ch1
    diff_ch = on_ch1 - on_ch2
    features.extend(diff_on_off.tolist())
    features.extend(diff_ch.tolist())
    features.extend(
        [
            float(np.linalg.norm(diff_on_off)),
            float(np.linalg.norm(diff_ch)),
            float(np.mean(np.abs(diff_on_off[:16]))),
            float(np.mean(np.abs(diff_ch[:16]))),
        ]
    )
    return np.array(features, dtype=np.float64)


def dataset_dirs() -> dict[str, Path]:
    dirs: dict[str, Path] = {
        "B2-1_normal": LOG_ROOT / "256pt_4ch_B2-1",
        "B2-1_0526": LOG_ROOT / "256pt_4ch_B2-1_0526",
        "B2-1_highPressure": LOG_ROOT / "256pt_4ch_B2-1_highPressure",
        "B2-1_highTemp": LOG_ROOT / "256pt_4ch_B2-1_highTemp",
    }
    for i in range(2, 11):
        dirs[f"B2-{i}_normal"] = LOG_ROOT / f"256pt_4ch_B2-{i}"
    return dirs


def load_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    features = []
    sensor_ids = []
    conditions = []
    files = []

    for label, directory in dataset_dirs().items():
        csv_files = sorted(directory.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {directory}")
        for csv_path in csv_files:
            features.append(file_feature(csv_path))
            sensor_ids.append(label.split("_")[0])
            conditions.append("normal" if label.endswith("_normal") else label.split("_", 1)[1])
            files.append(str(csv_path))

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
    markers = {"normal": "o", "0526": "s", "highPressure": "^", "highTemp": "D"}

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
            plt.scatter(
                z[mask, 0],
                z[mask, 1],
                s=52 if sid != "B2-1" else 70,
                c=colors[sid],
                marker=markers.get(condition, "o"),
                alpha=0.64 if sid != "B2-1" else 0.9,
                edgecolors="white",
                linewidths=0.45,
                zorder=3 if sid == "B2-1" else 2,
            )

    b21_centers = []
    for condition in ["normal", "0526", "highPressure", "highTemp"]:
        mask = (labels == "B2-1") & (conditions == condition)
        if np.any(mask):
            center = z[mask].mean(axis=0)
            b21_centers.append(center)
            plt.scatter(
                center[0],
                center[1],
                marker=markers[condition],
                s=165,
                c="#d7191c",
                edgecolors="black",
                linewidths=1.2,
                zorder=5,
            )
    if len(b21_centers) > 1:
        b21_centers_arr = np.vstack(b21_centers)
        plt.plot(b21_centers_arr[:, 0], b21_centers_arr[:, 1], color="#d7191c", lw=2.2, alpha=0.75, zorder=4)

    sensor_handles = [
        mlines.Line2D([], [], color=colors[sid], marker="o", linestyle="None", markersize=7, label=sid)
        for sid in SENSOR_ORDER
    ]
    condition_handles = [
        mlines.Line2D([], [], color="black", marker=marker, linestyle="None", markersize=8, label=label)
        for label, marker in markers.items()
    ]
    leg1 = plt.legend(handles=sensor_handles, title="Sensor", loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)
    plt.legend(handles=condition_handles, title="B2-1 condition", loc="upper left", bbox_to_anchor=(1.02, 0.42), frameon=False)
    ax.add_artist(leg1)

    ax.set_title("Contrastive embedding: same sensor pulled together, different sensors pushed apart", fontsize=13)
    ax.set_xlabel(f"LDA dimension {int(summary['lda_dim_x']) + 1}")
    ax.set_ylabel(f"LDA dimension {int(summary['lda_dim_y']) + 1}")
    ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.65)
    ax.text(
        0.02,
        0.02,
        f"silhouette={summary['silhouette']:.3f}  centroid_acc={summary['centroid_acc']:.3f}",
        transform=ax.transAxes,
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.92},
    )
    plt.tight_layout()
    plt.savefig(FIG_DIR / "contrastive_embedding_lda.png", bbox_inches="tight")
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
    plt.savefig(FIG_DIR / "contrastive_distance_boxplot.png", bbox_inches="tight")
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
    plt.savefig(FIG_DIR / "contrastive_centroid_similarity.png", bbox_inches="tight")
    plt.close()


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    x, labels, conditions, files = load_dataset()
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

    plot_embedding(z, labels, conditions, summary)  # type: ignore[arg-type]
    plot_distance_boxplot(z, labels)
    plot_centroid_similarity(z, labels)

    (RESULT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
