SENSORS_A1 = {
    "A1_Qin": {
        "source": {
            "schema": "dbo",
            "table": "T02_0506A_SCADA",
            "column": "A1_Qinto",
        },
        "fullTagName": "70flowa1qin",
        "description": "A1 Flow Rate In",
        "unit": "m3/hour",
        "group": "A1",
    },
    "A1_COD_in": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_SCADA",
            "column": "COD_in",
        },
        "fullTagName": "70coda1inf",
        "description": "A1 Influent COD",
        "unit": "mg/L",
        "group": "A1",
    },
    "A1_FQ_CH3OH": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_SCADA",
            "column": "FQ_CH3OH",
        },
        "fullTagName": "70flowa1methdosing",
        "description": "A1 Methanol Dosing Flow",
        "unit": "m3/hour",
        "group": "A1",
    },
    "A1_Q_r1": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_SCADA",
            "column": "Q_r1",
        },
        "fullTagName": "70flowa1internalrecycle",
        "description": "A1 Internal Recycle Flow",
        "unit": "m3/hour",
        "group": "A1",
    },
    "A1_NH3_N": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_SCADA",
            "column": "NH3_N",
        },
        "fullTagName": "70nh3_na1nh3n",
        "description": "A1 Influent NH3-N",
        "unit": "mg-N/L",
        "group": "A1",
    },
    "A1_A_PH": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_RealData",
            "column": "PH",
        },
        "fullTagName": "70pha1anoxic",
        "description": "A1 Anoxic Tank pH",
        "unit": None,
        "group": "A1",
    },
    "A1_A_ORP": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_RealData",
            "column": "ORP",
        },
        "fullTagName": "70orpa1anoxic",
        "description": "A1 Anoxic Tank ORP",
        "unit": "mV",
        "group": "A1",
    },
    "A1_A_DO": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_RealData",
            "column": "DO",
        },
        "fullTagName": "70doa1anoxic",
        "description": "A1 Anoxic Tank DO",
        "unit": "mg-O2/L",
        "group": "A1",
    },
    "A1_A_MLSS": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A1_RealData",
            "column": "MLSS",
        },
        "fullTagName": "70mlssa1anoxic",
        "description": "A1 Anoxic Tank MLSS",
        "unit": "mg/L",
        "group": "A1",
    },
    "A1_O_PH": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A1_RealData",
            "column": "PH",
        },
        "fullTagName": "70pha1aerobic",
        "description": "A1 Aerobic Tank pH",
        "unit": None,
        "group": "A1",
    },
    "A1_O_ORP": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A1_RealData",
            "column": "ORP",
        },
        "fullTagName": "70orpa1aerobic",
        "description": "A1 Aerobic Tank ORP",
        "unit": "mV",
        "group": "A1",
    },
    "A1_O_DO": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A1_RealData",
            "column": "DO",
        },
        "fullTagName": "70doa1aerobic",
        "description": "A1 Aerobic Tank DO",
        "unit": "mg-O2/L",
        "group": "A1",
    },
    "A1_O_MLSS": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A1_RealData",
            "column": "MLSS",
        },
        "fullTagName": "70mlssa1aerobic",
        "description": "A1 Aerobic Tank MLSS",
        "unit": "mg/L",
        "group": "A1",
    },
    "Q_A1_air": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A_Air",
            "column": "Q_A1_air",
        },
        "fullTagName": "70flowa1aerobic",
        "description": "A1 Aeration Flow Rate",
        "unit": "m3/min",
        "group": "A1",
    },
}


