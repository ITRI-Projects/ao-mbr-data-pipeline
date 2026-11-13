import math
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


def build_import_payload(sensor, reading):
    """Build the measurement fields; APIClient adds credentials privately."""
    value = reading["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Missing or non-numeric sensor value")
    value = serialize_value(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite sensor value")
    return {
        "fullTagName": sensor["fullTagName"],
        "datetime": reading["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
        "value": value,
    }
