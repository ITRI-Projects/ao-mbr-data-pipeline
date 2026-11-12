"""Select one saved forecast per workbook target using validation predictions."""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .workbook import NAMES, TARGETS


TARGET_COLUMNS = dict(zip(NAMES, TARGETS.values()))
ALGORITHM_ORDER = ("Ridge", "Random Forest", "XGBoost", "LSTM")


@dataclass(frozen=True)
class ForecastRun:
    path: Path
    variant: str
    horizon_minutes: int
    prediction_mode: str
    labels: dict
    predictions: dict
    sha256: str


def read_run(path, manifest):
    content = path.read_bytes()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or []
    algorithms = [algorithm for algorithm in ALGORITHM_ORDER if algorithm in fields]
    if (len(fields) != len(set(fields)) or not algorithms
            or not {"origin", "target_time", "split", "target"}.issubset(fields)):
        raise ValueError(f"Invalid prediction columns in {path}.")

    labels = {}
    predictions = {algorithm: {} for algorithm in algorithms}
    for row in reader:
        if row["split"] != "validation":
            continue
        try:
            key = (datetime.fromisoformat(row["origin"]), datetime.fromisoformat(row["target_time"]))
            observed = float(row["target"])
            values = [float(row[algorithm]) for algorithm in algorithms]
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid validation data in {path} at line {reader.line_num}.") from error
        if key in labels or not all(map(math.isfinite, [observed, *values])):
            raise ValueError(f"Duplicate timestamp pair or non-finite value in {path} at line {reader.line_num}.")
        labels[key] = observed
        for algorithm, value in zip(algorithms, values):
            predictions[algorithm][key] = value
    if not labels:
        raise ValueError(f"No validation rows in {path}.")

    horizon = manifest.get("horizon_minutes")
    if type(horizon) is not int or horizon < 1:
        raise ValueError(f"Invalid forecast horizon in {path.parent / 'manifest.json'}.")
    return ForecastRun(
        path, "tuned" if manifest.get("baseline_source") else "raw",
        horizon, manifest.get("prediction_mode", "absolute"),
        labels, predictions, hashlib.sha256(content).hexdigest(),
    )


def discover_runs(assets):
    runs = {model: {} for model in TARGET_COLUMNS}
    for path in sorted(assets.glob("*/manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        targets = manifest.get("targets", {})
        if len(targets) != 1:
            continue
        model, metadata = next(iter(targets.items()))
        if model not in runs:
            continue
        if metadata.get("target") != TARGET_COLUMNS[model]:
            raise ValueError(f"Unexpected target column for {model} in {path}.")
        run = read_run(path.with_name("predictions.csv"), manifest)
        if run.variant in runs[model]:
            raise ValueError(f"Multiple {run.variant} forecasts for {model}: {runs[model][run.variant].path}, {run.path}.")
        runs[model][run.variant] = run

    missing = [model for model, candidates in runs.items() if not candidates]
    if missing:
        raise ValueError(f"No single-target forecast artifacts in {assets} for: {', '.join(missing)}.")
    return runs


def validation_errors(run, algorithm):
    errors = [abs(run.predictions[algorithm][key] - label) for key, label in run.labels.items()]
    return math.sqrt(math.fsum(error ** 2 for error in errors) / len(errors)), math.fsum(errors) / len(errors)


def select_models(assets):
    selections = []
    for model, candidates in discover_runs(assets).items():
        if "raw" in candidates and "tuned" in candidates:
            raw, tuned = candidates["raw"], candidates["tuned"]
            if (raw.horizon_minutes, raw.prediction_mode) != (tuned.horizon_minutes, tuned.prediction_mode):
                raise ValueError(f"Raw and tuned forecasts for {model} have different horizons or prediction modes.")
            if raw.labels != tuned.labels:
                raise ValueError(f"Raw and tuned forecasts for {model} have different validation timestamps or labels.")

        ranked = []
        for run in candidates.values():
            for algorithm in run.predictions:
                rmse, mae = validation_errors(run, algorithm)
                rank = (rmse, mae, ALGORITHM_ORDER.index(algorithm), run.variant != "raw")
                ranked.append((rank, run, algorithm))
        (rmse, mae, _, _), winner, algorithm = min(ranked, key=lambda candidate: candidate[0])
        selections.append({
            "model": model,
            "target": TARGET_COLUMNS[model],
            "variant": winner.variant,
            "prediction_column": algorithm,
            "predictions_csv": winner.path,
            "predictions_sha256": winner.sha256,
            "horizon_minutes": winner.horizon_minutes,
            "validation_rows": len(winner.labels),
            "validation_rmse": rmse,
            "validation_mae": mae,
        })
    return selections


def save_selections(selections, output):
    output = output.resolve()
    records = []
    for selection in selections:
        source = selection["predictions_csv"].resolve()
        try:
            path = Path(os.path.relpath(source, output.parent)).as_posix()
        except ValueError:  # Windows paths on different volumes cannot be relative.
            path = source.as_posix()
        records.append(dict(selection, predictions_csv=path))

    document = {
        "selection_split": "validation",
        "ranking": ["RMSE", "MAE", "algorithm order", "raw before tuned"],
        "algorithm_order": ALGORITHM_ORDER,
        "selections": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False)
    staged = Path(temporary.name)
    try:
        with temporary:
            json.dump(document, temporary, indent=2, allow_nan=False)
            temporary.write("\n")
        staged.replace(output)
    finally:
        staged.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default="docs/assets", help="Directory containing saved forecast runs")
    parser.add_argument("--output", type=Path, default="data/forecast_selection.json", help="Selection JSON path")
    args = parser.parse_args(argv)
    try:
        selections = select_models(args.assets)
        save_selections(selections, args.output)
    except (ValueError, OSError, OverflowError) as error:
        parser.exit(1, f"Model selection failed: {error}\n")
    for selection in selections:
        print(f"{selection['target']}: {selection['prediction_column']} ({selection['variant']}), "
              f"validation RMSE {selection['validation_rmse']:.6g}")
    print(f"Saved {len(selections)} selections to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
