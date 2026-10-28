"""Causal sensor preparation and behavior audits shared by exploration notebooks."""
import numpy as np
import pandas as pd

def longest_run(mask):
    groups = mask.ne(mask.shift(fill_value=False)).cumsum()
    return int(mask.groupby(groups).sum().max()) if len(mask) else 0


def sensor_group(alias):
    name = alias.casefold()
    if "mlss" in name:
        return "mlss"
    if name.startswith("q_") or "qin" in name or "q_r" in name or "fq_ch3oh" in name:
        return "flow"
    if any(token in name for token in ("_do", "_ph", "_orp", "cod", "nh3", "nh4", "no3")):
        return "chemistry"
    return "other"


def prepare_sensors(raw, aliases, group_limits, overrides):
    if raw.empty or not raw.index.is_unique or not raw.index.is_monotonic_increasing:
        raise ValueError("Expected a nonempty, unique increasing minute grid.")
    expected = pd.date_range(raw.index[0], raw.index[-1], freq="min")
    if not raw.index.equals(expected):
        raise ValueError("Preparation requires a complete minute grid.")
    unknown = set(overrides) - set(raw.columns) - set(aliases.values())
    if unknown:
        raise ValueError(f"Unknown sensor overrides: {sorted(unknown)}")
    filled = raw.copy()
    ages = pd.DataFrame(index=raw.index)
    policies = []
    times = pd.Series(raw.index, index=raw.index)
    for column in raw:
        alias = aliases[column]
        group = sensor_group(alias)
        limit = overrides.get(column, overrides.get(alias, group_limits[group]))
        if isinstance(limit, bool) or not isinstance(limit, (int, np.integer)) or limit < 0:
            raise ValueError(f"Invalid maximum age for {column}: {limit}")
        last_seen = times.where(raw[column].notna()).ffill()
        ages[column] = (times - last_seen).dt.total_seconds().div(60)
        filled[column] = raw[column].ffill().where(ages[column].le(limit))
        policies.append({"sensor": column, "alias": alias, "group": group,
                         "max_age_minutes": limit})
    mask = raw.isna() & filled.notna()
    pd.testing.assert_frame_equal(filled.where(~mask), raw)
    return filled, mask, ages, pd.DataFrame(policies).set_index("sensor")



def summarize_sensor_behavior(raw, aliases, review_end):
    """Describe readings before a cutoff without using held-out observations."""
    review = raw.loc[raw.index < review_end]
    if review.empty:
        raise ValueError("Choose POLICY_REVIEW_END after the start of the selected window.")
    behavior_rows = []
    for column in review:
        values = review[column]
        observed = values.dropna()
        intervals = observed.index.to_series().diff().dt.total_seconds().div(60)
        same_as_previous = values.notna() & values.eq(values.shift())
        behavior_rows.append({
            "sensor": column, "alias": aliases[column],
            "observed": int(values.notna().sum()), "missing_percent": values.isna().mean() * 100,
            "longest_gap_minutes": longest_run(values.isna()),
            "median_observation_interval_minutes": intervals.median(),
            "unique_observed": observed.nunique(),
            "longest_identical_run_minutes": longest_run(same_as_previous) + int(not observed.empty),
            "median_absolute_change": values.diff().abs().median(),
            "negative_observations": int(values.lt(0).sum()),
            "constant_or_unobserved": observed.nunique() <= 1,
        })
    behavior_summary = pd.DataFrame(behavior_rows).set_index("sensor")
    return behavior_summary
