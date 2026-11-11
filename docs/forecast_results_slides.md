# Multivariate Forecast Results and Discussion

## Slide 1 — Forecast design and chronological evaluation

| Setting | Configuration |
|---|---|
| Forecast horizon | 10 minutes ahead |
| Forecast frequency | Every 10 minutes |
| Input history | Seven time points from 60 minutes ago through the forecast time |
| Training | 4–17 April 2026 · 71.0–71.7% |
| Validation | 18–20 April 2026 · 15.3–15.7% |
| Held-out test | 21–23 April 2026 · 12.9–13.3% |
| Scoring | Compare forecasts with measured readings at the exact target time |

The split percentages count eligible forecasts and vary by target. The nitrate run uses the same 10-minute design and date boundaries. Its separate export retains original nitrate observations for a constant-signal baseline and excludes invalid readings and synchronized corrupt intervals.

## Slide 2 — How original and tuned models were compared

- Each arrow shows **original → tuned** for the same algorithm on the same test samples.
- Tuning reused the original inputs and splits. It selected settings by lowest validation MSE and included the original model as a candidate.
- The tuning comparisons cover five targets. Nitrate is shown as a baseline run.
- The highlighted winners have the lowest held-out test RMSE. RMSE uses the target's original units.
- Negative test R² means the model had higher squared error than predicting the test-set average.

## Slide 3 — Best held-out results by target

| Target | Best result | Test forecasts | Test RMSE | Test R² |
|---|---|---:|---:|---:|
| Effluent ammonia | Tuned LSTM | 362 | 0.011777 mg-N/L | −0.040 |
| Effluent nitrate | Ridge, Random Forest, and XGBoost tied | 362 | 0.000000 mg-N/L | Undefined |
| A1 methanol dosing | Tuned Random Forest | 365 | 7.686 m³/h | 0.979 |
| A2 methanol dosing | Original Ridge Regression | 365 | 8.079 m³/h | 0.951 |
| A1 aeration airflow | Ridge Regression (original and tuned tied) | 361 | 1.515 m³/min | 0.820 |
| A2 aeration airflow | Tuned Ridge Regression | 361 | 1.356 m³/min | 0.829 |

## Slide 4 — Effluent ammonia (NH₄-N)

**362 held-out forecasts · 10 minutes ahead**

| Algorithm | Test RMSE (mg-N/L) | Test R² | Highlight |
|---|---:|---:|---|
| Ridge Regression | 0.013040 → 0.012517 | −0.274 → −0.174 | RMSE fell 4.0% |
| Random Forest | 0.012762 → 0.012671 | −0.221 → −0.203 | Smallest RMSE improvement (0.7%) |
| XGBoost | 0.013077 → 0.012333 | −0.282 → −0.140 | RMSE fell 5.7% |
| **LSTM** | **0.012681 → 0.011777** | **−0.205 → −0.040** | Lowest RMSE before and after tuning (7.1% lower) |

[Original metrics](assets/eff_nh3n_forecast/metrics_summary.csv) · [Original forecast plots](assets/eff_nh3n_forecast/train_test_predictions.png) · [Tuning comparison](assets/eff_nh3n_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/eff_nh3n_forecast_tuned/train_test_predictions.png)

## Slide 5 — Effluent nitrate (NO₃-N)

**362 held-out forecasts · 10 minutes ahead · Nitrate baseline**

| Algorithm | Test MAE (mg-N/L) | Test RMSE (mg-N/L) | Test R² |
|---|---:|---:|---:|
| Ridge Regression | 0.000000 | 0.000000 | Undefined |
| Random Forest | 0.000000 | 0.000000 | Undefined |
| XGBoost | 0.000000 | 0.000000 | Undefined |
| LSTM | 0.009560 | 0.016211 | Undefined |

The run used 2,005 training, 432 validation, and 362 test samples. Every scored nitrate reading was 5.0 mg-N/L. Ridge, Random Forest, and XGBoost reproduced that level exactly. Performance on changing nitrate concentrations remains unmeasured.

[Nitrate run settings and sample counts](assets/eff_no3n_forecast/manifest.json) · [Nitrate metrics](assets/eff_no3n_forecast/metrics_summary.csv) · [Nitrate forecast plots](assets/eff_no3n_forecast/train_test_predictions.png)

## Slide 6 — A1 methanol dosing

**365 held-out forecasts · 10 minutes ahead**

