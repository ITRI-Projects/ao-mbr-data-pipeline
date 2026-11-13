import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.training import select_model


ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"


class ModelSelectionTests(unittest.TestCase):
    def test_assets_produce_one_verifiable_selection_per_target(self):
        selections = select_model.select_models(ASSETS)
        expected = {
            "Eff_NH4_N": ("LSTM", "tuned"),
            "Eff_NO3_N": ("Ridge", "raw"),
            "A1_FQ_CH3OH": ("Random Forest", "tuned"),
            "A2_FQ_CH3OH": ("Random Forest", "tuned"),
            "A1_Q_air": ("Ridge", "raw"),
            "A2_Q_air": ("LSTM", "tuned"),
        }
        self.assertEqual(len(selections), len(expected))
        self.assertEqual(
            {row["target"]: (row["prediction_column"], row["variant"]) for row in selections},
            expected,
        )
        with TemporaryDirectory() as folder:
            output = Path(folder) / "selection.json"
            select_model.save_selections(selections, output)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(document["selection_split"], "validation")
            self.assertEqual(len(document["selections"]), len(expected))
            for row in document["selections"]:
                source = output.parent / row["predictions_csv"]
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), row["predictions_sha256"])
                with source.open(encoding="utf-8-sig", newline="") as stream:
                    self.assertIn(row["prediction_column"], next(csv.reader(stream)))

    def test_mismatched_validation_labels_prevent_selection(self):
        runs = select_model.discover_runs(ASSETS)
        tuned = runs["a1_air_flow"]["tuned"]
        labels = tuned.labels.copy()
        labels[next(iter(labels))] += 1
        runs["a1_air_flow"]["tuned"] = replace(tuned, labels=labels)
        with patch.object(select_model, "discover_runs", return_value=runs):
            with self.assertRaisesRegex(ValueError, "different validation timestamps or labels"):
                select_model.select_models(ASSETS)
