# Training utilities

- `sensor_preparation.py`: sensor behavior audit and causal age-limited filling (notebook 02).
- `training_data.py`: conservative gap filling and historical-window ranking.
- `forecast_dataset.py`: configured one-hour forecasting datasets and sequence exports.

Run the dataset CLI from the repository root:

```bash
python -m src.training.forecast_dataset --source notebooks/data/google_drive_raw_aliases.csv
```

Notebook 02 keeps loading, policy settings, plotting and exporting visible while
calling reusable preparation functions here. Database and API code stays in `src/`.

The model notebooks 03-05 reference `src.training.preparation_experiments`, and
notebook 01 optionally references `src.training.dataset_review`. Those two modules
were already absent before this refactor; their implementations must be restored
to this package before running the corresponding training sections.
