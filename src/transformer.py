from datetime import date, datetime, time
from decimal import Decimal


def serialize_value(value):
    if value is None:
        return None

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    return value


def build_prediction_payload(
    prediction_name,
    forecast_time,
    features,
):
    return {
        "prediction": prediction_name,
        "forecast_time": forecast_time.isoformat(),
        "features": {key: serialize_value(value) for key, value in features.items()},
    }
