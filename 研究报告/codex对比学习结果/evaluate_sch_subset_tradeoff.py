from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import accuracy_score, silhouette_score
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import NearestCentroid
from sklearn.preprocessing import StandardScaler


RESULT_DIR = Path(__file__).resolve().parent
ROOT = RESULT_DIR.parents[1]
LOG_ROOT = ROOT / "PUF_dataTransFreq" / "logs"
OUT_JSON = RESULT_DIR / "sch_subset_tradeoff.json"

LINE_TYPES = ["SPECTRUM_CH1", "SPECTRUM_CH2", "OFF_SPECTRUM_CH1", "OFF_SPECTRUM_CH2"]
SENSOR_ORDER = [f"B2-{i}" for i in range(1, 11)]
TOP_COUNTS = [1, 2, 4, 8, 16, 32, 64, 128, 256]


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


def normalize_rows(arr: np.ndarray) -> np.ndarray:
    return arr / (arr.sum(axis=1, keepdims=True) + 1e-12)


def read_file(csv_path: Path) -> dict[int, dict[str, np.ndarray]]:
    sch_map: dict[int, dict[str, np.ndarray]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sch = int(row["sch_index"])
            line_type = row["line_type"]
            if line_type not in LINE_TYPES:
                continue
            vec = np.array([float(row[f"bin_{i}"]) for i in range(128)], dtype=np.float64)
            if sch not in sch_map:
                sch_map[sch] = {}
            sch_map[sch][line_type] = vec
    return sch_map


def compact_row_features(arr: np.ndarray) -> list[float]:
    arr_norm = normalize_rows(arr)
    mean_shape = arr_norm.mean(axis=0)
    std_shape = arr_norm.std(axis=0)
    band_energy = [
        float(arr_norm[:, :8].sum(axis=1).mean()),
        float(arr_norm[:, 8:16].sum(axis=1).mean()),
        float(arr_norm[:, 16:32].sum(axis=1).mean()),
        float(arr_norm[:, 32:64].sum(axis=1).mean()),
        float(arr_norm[:, 64:128].sum(axis=1).mean()),
    ]
    band_std = [
        float(arr_norm[:, :16].std()),
        float(arr_norm[:, 16:64].std()),
        float(arr_norm[:, 64:128].std()),
    ]
    return mean_shape.tolist() + std_shape.tolist() + band_energy + band_std


def feature_from_subset(sch_map: dict[int, dict[str, np.ndarray]], subset: set[int]) -> np.ndarray:
    features: list[float] = []
    collected: dict[str, list[np.ndarray]] = {line_type: [] for line_type in LINE_TYPES}

    for sch in subset:
        if sch not in sch_map:
            continue
        for line_type in LINE_TYPES:
            if line_type in sch_map[sch]:
                collected[line_type].append(sch_map[sch][line_type])

    for line_type in LINE_TYPES:
        if not collected[line_type]:
            arr = np.zeros((1, 128), dtype=np.float64)
        else:
            arr = np.vstack(collected[line_type])
        features.extend(compact_row_features(arr))

    on_ch1 = normalize_rows(np.vstack(collected["SPECTRUM_CH1"])) if collected["SPECTRUM_CH1"] else np.zeros((1, 128), dtype=np.float64)
    off_ch1 = normalize_rows(np.vstack(collected["OFF_SPECTRUM_CH1"])) if collected["OFF_SPECTRUM_CH1"] else np.zeros((1, 128), dtype=np.float64)
    on_ch2 = normalize_rows(np.vstack(collected["SPECTRUM_CH2"])) if collected["SPECTRUM_CH2"] else np.zeros((1, 128), dtype=np.float64)

    diff_on_off = on_ch1.mean(axis=0) - off_ch1.mean(axis=0)
    diff_ch = on_ch1.mean(axis=0) - on_ch2.mean(axis=0)
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


def load_cache() -> tuple[list[dict[int, dict[str, np.ndarray]]], np.ndarray, np.ndarray, list[str]]:
    cached = []
    labels = []
    conditions = []
    files = []
    for label, directory in dataset_dirs().items():
        for csv_path in sorted(directory.glob("*.csv")):
            cached.append(read_file(csv_path))
            labels.append(label.split("_")[0])
            conditions.append("normal" if label.endswith("_normal") else label.split("_", 1)[1])
            files.append(str(csv_path))
    return cached, np.array(labels), np.array(conditions), files


def build_matrix(cached: list[dict[int, dict[str, np.ndarray]]], subset: set[int]) -> np.ndarray:
    return np.vstack([feature_from_subset(file_map, subset) for file_map in cached])


def cv_accuracy(X: np.ndarray, y: np.ndarray) -> float:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    scores = []
    for train_idx, test_idx in skf.split(X, y):
        scaler = StandardScaler().fit(X[train_idx])
        X_train = scaler.transform(X[train_idx])
        X_test = scaler.transform(X[test_idx])
        clf = LinearDiscriminantAnalysis()
        clf.fit(X_train, y[train_idx])
        pred = clf.predict(X_test)
        scores.append(accuracy_score(y[test_idx], pred))
    return float(np.mean(scores))


def embedding_quality(X: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    lda = LinearDiscriminantAnalysis(n_components=min(len(np.unique(y)) - 1, Xs.shape[1]))
    Z_full = lda.fit_transform(Xs, y)

    best_sil = -np.inf
    best_Z = None
    for i in range(Z_full.shape[1]):
        for j in range(i + 1, Z_full.shape[1]):
            Z = StandardScaler().fit_transform(Z_full[:, [i, j]])
            sil = silhouette_score(Z, y, metric="euclidean")
            if sil > best_sil:
                best_sil = float(sil)
                best_Z = Z
    assert best_Z is not None

    centroid_clf = NearestCentroid()
    centroid_clf.fit(best_Z, y)
    centroid_acc = float(accuracy_score(y, centroid_clf.predict(best_Z)))
    return best_sil, centroid_acc


def rank_single_sch(cached: list[dict[int, dict[str, np.ndarray]]], y: np.ndarray) -> list[dict[str, float | int]]:
    ranked = []
    for sch in range(256):
        X = build_matrix(cached, {sch})
        sil, centroid_acc = embedding_quality(X, y)
        ranked.append(
            {
                "sch": sch,
                "cv_acc": centroid_acc,
                "silhouette": sil,
                "centroid_acc": centroid_acc,
            }
        )
    ranked.sort(key=lambda item: (item["cv_acc"], item["silhouette"], item["centroid_acc"]), reverse=True)
    return ranked


def evaluate_top_subsets(cached: list[dict[int, dict[str, np.ndarray]]], y: np.ndarray, ranked_sch: list[dict[str, float | int]]) -> list[dict[str, object]]:
    results = []
    ranked_ids = [int(item["sch"]) for item in ranked_sch]
    full_ascii_ms = None

    for top_n in TOP_COUNTS:
        subset = set(ranked_ids[:top_n])
        X = build_matrix(cached, subset)
        cv_acc = cv_accuracy(X, y)
        sil, centroid_acc = embedding_quality(X, y)

        # Relative UART estimate for sch-driven spectrum traffic.
        # 4 records per sch per capture file: SPECTRUM_CH1/CH2 + OFF_SPECTRUM_CH1/CH2
        records_per_sch = 4
        ascii_chars_per_record = 781
        binary_bytes_per_record = 512 + 16  # 128 bins * 4 bytes + rough frame/header allowance
        ascii_bytes = top_n * records_per_sch * ascii_chars_per_record
        binary_bytes = top_n * records_per_sch * binary_bytes_per_record
        ascii_ms = ascii_bytes / 92160.0 * 1000.0
        binary_ms = binary_bytes / 92160.0 * 1000.0
        if top_n == 256:
            full_ascii_ms = ascii_ms

        results.append(
            {
                "top_n": top_n,
                "selected_sch": ranked_ids[:top_n],
                "cv_acc": cv_acc,
                "silhouette": sil,
                "centroid_acc": centroid_acc,
                "ascii_uart_ms_est": ascii_ms,
                "binary_uart_ms_est": binary_ms,
                "ascii_speedup_vs_256": (full_ascii_ms / ascii_ms) if full_ascii_ms else 1.0,
            }
        )

    # Fix speedup numbers once 256 baseline is known.
    assert full_ascii_ms is not None
    for item in results:
        item["ascii_speedup_vs_256"] = full_ascii_ms / float(item["ascii_uart_ms_est"])
    return results


def main() -> None:
    cached, labels, _conditions, files = load_cache()
    ranked = rank_single_sch(cached, labels)
    subset_results = evaluate_top_subsets(cached, labels, ranked)

    payload = {
        "n_files": len(files),
        "ranked_single_sch_top20": ranked[:20],
        "subset_results": subset_results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
