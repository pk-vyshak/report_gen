"""Data enrichment functions - add derived columns."""

import polars as pl

WEEKEND_DAYS = {"Saturday", "Sunday"}


def add_week_start(df: pl.DataFrame, date_col: str = "report_day") -> pl.DataFrame:
    """Add week_start column (Monday of that week).

    Uses ISO week definition where Monday is day 1.
    """
    return df.with_columns(
        pl.col(date_col).dt.truncate("1w").alias("week_start")
    )


def add_is_weekend(df: pl.DataFrame, day_col: str = "day_of_week") -> pl.DataFrame:
    """Add is_weekend boolean based on day of week string."""
    return df.with_columns(
        pl.col(day_col).is_in(list(WEEKEND_DAYS)).alias("is_weekend")
    )


def enrich(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all enrichment transformations."""
    df = add_week_start(df)
    df = add_is_weekend(df)
    return df
