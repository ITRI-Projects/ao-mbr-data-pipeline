from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import pyodbc

from src import forecast_loader
from src.training import select_model


ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"


class ForecastLoaderTests(unittest.TestCase):
    def test_preview_of_saved_assets_skips_connection_by_default(self):
        with TemporaryDirectory() as folder:
            selection = Path(folder) / "selection.json"
            select_model.save_selections(select_model.select_models(ASSETS), selection)
            forecasts = forecast_loader.read_selection(selection)
            rows = forecast_loader.align_predictions(forecasts)
            self.assertEqual(len(rows), 365)
            self.assertEqual(sum(None not in row for row in rows), 358)
            self.assertEqual([len(forecast.values) for forecast in forecasts], [362, 362, 365, 365, 361, 361])

            with patch("builtins.input", return_value="") as prompt, patch("builtins.print"), \
                    patch.object(forecast_loader, "get_connection") as connect:
                self.assertEqual(forecast_loader.main(["--selection", str(selection)]), 0)
            prompt.assert_called_once()
            connect.assert_not_called()

    def test_confirmed_import_uses_the_previewed_rows_and_commits(self):
        forecast = forecast_loader.SelectedForecast("Eff_NH4_N", "LSTM", "tuned", 0.1,
                                                    {datetime(2026, 4, 21): 1.5})
        connection = Mock()
        cursor = connection.cursor.return_value
        with patch.object(forecast_loader, "read_selection", return_value=[forecast]), \
                patch.object(forecast_loader, "print_preview") as preview, \
                patch.object(forecast_loader, "get_connection", return_value=connection) as connect, \
                patch("builtins.print"):
            def confirm(_):
                preview.assert_called_once()
                connect.assert_not_called()
                return "yes"

            with patch("builtins.input", side_effect=confirm):
                self.assertEqual(forecast_loader.main([]), 0)

        cursor.executemany.assert_called_once_with(
            "INSERT INTO #ForecastImport ([target_time], [Eff_NH4_N]) VALUES (?, ?)",
            [(datetime(2026, 4, 21), 1.5)],
        )
        self.assertIn("MERGE dbo.ForecastPredictions", cursor.execute.call_args.args[0])
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once_with()

    def test_failed_write_rolls_back(self):
        forecast = forecast_loader.SelectedForecast("Eff_NH4_N", "LSTM", "tuned", 0.1,
                                                    {datetime(2026, 4, 21): 1.5})
        connection = Mock()
        connection.cursor.return_value.executemany.side_effect = pyodbc.Error("42000")
        with patch.object(forecast_loader, "get_connection", return_value=connection):
            with self.assertRaises(pyodbc.Error):
                forecast_loader.load_predictions([forecast], forecast_loader.align_predictions([forecast]))
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()
