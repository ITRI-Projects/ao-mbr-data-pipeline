"""Prepare the complete local history while preserving the existing test inputs."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from config.sensors import SENSORS
from .sensor_preparation import prepare_sensors


def main():
    source = Path("notebooks/data/google_drive_full_raw.csv")
    output = Path("data/training/expanded_history_inputs")
    raw = pd.read_csv(source, index_col="datetime", parse_dates=True).sort_index()
    raw = raw.loc[raw.index < pd.Timestamp("2026-04-24")]
    if not raw.index.is_unique or not raw.index.equals(raw.index.floor("min")):
        raise ValueError("Expected unique minute-aligned observations")
    raw = raw.reindex(pd.date_range(raw.index.min(), "2026-04-23 23:59", freq="min", name="datetime"))
    by_tag = {s["fullTagName"].casefold(): alias for alias, s in SENSORS.items()}
    aliases = {c: by_tag.get(c.casefold(), c) for c in raw}
    filled, mask, ages, policy = prepare_sensors(
        raw, aliases, {"flow": 2, "chemistry": 5, "mlss": 15, "other": 0}, {})
    filled, mask = filled.rename(columns=aliases), mask.rename(columns=aliases)
    # Compare every held-out minute, including missingness, before writing anything.
    for frame, filename in ((filled, "data_filled.csv"), (mask, "data_filled_mask.csv")):
        original = pd.read_csv(Path("notebooks/data") / filename, index_col="datetime", parse_dates=True)
        pd.testing.assert_frame_equal(frame.loc["2026-04-21":"2026-04-23"],
                                      original.loc["2026-04-21":"2026-04-23"], check_freq=False)
    output.mkdir(parents=True, exist_ok=True)
    filled.to_csv(output / "data_filled.csv", index_label="datetime")
    mask.to_csv(output / "data_filled_mask.csv", index_label="datetime")
    ages.rename(columns=aliases).to_csv(output / "measurement_age.csv")
    policy.to_csv(output / "preparation_policy.csv")
    metadata = {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "start": str(raw.index.min()), "end": str(raw.index.max()),
                "train_end_exclusive": "2026-04-18", "test_start": "2026-04-21",
                "test_end_exclusive": "2026-04-24", "test_inputs_and_mask_equal_original": True}
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
