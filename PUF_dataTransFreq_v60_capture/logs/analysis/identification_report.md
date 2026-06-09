# V6.0 10-Sensor PUF Fingerprint Identification Report

Generated from 10 sensors (B2-1 ~ B2-10), each with 100 MODE=08 + 100 MODE=64 frames.

---
## MODE=08 Analysis

| Metric | Value |
|--------|-------|
| Frames analyzed | 1000 |
| Features extracted | 94 |
| Raw-data intra-sensor distance (mean±std) | 17.3 ± ??? |
| Raw-data inter-sensor distance (mean) | 291.4 |
| **Raw separation ratio (inter/intra)** | **16.886** |
| Feature-space intra distance | 3.098 |
| Feature-space inter distance | 8.999 |
| **Feature separation ratio** | **2.905** |
| **Silhouette score** | **0.5272** |
| KNN-3 accuracy | 99.67% |
| 5-fold CV accuracy | 100.00% ± 0.00% |

---
## MODE=64 Analysis

| Metric | Value |
|--------|-------|
| Frames analyzed | 1000 |
| Features extracted | 94 |
| Raw-data intra-sensor distance (mean±std) | 17.6 ± ??? |
| Raw-data inter-sensor distance (mean) | 801.9 |
| **Raw separation ratio (inter/intra)** | **45.458** |
| Feature-space intra distance | 4.317 |
| Feature-space inter distance | 9.618 |
| **Feature separation ratio** | **2.228** |
| **Silhouette score** | **0.3845** |
| KNN-3 accuracy | 99.33% |
| 5-fold CV accuracy | 99.90% ± 0.20% |

---
## Cross-Mode Comparison

| Metric | MODE=08 | MODE=64 | Better |
|--------|---------|---------|--------|
| Separation Ratio Raw | 16.8858 | 45.4585 | MODE=64 |
| Feat Separation Ratio | 2.9048 | 2.2278 | MODE=08 |
| Silhouette Score | 0.5272 | 0.3845 | MODE=08 |
| Knn3 Accuracy | 0.9967% | 0.9933% | MODE=08 |
| Cv Mean | 1.0000% | 0.9990% | MODE=08 |

## Per-Sensor Detail

| Sensor | MODE=08 Intra Mean | MODE=08 Inter Mean | MODE=08 Sep Ratio | MODE=64 Intra Mean | MODE=64 Inter Mean | MODE=64 Sep Ratio |
|--------|-------------------|--------------------|-------------------|--------------------|--------------------|-------------------|
| B2-1 | 17.1 | 307.8 | 17.962 | 17.4 | 879.5 | 50.610 |
| B2-2 | 17.4 | 340.1 | 19.567 | 19.4 | 937.6 | 48.283 |
| B2-3 | 17.2 | 222.3 | 12.945 | 17.4 | 611.7 | 35.237 |
| B2-4 | 17.2 | 225.9 | 13.123 | 17.5 | 587.9 | 33.670 |
| B2-5 | 18.0 | 426.0 | 23.696 | 18.2 | 1246.0 | 68.625 |
| B2-6 | 17.1 | 215.1 | 12.591 | 17.1 | 578.4 | 33.836 |
| B2-7 | 17.2 | 308.8 | 17.929 | 17.3 | 835.5 | 48.238 |
| B2-8 | 17.1 | 213.6 | 12.452 | 17.4 | 581.0 | 33.432 |
| B2-9 | 17.2 | 267.0 | 15.546 | 17.4 | 668.0 | 38.341 |
| B2-10 | 17.1 | 387.4 | 22.714 | 17.4 | 1093.2 | 62.793 |

## Conclusion
- **Best performing mode**: MODE=08
- **Min separation ratio**: 2.228
- **Max KNN accuracy**: 99.67%
- Silhouette score > 0.5 indicates well-separated clusters.
- Separation ratio >> 1.0 means inter-sensor distance dominates intra-sensor variation.