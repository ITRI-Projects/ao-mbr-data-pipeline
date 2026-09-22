PREDICTIONS = {
    "effluent_nh3_n": {
        "data_window": {
            "start": "2026-03-24 00:00:00",
            "end": "2026-04-23 13:00:00",
        },
        "forecast_window": {
            "start": "2026-04-18 14:00:00",
            "end": "2026-04-23 13:00:00",
            "frequency": "1h",
        },
        "features": {
            "A1_Q_in": {
                "table": "T02_0506A_SCADA",
                "column": "A1_Q_in",
            },
            "A1_MLSS": {
                "table": "T02_07A1_RealData",
                "column": "A1_MLSS",
            },
            "A1_NH3_N": {
                "table": "T02_06A1_SCADA",
                "column": "A1_NH3_N",
            },
            "A1_Q_air": {
                "table": "T02_07A_air",
                "column": "A1_Q_air",
            },
        },
        "target": {
            "name": "Eff_NH3_N",
            "table": "T02_09A_outlet_SCADA",
            "column": "Eff_NH3-N",
        },
        "timestamp": {
            "id_column": "DATA_ID",
            "date_column": "DATA_DATE",
            "time_column": "DATA_TIME",
        },
    }
}
