"""Filenames shared by the cleaning exporter and training reader."""

PREPARED_CSV = "data_filled.csv"
FILL_MASK_CSV = "data_filled_mask.csv"
SENSOR_FAULT_MASK_CSV = "data_sensor_fault_mask.csv"
SHORT_REPAIR_MASK_CSV = "data_short_error_replacement_mask.csv"
SYNCHRONIZED_MASK_CSV = "data_synchronized_corrupt_mask.csv"

MASK_FILENAMES = (
    FILL_MASK_CSV,
    SENSOR_FAULT_MASK_CSV,
    SHORT_REPAIR_MASK_CSV,
    SYNCHRONIZED_MASK_CSV,
)
