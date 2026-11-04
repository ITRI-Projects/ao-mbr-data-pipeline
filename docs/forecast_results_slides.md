# Multivariate Forecast Results and Discussion

## Slide 1 — Forecast design and chronological evaluation

- Source history spans 24 March 2026 13:00 through 23 April 2026 23:59.
- Training uses available history through April 17. Validation covers April 18–20. The rolling test covers April 21–23.
- Each forecast predicts the observed value one hour ahead. Forecasts are issued every 20 minutes and use 12 input steps spanning 3 hours 40 minutes.
- Models include Ridge, Random Forest, XGBoost and LSTM. The fill mask excludes carried-forward estimates from future labels.

## Slide 2 — How baseline and tuned models were compared

- Baseline refers to the original training run. The tuned runs reuse its prepared inputs and chronological splits.
- The search minimizes validation MSE and includes the fitted baseline model as a candidate. The test period evaluates the resulting models.
- Each arrow shows baseline → tuned for the same algorithm. Training R² measures in-sample fit. Negative test R² indicates higher squared error than the retrospective test-set mean.
- Saved prediction files agree on forecast origins, target times, split assignments and observed labels for all five available pairs.

## Slide 3 — Held-out performance of validation-selected models

For each paired target, the table uses the algorithm with the lowest tuned validation RMSE and compares it with that same algorithm's baseline. Test RMSE stays in the target's original units.

| Target | Algorithm | Test N | Test R² | Test RMSE |
|---|---|---:|---:|---:|
| Effluent ammonium | XGBoost | 211 | -0.060 → -0.000013 | 0.011436 → 0.011109 mg-N/L |
| Effluent nitrate | Ridge (baseline tie) | 211 | undefined → — | 0.000000 → — mg-N/L |
| A1 methanol dosing | Ridge | 213 | 0.732 → 0.730 | 26.368808 → 26.492304 m3/hour |
| A2 methanol dosing | XGBoost | 213 | 0.581 → 0.640 | 23.050518 → 21.378594 m3/hour |
| A1 aeration airflow | LSTM | 211 | -0.289 → -0.289 | 3.649801 → 3.649800 m3/min |
| A2 aeration airflow | LSTM | 211 | -0.293 → 0.082 | 3.352191 → 2.825258 m3/min |

## Slide 4 — Effluent ammonium

Held-out test samples **211**. MAE and RMSE in **mg-N/L**.

| Algorithm | Train R² | Validation R² | Test R² | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Ridge | 0.425 → 0.004 | -87.034 → -15.502 | -141.572 → -14.808 | 0.101064 → 0.042626 | 0.132648 → 0.044170 |
| Random Forest | 0.769 → 0.367 | -2.033 → -0.338 | -0.101 → -46.474 | 0.009745 → 0.069990 | 0.011656 → 0.076544 |
| XGBoost | 0.881 → 0.476 | -0.231 → -0.107 | -0.060 → -0.000013 | 0.009118 → 0.009128 | 0.011436 → 0.011109 |
| LSTM | 0.053 → 0.042 | -0.811 → -0.588 | -5.480 → -2.034 | 0.020905 → 0.016295 | 0.028279 → 0.019351 |

**XGBoost** has the lowest tuned validation RMSE. Its test RMSE moved from **0.011436** to **0.011109 mg-N/L**.

[Baseline metrics](assets/eff_nh3n_forecast/metrics_summary.csv) · [Baseline forecast plots](assets/eff_nh3n_forecast/train_test_predictions.png) · [Tuning comparison](assets/eff_nh3n_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/eff_nh3n_forecast_tuned/train_test_predictions.png)

## Slide 5 — Effluent nitrate

Held-out test samples **211**. MAE and RMSE in **mg-N/L**.

| Algorithm | Train R² | Validation R² | Test R² | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Ridge | undefined → — | undefined → — | undefined → — | 0.000000 → — | 0.000000 → — |
| Random Forest | undefined → — | undefined → — | undefined → — | 0.000000 → — | 0.000000 → — |
| XGBoost | undefined → — | undefined → — | undefined → — | 0.000000 → — | 0.000000 → — |
| LSTM | undefined → — | undefined → — | undefined → — | 0.009333 → — | 0.020488 → — |

The nitrate target is constant across all three splits. Ridge, Random Forest and XGBoost tie at zero baseline error. R² is undefined. The assets contain no tuned nitrate run, so the tuned values are shown as dashes.

[Baseline metrics](assets/eff_no3n_forecast/metrics_summary.csv) · [Baseline forecast plots](assets/eff_no3n_forecast/train_test_predictions.png)

## Slide 6 — A1 methanol dosing

Held-out test samples **213**. MAE and RMSE in **m3/hour**.

| Algorithm | Train R² | Validation R² | Test R² | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Ridge | 0.831 → 0.831 | 0.788 → 0.788 | 0.732 → 0.730 | 17.854024 → 17.958605 | 26.368808 → 26.492304 |
| Random Forest | 0.924 → 0.907 | 0.624 → 0.772 | 0.679 → 0.796 | 18.965436 → 15.365409 | 28.865771 → 23.011795 |
| XGBoost | 0.878 → 0.981 | 0.710 → 0.774 | 0.777 → 0.710 | 16.397944 → 20.541751 | 24.052408 → 27.450109 |
| LSTM | 0.831 → 0.811 | 0.713 → 0.748 | 0.741 → 0.698 | 17.641619 → 19.962884 | 25.907472 → 28.020748 |

