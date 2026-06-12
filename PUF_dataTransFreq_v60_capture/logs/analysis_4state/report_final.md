# Final: 10 Sensors × 4 Conditions — LDA Analysis

## Method
- File-level features: per-CSV averaged normalized FFT spectrum (FULL mode only)
- Feature: 128-bin spectrum (CH1+CH2) + CH1/CH2 diff + low-freq energy ratios
- Condition normalization: subtract per-condition mean to remove environmental bias
- Dimensionality reduction: PCA → LDA → best 2D silhouette search

## Key Metrics
| Metric | Value |
|:---|---:|
| Silhouette | **0.3499** |
| 1-NN Accuracy | **1.0000** |
| Intra-Sensor Distance | 1.5744 |
| Inter-Sensor Distance | 24.4585 |
| Inter/Intra Ratio | **15.54x** |

## Figures
![Main LDA](figures/final_lda_main.png)
![B2-1 Detail](figures/final_b2-1_detail.png)
![Distance](figures/final_distance.png)
![Centroid](figures/final_centroid.png)
