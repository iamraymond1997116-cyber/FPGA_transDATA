from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


RESULT_DIR = Path(__file__).resolve().parent
JSON_PATH = RESULT_DIR / "sch_subset_tradeoff.json"
VIEW_JSON_PATH = RESULT_DIR / "sch_view_split_analysis.json"
FIG_DIR = RESULT_DIR / "figures"
REPORT_PATH = RESULT_DIR / "report.md"


def load_payload() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def load_view_payload() -> dict:
    return json.loads(VIEW_JSON_PATH.read_text(encoding="utf-8"))


def gaussian_band(entries: list[dict[str, float]], sigma: float = 3.0) -> np.ndarray:
    x = np.arange(256, dtype=float)
    heat = np.zeros(256, dtype=float)
    if not entries:
        return heat

    weights = np.linspace(1.0, 0.45, num=len(entries))
    for base_weight, entry in zip(weights, entries, strict=False):
        sch = int(entry["sch"])
        proxy = float(entry.get("proxy_acc", 0.0))
        heat += base_weight * (0.5 + 0.5 * proxy) * np.exp(-0.5 * ((x - sch) / sigma) ** 2)

    peak = float(heat.max())
    if peak > 0:
        heat /= peak
    return heat


def make_figures(payload: dict, view_payload: dict) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    top20 = payload["ranked_single_sch_top20"]
    subset_results = payload["subset_results"]

    sch_labels = [str(item["sch"]) for item in top20[:12]]
    sch_scores = [item["silhouette"] for item in top20[:12]]
    plt.figure(figsize=(10, 5), dpi=200)
    plt.bar(sch_labels, sch_scores, color="#1f77b4")
    plt.ylabel("Silhouette")
    plt.xlabel("SCH index")
    plt.title("Top informative SCH values")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "top_sch_scores.png", bbox_inches="tight")
    plt.close()

    top_n = [item["top_n"] for item in subset_results]
    cv_acc = [item["cv_acc"] for item in subset_results]
    sil = [item["silhouette"] for item in subset_results]
    plt.figure(figsize=(10, 5), dpi=200)
    plt.plot(top_n, cv_acc, marker="o", label="5-fold CV accuracy")
    plt.plot(top_n, sil, marker="s", label="Embedding silhouette")
    plt.xscale("log", base=2)
    plt.xticks(top_n, [str(v) for v in top_n])
    plt.ylim(0.45, 1.02)
    plt.xlabel("Number of selected SCH values")
    plt.ylabel("Score")
    plt.title("Accuracy vs SCH subset size")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "accuracy_vs_subset_size.png", bbox_inches="tight")
    plt.close()

    ascii_ms = [item["ascii_uart_ms_est"] for item in subset_results]
    binary_ms = [item["binary_uart_ms_est"] for item in subset_results]
    plt.figure(figsize=(10, 5), dpi=200)
    plt.plot(top_n, ascii_ms, marker="o", label="ASCII")
    plt.plot(top_n, binary_ms, marker="s", label="Binary")
    plt.xscale("log", base=2)
    plt.yscale("log", base=10)
    plt.xticks(top_n, [str(v) for v in top_n])
    plt.xlabel("Number of selected SCH values")
    plt.ylabel("Estimated UART time (ms)")
    plt.title("UART time vs SCH subset size")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "uart_time_vs_subset_size.png", bbox_inches="tight")
    plt.close()

    view_order = ["ON_CH1", "ON_CH2", "OFF_CH1", "OFF_CH2", "ALL"]
    heat = np.zeros((len(view_order), 256), dtype=float)
    row_entries: list[list[dict[str, float]]] = []

    for row, view_name in enumerate(view_order):
        if view_name == "ALL":
            entries = [
                item
                for name in ["ON_CH1", "ON_CH2", "OFF_CH1", "OFF_CH2"]
                for item in view_payload["views"][name]["top10_single_sch"]
            ]
            heat[row] = gaussian_band(entries, sigma=4.0)
        else:
            entries = view_payload["views"][view_name]["top10_single_sch"]
            heat[row] = gaussian_band(entries, sigma=3.0)
        row_entries.append(entries)

    plt.figure(figsize=(15, 5.2), dpi=220)
    plt.imshow(heat, aspect="auto", cmap="YlOrRd", origin="upper")
    for row, entries in enumerate(row_entries):
        xs = [int(item["sch"]) for item in entries]
        ys = [row] * len(xs)
        plt.scatter(xs, ys, s=16, c="white", edgecolors="black", linewidths=0.35, zorder=3)
    plt.yticks(range(len(view_order)), view_order)
    plt.xticks(range(0, 256, 16), [str(v) for v in range(0, 256, 16)])
    plt.xlabel("SCH index (0-255)")
    plt.title("SCH hotspot bands across 0-255")
    plt.colorbar(label="Normalized hotspot intensity")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "sch_hotspot_heatmap.png", bbox_inches="tight")
    plt.close()