SENSORS_A2 = {
    "A2_Qin": {
        "source": {
            "schema": "dbo",
            "table": "T02_0506A_SCADA",
            "column": "A2_Qinto",
        },
        "fullTagName": "70flowa2qin",
        "description": "A2 Flow Rate In",
        "unit": "m3/hour",
        "group": "A2",
    },
    "A2_COD_in": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_SCADA",
            "column": "COD_in",
        },
        "fullTagName": "70coda2inf",
        "description": "A2 Influent COD",
        "unit": "mg/L",
        "group": "A2",
    },
    "A2_Q_r1": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_SCADA",
            "column": "Q_r1",
        },
        "fullTagName": "70flowa2internalrecycle",
        "description": "A2 Internal Recycle Flow",
        "unit": "m3/hour",
        "group": "A2",
    },
    "A2_FQ_CH3OH": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_SCADA",
            "column": "FQ_CH3OH",
        },
        "fullTagName": "70flowa2methdosing",
        "description": "A2 Methanol Dosing Flow",
        "unit": "m3/hour",
        "group": "A2",
    },
    "A2_NH3_N": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_SCADA",
            "column": "NH3_N",
        },
        "fullTagName": "70nh3_na2nh3n",
        "description": "A2 Influent NH3-N",
        "unit": "mg-N/L",
        "group": "A2",
    },
    "A2_A_PH": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_RealData",
            "column": "PH",
        },
        "fullTagName": "70pha2anoxic",
        "description": "A2 Anoxic Tank pH",
        "unit": None,
        "group": "A2",
    },
    "A2_A_ORP": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_RealData",
            "column": "ORP",
        },
        "fullTagName": "70orpa2anoxic",
        "description": "A2 Anoxic Tank ORP",
        "unit": "mV",
        "group": "A2",
    },
    "A2_A_DO": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_RealData",
            "column": "DO",
        },
        "fullTagName": "70doa2anoxic",
        "description": "A2 Anoxic Tank DO",
        "unit": "mg-O2/L",
        "group": "A2",
    },
    "A2_A_MLSS": {
        "source": {
            "schema": "dbo",
            "table": "T02_06A2_RealData",
            "column": "MLSS",
        },
        "fullTagName": "70mlssa2anoxic",
        "description": "A2 Anoxic Tank MLSS",
        "unit": "mg/L",
        "group": "A2",
    },
    "A2_O_PH": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A2_RealData",
            "column": "PH",
        },
        "fullTagName": "70pha2aerobic",
        "description": "A2 Aerobic Tank pH",
        "unit": None,
        "group": "A2",
    },
    "A2_O_ORP": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A2_RealData",
            "column": "ORP",
        },
        "fullTagName": "70orpa2aerobic",
        "description": "A2 Aerobic Tank ORP",
        "unit": "mV",
        "group": "A2",
    },
    "A2_O_DO": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A2_RealData",
            "column": "DO",
        },
        "fullTagName": "70doa2aerobic",
        "description": "A2 Aerobic Tank DO",
        "unit": "mg-O2/L",
        "group": "A2",
    },
    "A2_O_MLSS": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A2_RealData",
            "column": "MLSS",
        },
        "fullTagName": "70mlssa2aerobic",
        "description": "A2 Aerobic Tank MLSS",
        "unit": "mg/L",
        "group": "A2",
    },
    "Q_A2_air": {
        "source": {
            "schema": "dbo",
            "table": "T02_07A_Air",
            "column": "Q_A2_air",
        },
        "fullTagName": "70flowa2aerobic",
        "description": "A2 Aeration Flow Rate",
        "unit": "m3/min",
        "group": "A2",
    },
}


SENSORS_EFFLUENT = {
    "Eff_NH4_N": {
        "source": {
            "schema": "dbo",
            "table": "T02_08A_SCADA",
            "column": "NH4_N",
        },
        "fullTagName": "70nh4_neffammonia",
        "description": "Effluent NH4_N",
        "unit": "mg-N/L",
        "group": "Effluent",
    },
    "Eff_NO3_N": {
        "source": {
            "schema": "dbo",
            "table": "T02_08A_SCADA",
            "column": "NO3_N",
        },
        "fullTagName": "70no3_neffnitrate",
        "description": "Effluent NO3_N",
        "unit": "mg-N/L",
        "group": "Effluent",
    },
}

# Unified lookup for extraction and API payload construction
SENSORS = {**SENSORS_A1, **SENSORS_A2, **SENSORS_EFFLUENT}
