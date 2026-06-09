# Reproduce Instructions

This folder contains the reproducible script for the LDA-based contrastive-style embedding result.

## Run

From project root:

```powershell
python "D:\Project\FPGA_DATAtransFreq_0514\研究报告\codex对比学习结果\reproduce_contrastive_lda.py"
```

## Dependencies

The script uses:

- `numpy`
- `matplotlib`
- `scikit-learn`

## Inputs

The script reads CSV files from:

- `D:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq\logs\256pt_4ch_B2-1`
- `D:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq\logs\256pt_4ch_B2-1_0526`
- `D:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq\logs\256pt_4ch_B2-1_highPressure`
- `D:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq\logs\256pt_4ch_B2-1_highTemp`
- `D:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq\logs\256pt_4ch_B2-2` through `B2-10`

## Outputs

The script regenerates:

- `summary.json`
- `figures/contrastive_embedding_lda.png`
- `figures/contrastive_distance_boxplot.png`
- `figures/contrastive_centroid_similarity.png`

## Expected Metrics

Expected values should be close to:

- `n_files`: `530`
- `n_features`: `1828`
- `silhouette`: `0.8905`
- `centroid_acc`: `1.0000`
- `same_mean_distance`: `0.0703`
- `different_mean_distance`: `1.9296`
- `distance_ratio`: `27.44`

Small floating-point differences are normal across library versions.

## Method Summary

Each CSV is treated as one file-level sample. For each file, the script extracts normalized spectral-shape features from four line types:

- `SPECTRUM_CH1`
- `SPECTRUM_CH2`
- `OFF_SPECTRUM_CH1`
- `OFF_SPECTRUM_CH2`

It then adds low-frequency band ratios, ON/OFF differential features, and CH1/CH2 differential features. Features are standardized, projected with LDA, and the best 2D LDA plane is selected by silhouette score.