def write_report(payload: dict, view_payload: dict) -> None:
    subset_results = payload["subset_results"]
    best8 = next(item for item in subset_results if item["top_n"] == 8)
    best16 = next(item for item in subset_results if item["top_n"] == 16)
    full256 = next(item for item in subset_results if item["top_n"] == 256)

    view_block = []
    for view_name in ["ON_CH1", "ON_CH2", "OFF_CH1", "OFF_CH2"]:
        top10 = [item["sch"] for item in view_payload["views"][view_name]["top10_single_sch"]]
        view_block.append(f"- `{view_name}` top10: `{top10}`")

    report = f"""# SCH 子集与 UART 开销量化评估

## 结论

这次评估回答两个问题：
1. `sch` 从 `0..255` 全扫是否必要；
2. 只保留少量高价值 `sch` 时，UART 能省多少，识别会掉多少。

结论很明确：研究阶段需要全扫来找出高价值区间，但在线识别阶段不需要全扫。保留少量高价值 `sch`，识别率几乎不掉，UART 开销却能明显下降。

## 关键结果

- `top 8 sch` 的 5-fold CV 准确率：`{best8["cv_acc"]:.4f}`
- `top 16 sch` 的 5-fold CV 准确率：`{best16["cv_acc"]:.4f}`
- `top 256 sch` 的 5-fold CV 准确率：`{full256["cv_acc"]:.4f}`
- `top 8 sch` 相比 `256 sch` 的 ASCII 传输时间缩短：`{best8["ascii_speedup_vs_256"]:.1f}x`

也就是说，前 8 个最有信息量的 `sch` 已经保住了大部分识别能力。

## 最推荐子集

前 8 个 `sch`：

`{best8["selected_sch"]}`

前 16 个 `sch`：

`{best16["selected_sch"]}`

## 图示

![Top SCH scores](figures/top_sch_scores.png)

![Accuracy vs subset size](figures/accuracy_vs_subset_size.png)

![UART time vs subset size](figures/uart_time_vs_subset_size.png)

![SCH hotspot distribution](figures/sch_hotspot_heatmap.png)

## 结果解释

第一张图说明：单个 `sch` 的区分能力差异很大，不是所有 `sch` 都有同样的身份信息量。

第二张图说明：随着 `sch` 数量增加，识别率很快饱和，`8` 个左右已经接近上限，后面继续加到 `16/32/64/128/256`，收益很小。

第三张图说明：UART 时间几乎线性随 `sch` 数量增长，所以减少 `sch` 数量是最直接、最有效的降时延手段。

第四张图是更直观的热区图。它显示高价值 `sch` 不是离散乱点，而是明显成带分布，说明身份信息更可能集中在若干连续区间，而不是均匀铺在 `0..255` 全部位置。

## 对你的问题的直接回答

### UART 怎么优化

- 优先减少在线发送的 `sch` 个数
- 再考虑 ASCII 改 binary
- 再考虑只传筛选后的频谱特征，而不是 RAW 全量数据

### `sch 0..255` 全扫有没有必要

- 研究阶段：有必要，用来找出真正有区分力的 `sch` 区间
- 部署阶段：没必要，保留 `top 8` 或 `top 16` 更划算

### CH1 和 CH2 是否等价

当前数据里不等价。`OFF_CH2` 明显强于 `OFF_CH1`，`ON_CH2` 也整体优于 `ON_CH1`，所以不建议默认平均对待两路通道。

### 这些 `sch` 的位置有没有规律

有，而且是“成带区间”规律，不是随机散点。当前最明显的热区包括：

- `ON_CH1`: `32~33`, `89~91`, `106~108`, `234~240`
- `ON_CH2`: `32~33`, `106~109`, `113~115`, `128~129`, `235~236`
- `OFF_CH1`: `106~108`, `112~116`, `120~122`
- `OFF_CH2`: `89~90`, `112~115`, `120~121`, `241~243`

这说明后续在线配置时，不建议随机挑 `sch`，而应该优先保留这些成带的高价值区间。

## 四路视角摘要

{chr(10).join(view_block)}

## 复现

评估脚本：

- `evaluate_sch_subset_tradeoff.py`

出图和报告脚本：

- `render_report.py`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    payload = load_payload()
    view_payload = load_view_payload()
    make_figures(payload, view_payload)
    write_report(payload, view_payload)


if __name__ == "__main__":
    main()
