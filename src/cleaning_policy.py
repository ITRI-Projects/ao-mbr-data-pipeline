"""Sensor limits and gap handling for the SQL cleaning command."""

TANK_SENSORS = ("A_DO", "O_DO", "A_MLSS", "O_MLSS", "A_ORP", "O_ORP", "A_PH", "O_PH")
CONSTANT_SENSORS = ("A1_NH3_N", "A2_NH3_N", "Eff_NO3_N")
SENSOR_BOUNDS = {
    "A1_COD_in": (0, None),
    "A2_COD_in": (0, None),
    "A1_Q_air": (0, None),
    "A2_Q_air": (0, None),
    "A1_Qin": (0, None),
    "A2_Qin": (0, None),
    "A1_FQ_CH3OH": (0, None),
    "A2_FQ_CH3OH": (0, None),
    "A1_Q_r1": (0, None),
    "A2_Q_r1": (0, None),
    "A1_NH3_N": (0, None),
    "A2_NH3_N": (0, None),
    "Eff_NH4_N": (0, None),
    "Eff_NO3_N": (0, None),
    "A_DO": (0, 25),
    "O_DO": (0, 25),
    "A_MLSS": (0, None),
    "O_MLSS": (0, None),
    "A_PH": (0, 14),
    "O_PH": (0, 14),
}

FORWARD_FILL_MINUTES = 10
FREEZE_SENSOR_FRACTION = 0.80
SYNCHRONIZED_FREEZE_MINUTES = 60
FLATLINE_MINUTES = 60
SHORT_REPAIR_MINUTES = 10