**Ridge** has the lowest tuned validation RMSE. Its test RMSE moved from **26.368808** to **26.492304 m3/hour**.

[Baseline metrics](assets/a1_ch3oh_forecast/metrics_summary.csv) · [Baseline forecast plots](assets/a1_ch3oh_forecast/train_test_predictions.png) · [Tuning comparison](assets/a1_ch3oh_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a1_ch3oh_forecast_tuned/train_test_predictions.png)

## Slide 7 — A2 methanol dosing

Held-out test samples **213**. MAE and RMSE in **m3/hour**.

| Algorithm | Train R² | Validation R² | Test R² | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Ridge | 0.803 → 0.804 | 0.650 → 0.650 | 0.607 → 0.608 | 14.527613 → 14.538199 | 22.313058 → 22.288170 |
| Random Forest | 0.926 → 0.908 | 0.598 → 0.651 | 0.559 → 0.653 | 14.666775 → 12.977797 | 23.654645 → 20.987292 |
| XGBoost | 0.869 → 0.955 | 0.676 → 0.684 | 0.581 → 0.640 | 16.124259 → 14.865253 | 23.050518 → 21.378594 |
| LSTM | 0.805 → 0.775 | 0.572 → 0.619 | 0.634 → 0.600 | 16.136361 → 16.917903 | 21.531232 → 22.516322 |

**XGBoost** has the lowest tuned validation RMSE. Its test RMSE moved from **23.050518** to **21.378594 m3/hour**.

[Baseline metrics](assets/a2_ch3oh_forecast/metrics_summary.csv) · [Baseline forecast plots](assets/a2_ch3oh_forecast/train_test_predictions.png) · [Tuning comparison](assets/a2_ch3oh_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a2_ch3oh_forecast_tuned/train_test_predictions.png)

## Slide 8 — A1 aeration airflow

Held-out test samples **211**. MAE and RMSE in **m3/min**.

| Algorithm | Train R² | Validation R² | Test R² | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Ridge | 0.680 → 0.672 | 0.596 → 0.600 | 0.213 → 0.242 | 1.600886 → 1.547761 | 2.850983 → 2.797598 |
| Random Forest | 0.872 → 0.813 | -2.877 → 0.275 | 0.140 → 0.229 | 1.842058 → 1.564249 | 2.980221 → 2.821518 |
| XGBoost | 0.860 → 0.677 | -6.029 → 0.630 | 0.084 → 0.073 | 2.025419 → 1.898258 | 3.075671 → 3.094388 |
| LSTM | 0.838 → 0.838 | 0.821 → 0.821 | -0.289 → -0.289 | 2.034440 → 2.034440 | 3.649801 → 3.649800 |

**LSTM** has the lowest tuned validation RMSE. Its test RMSE moved from **3.649801** to **3.649800 m3/min**.

[Baseline metrics](assets/a1_air_forecast/metrics_summary.csv) · [Baseline forecast plots](assets/a1_air_forecast/train_test_predictions.png) · [Tuning comparison](assets/a1_air_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a1_air_forecast_tuned/train_test_predictions.png)

## Slide 9 — A2 aeration airflow

Held-out test samples **211**. MAE and RMSE in **m3/min**.

| Algorithm | Train R² | Validation R² | Test R² | Test MAE | Test RMSE |
|---|---:|---:|---:|---:|---:|
| Ridge | 0.797 → 0.796 | 0.737 → 0.738 | 0.182 → 0.197 | 1.624938 → 1.607041 | 2.666906 → 2.642164 |
| Random Forest | 0.928 → 0.893 | 0.721 → 0.821 | 0.323 → 0.409 | 1.347319 → 1.186022 | 2.426060 → 2.265884 |
| XGBoost | 0.910 → 0.709 | -0.059 → 0.848 | 0.217 → 0.292 | 1.548305 → 1.460398 | 2.608962 → 2.480585 |
| LSTM | 0.833 → 0.852 | 0.742 → 0.879 | -0.293 → 0.082 | 2.050190 → 1.740633 | 3.352191 → 2.825258 |

**LSTM** has the lowest tuned validation RMSE. Its test RMSE moved from **3.352191** to **2.825258 m3/min**.

[Baseline metrics](assets/a2_air_forecast/metrics_summary.csv) · [Baseline forecast plots](assets/a2_air_forecast/train_test_predictions.png) · [Tuning comparison](assets/a2_air_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a2_air_forecast_tuned/train_test_predictions.png)

## Slide 10 — What changed after tuning

- Test RMSE improved in **14 of 20** paired algorithm comparisons, worsened in **6**, and stayed within 0.000000001 of baseline in **0**.
- The highest tuned test R² was **0.796** across the five paired targets. Nitrate is reported separately because its observed labels are constant and its tuned run is missing.
- All comparisons use the saved forecasts in the linked asset folders.
