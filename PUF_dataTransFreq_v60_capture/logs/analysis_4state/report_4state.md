# 10 Sensors × 4 Conditions — Cross-Condition LDA Analysis

## Overview
Frame-level normalized spectral features + LDA supervised projection.
Each of the 2000 128-point dual-channel ADC frames is treated as an individual sample.

## Key Metrics
| Metric | Value |
|:---|---:|
| Silhouette | **-0.1073** |
| Centroid Accuracy (1-NN) | **1.0000** |
| Intra-Sensor Distance | 1.2170 |
| Inter-Sensor Distance | 2.2016 |
| Inter/Intra Ratio | **1.81x** |

## Figures

### Main LDA Embedding
![Main](figures/lda_embedding_main.png)

### B2-1 Condition Detail
![B2-1](figures/lda_b2-1_conditions.png)

### Distance Analysis
![Distance](figures/distance_boxplot.png)

### Centroid Similarity
![Centroid](figures/centroid_similarity.png)
