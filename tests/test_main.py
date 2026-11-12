import unittest
from unittest.mock import patch

import main


class MenuTests(unittest.TestCase):
    def test_default_counts_and_option_two_submits(self):
        for choice, dry_run in (("", True), ("2", False)):
            with self.subTest(choice=choice), \
                    patch("builtins.input", side_effect=[choice, "A2_Qin"]), \
                    patch("builtins.print"), \
                    patch.object(main, "setup_logger"), \
                    patch.object(main, "run_pipeline", return_value=0) as run:
                self.assertEqual(main.main([]), 0)
                run.assert_called_once_with(
                    sensor_alias="A2_Qin",
                    sensor=main.SENSORS["A2_Qin"],
                    data_window=main.DATA_WINDOW,
                    timestamp_columns=main.TIMESTAMP_COLUMNS,
                    dry_run=dry_run,
                    resume_from_id=None,
                    resume_after_id=None,
                )

    def test_csv_menu_and_pathless_flag_dispatch_to_loader(self):
        for argv, answers in (([], ["3", "clean data.csv"]),
                              (["--load-csv"], ["clean data.csv"])):
            with self.subTest(argv=argv), \
                    patch("builtins.input", side_effect=answers), \
                    patch("builtins.print"), \
                    patch.dict("os.environ", {"CSV_TIMESTAMP_FORMAT": "%d/%m/%Y %H:%M"}), \
                    patch.object(main, "setup_logger"), \
                    patch.object(main, "load_csv", return_value=1) as load:
                self.assertEqual(main.main(argv), 1)
                load.assert_called_once_with(
                    "clean data.csv", table="CleanedSensorData", schema="dbo",
                    timestamp_column="datetime", validate_only=False,
                    timestamp_format="%d/%m/%Y %H:%M",
                )

    def test_database_check_dispatches_without_additional_prompts(self):
        with patch("builtins.input", side_effect=["4"]) as prompt, \
                patch("builtins.print"), \
                patch.object(main, "check_database", return_value=1) as check:
            self.assertEqual(main.main([]), 1)
            prompt.assert_called_once_with("Operation [1]: ")
            check.assert_called_once_with()
