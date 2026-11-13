"""Interactive menu and command arguments."""

from config.sensors import SENSORS
from src.settings import (
    CLEANED_SENSOR_TABLE,
    CLEANING_OUTPUT_DIR,
    DEFAULT_SCHEMA,
    FORECAST_ASSETS_DIR,
    FORECAST_SELECTION_PATH,
)


def prompt_operation():
    print("\nChoose an operation:")
    for number, (label, _) in MENU.items():
        print(f"  {number}. {label}")
    print("  q. Quit")
    while True:
        choice = input("Operation [1]: ").strip().lower() or "1"
        if choice == "q":
            return None
        if choice in MENU:
            return MENU[choice][1]
        print("Enter a listed operation number or q.")


def prompt_sensor():
    aliases = list(SENSORS)
    print("\nSelect a sensor column:")
    previous_group = None
    for number, alias in enumerate(aliases, 1):
        sensor = SENSORS[alias]
        group = sensor.get("group", "Other")
        if group != previous_group:
            print(f"\n{group}:")
            previous_group = group
        source = sensor["source"]
        print(f"  {number}. {alias} — {source['table']}.{source['column']} — {sensor.get('description', '')}")
    while True:
        choice = input("Sensor number or alias, q to quit: ").strip()
        if choice.lower() == "q":
            return None
        if choice in SENSORS:
            return choice
        if choice.isdecimal() and 1 <= int(choice) <= len(aliases):
            return aliases[int(choice) - 1]
        print("Enter a listed sensor number or alias, or q.")


def prompt_train_command(parser):
    data = input("Prepared training CSV path: ").strip()
    if not data:
        parser.error("Prepared training CSV path is required")
    output = input("Baseline output directory: ").strip()
    if not output:
        parser.error("Baseline output directory is required")
    target = input("Target model name (e.g. eff_nh3_n, Enter for all available targets): ").strip()
    command = ["-m", "src.training.train", "--data", data, "--output", output]
    if target:
        command.extend(["--targets", target])
    return command


def prompt_tune_command(parser):
    source = input("Baseline output directory from a completed single-target training run: ").strip()
    if not source:
        parser.error("Single-target baseline output directory is required")
    output = input("Separate tuned output directory: ").strip()
    if not output:
        parser.error("Tuned output directory is required")
    return ["-m", "src.training.tune", "--source", source, "--output", output]


def prompt_cleaning_command(_parser):
    command = ["-m", "src.cleaning"]
    for flag, prompt in (
        ("--table", f"SQL table [{DEFAULT_SCHEMA}.{CLEANED_SENSOR_TABLE}]: "),
        ("--start", "First minute (YYYY-MM-DD HH:MM, Enter for earliest): "),
        ("--end", "Last minute (YYYY-MM-DD HH:MM, Enter for latest): "),
        ("--output", f"Export parent directory [{CLEANING_OUTPUT_DIR}]: "),
    ):
        value = input(prompt).strip()
        if value:
            command.extend([flag, value])
    return command


def prompt_model_selection_command(_parser):
    command = ["-m", "src.training.select_model"]
    assets = input(f"Saved forecast directory [{FORECAST_ASSETS_DIR}]: ").strip()
    output = input(f"Selection JSON path [{FORECAST_SELECTION_PATH}]: ").strip()
    if assets:
        command.extend(["--assets", assets])
    if output:
        command.extend(["--output", output])
    return command


def prompt_forecast_load_command(_parser):
    command = ["-m", "src.etl.forecast_loader"]
    selection = input(f"Selection JSON path [{FORECAST_SELECTION_PATH}]: ").strip()
    if selection:
        command.extend(["--selection", selection])
    return command


MENU = {
    "1": ("Dry run (count only)", "dry_run"),
    "2": ("Actual API submission", "submit"),
    "3": ("Load cleaned CSV into database", "load_csv"),
    "4": ("Check SQL Server connection and permissions", "db_check"),
    "5": ("Train forecasting models", prompt_train_command),
    "6": ("Tune a single-target baseline", prompt_tune_command),
    "7": ("Prepare loaded SQL sensor data for training", prompt_cleaning_command),
    "8": ("Select one forecast model per target", prompt_model_selection_command),
    "9": ("Review selected forecasts and optionally load them into SQL Server", prompt_forecast_load_command),
}