| Algorithm | Test RMSE (m³/h) | Test R² | Highlight |
|---|---:|---:|---|
| Ridge Regression | 9.668 → 9.742 | 0.967 → 0.966 | RMSE rose 0.8% |
| **Random Forest** | **8.222 → 7.686** | **0.976 → 0.979** | Lowest RMSE before and after tuning (6.5% lower) |
| XGBoost | 8.438 → 8.265 | 0.975 → 0.976 | RMSE fell 2.1% |
| LSTM | 11.182 → 9.202 | 0.956 → 0.970 | Largest RMSE reduction (17.7%) |

[Original metrics](assets/a1_ch3oh_forecast/metrics_summary.csv) · [Original forecast plots](assets/a1_ch3oh_forecast/train_test_predictions.png) · [Tuning comparison](assets/a1_ch3oh_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a1_ch3oh_forecast_tuned/train_test_predictions.png)

## Slide 7 — A2 methanol dosing

**365 held-out forecasts · 10 minutes ahead**

| Algorithm | Test RMSE (m³/h) | Test R² | Highlight |
|---|---:|---:|---|
| **Ridge Regression** | **8.079 → 8.170** | **0.951 → 0.950** | Lowest RMSE in both runs. The original fit scored better |
| Random Forest | 10.911 → 10.914 | 0.911 → 0.911 | RMSE rose by less than 0.1% |
| XGBoost | 9.533 → 10.157 | 0.932 → 0.923 | RMSE rose 6.5% |
| LSTM | 15.015 → 20.482 | 0.832 → 0.688 | Largest RMSE increase (36.4%) |

[Original metrics](assets/a2_ch3oh_forecast/metrics_summary.csv) · [Original forecast plots](assets/a2_ch3oh_forecast/train_test_predictions.png) · [Tuning comparison](assets/a2_ch3oh_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a2_ch3oh_forecast_tuned/train_test_predictions.png)

## Slide 8 — A1 aeration airflow

**361 held-out forecasts · 10 minutes ahead**

| Algorithm | Test RMSE (m³/min) | Test R² | Highlight |
|---|---:|---:|---|
| **Ridge Regression** | **1.515 → 1.515** | **0.820 → 0.820** | Lowest RMSE in both runs. Tuning retained the original fit |
| Random Forest | 1.762 → 1.742 | 0.757 → 0.762 | Only model with lower RMSE after tuning |
| XGBoost | 1.765 → 2.083 | 0.756 → 0.660 | Largest RMSE increase (18.0%) |
| LSTM | 3.356 → 3.520 | 0.118 → 0.029 | Highest RMSE in both runs |

[Original metrics](assets/a1_air_forecast/metrics_summary.csv) · [Original forecast plots](assets/a1_air_forecast/train_test_predictions.png) · [Tuning comparison](assets/a1_air_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a1_air_forecast_tuned/train_test_predictions.png)

## Slide 9 — A2 aeration airflow

**361 held-out forecasts · 10 minutes ahead**

| Algorithm | Test RMSE (m³/min) | Test R² | Highlight |
|---|---:|---:|---|
| **Ridge Regression** | **1.370 → 1.356** | **0.825 → 0.829** | Lowest RMSE in both runs |
| Random Forest | 1.732 → 1.515 | 0.721 → 0.786 | RMSE fell 12.5% |
| XGBoost | 1.496 → 1.631 | 0.791 → 0.752 | RMSE rose 9.0% |
| LSTM | 2.460 → 2.086 | 0.436 → 0.595 | Largest RMSE reduction (15.2%) and highest tuned RMSE |

[Original metrics](assets/a2_air_forecast/metrics_summary.csv) · [Original forecast plots](assets/a2_air_forecast/train_test_predictions.png) · [Tuning comparison](assets/a2_air_forecast_tuned/comparison.csv) · [Tuned forecast plots](assets/a2_air_forecast_tuned/train_test_predictions.png)

## Slide 10 — Conclusions

- **A1 aeration airflow.** Ridge Regression led before and after tuning. Its RMSE stayed at **1.515 m³/min**.
- **A2 aeration airflow.** Tuned Ridge Regression led with **1.356 m³/min** RMSE.
- **A1 methanol dosing.** Tuned Random Forest led with **7.686 m³/h** RMSE and **0.979** R².
- **A2 methanol dosing.** Original Ridge Regression led with **8.079 m³/h** RMSE. Its tuned fit had slightly higher error.
- **Effluent ammonia.** Tuned LSTM led and reduced RMSE by **7.1%**. All four models still had negative test R².
- **Effluent nitrate.** Three models exactly reproduced the recorded 5.0 mg-N/L level across 362 ten-minute forecasts. R² is undefined for this constant target.
- **Effect of tuning.** Test RMSE improved in **11 of 20** model comparisons, worsened in **8**, and stayed unchanged in **1**.
