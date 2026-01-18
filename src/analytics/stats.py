"""Statistical functions using scipy for complex calculations."""

from typing import Literal

import numpy as np
import polars as pl
from scipy import stats


def pearson_correlation(
    df: pl.DataFrame,
    col_x: str,
    col_y: str,
    min_samples: int = 10,
) -> float | None:
    """Calculate Pearson correlation coefficient.

    Args:
        df: DataFrame with the columns
        col_x: First column name
        col_y: Second column name
        min_samples: Minimum non-null pairs required

    Returns:
        Correlation coefficient or None if insufficient data.
    """
    if col_x not in df.columns or col_y not in df.columns:
        return None

    valid = df.select([col_x, col_y]).drop_nulls()

    if len(valid) < min_samples:
        return None

    x = valid[col_x].to_numpy()
    y = valid[col_y].to_numpy()

    # Handle edge case of zero variance
    if np.std(x) == 0 or np.std(y) == 0:
        return None

    corr, _ = stats.pearsonr(x, y)
    return float(corr)


def detect_trend(
    values: list[float] | np.ndarray,
    p_threshold: float = 0.05,
    r_threshold: float = 0.3,
) -> Literal["increasing", "decreasing", "stable"]:
    """Detect trend direction using linear regression.

    Args:
        values: Ordered metric values (e.g., daily impressions)
        p_threshold: P-value threshold for significance
        r_threshold: Minimum R-value for meaningful trend

    Returns:
        Trend direction based on slope significance.
    """
    if len(values) < 3:
        return "stable"

    arr = np.array(values)
    x = np.arange(len(arr))

    slope, _, r_value, p_value, _ = stats.linregress(x, arr)

    # Significant trend if p < threshold and reasonable R-squared
    if p_value < p_threshold and abs(r_value) > r_threshold:
        return "increasing" if slope > 0 else "decreasing"
    return "stable"


def calculate_z_scores(values: list[float] | np.ndarray) -> np.ndarray:
    """Calculate z-scores for a list of values.

    Args:
        values: Metric values

    Returns:
        Array of z-scores (0 if std is 0).
    """
    arr = np.array(values)
    mean = np.mean(arr)
    std = np.std(arr)

    if std == 0:
        return np.zeros_like(arr)

    return (arr - mean) / std


def weekend_lift(
    weekend_values: list[float] | np.ndarray,
    weekday_values: list[float] | np.ndarray,
) -> float | None:
    """Calculate weekend performance lift over weekday.

    Formula: (weekend_avg - weekday_avg) / weekday_avg

    Args:
        weekend_values: Metric values for weekend days
        weekday_values: Metric values for weekdays

    Returns:
        Lift percentage or None if weekday avg is 0.
    """
    weekend_arr = np.array(weekend_values)
    weekday_arr = np.array(weekday_values)

    if len(weekend_arr) == 0 or len(weekday_arr) == 0:
        return None

    weekend_avg = np.mean(weekend_arr)
    weekday_avg = np.mean(weekday_arr)

    if weekday_avg == 0:
        return None

    return float((weekend_avg - weekday_avg) / weekday_avg)
