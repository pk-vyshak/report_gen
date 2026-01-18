"""Data cleaning functions using Polars expressions."""

import polars as pl


def clean_currency_column(col_name: str) -> pl.Expr:
    """Remove commas and currency symbols, convert to float.

    Handles Indian notation (45,00,000) by stripping all commas.
    """
    return (
        pl.col(col_name)
        .cast(pl.Utf8)
        .str.replace_all(",", "")
        .str.replace_all("$", "")
        .str.replace_all("₹", "")
        .str.strip_chars()
        .cast(pl.Float64)
        .alias(col_name)
    )


def clean_percentage_column(col_name: str) -> pl.Expr:
    """Remove % symbol and convert to decimal (100% -> 1.0)."""
    return (
        pl.col(col_name)
        .cast(pl.Utf8)
        .str.replace("%", "")
        .str.strip_chars()
        .cast(pl.Float64)
        .truediv(100)
        .alias(col_name)
    )


def clean_datetime_column(col_name: str, dtype: pl.DataType) -> pl.Expr:
    """Convert datetime/date column to date.

    Handles:
    - Already parsed Date/Datetime (from Excel)
    - String format 'MM/DD/YY HH:MM'
    """
    col = pl.col(col_name)

    if dtype == pl.Date:
        return col.alias(col_name)  # Already a date
    elif dtype.base_type() == pl.Datetime:
        return col.dt.date().alias(col_name)
    else:
        # String - parse it
        return (
            col.cast(pl.Utf8)
            .str.to_datetime("%m/%d/%y %H:%M", strict=False)
            .dt.date()
            .alias(col_name)
        )


def clean_date_column(col_name: str, dtype: pl.DataType) -> pl.Expr:
    """Convert to date, handling pre-parsed dates from Excel."""
    col = pl.col(col_name)

    if dtype == pl.Date:
        return col.alias(col_name)
    elif dtype.base_type() == pl.Datetime:
        return col.dt.date().alias(col_name)
    else:
        return (
            col.cast(pl.Utf8)
            .str.to_date("%m/%d/%y", strict=False)
            .alias(col_name)
        )


def clean_integer_column(col_name: str) -> pl.Expr:
    """Convert to integer, handling commas and float strings like '3.0'."""
    return (
        pl.col(col_name)
        .cast(pl.Utf8)
        .str.replace_all(",", "")
        .str.strip_chars()
        .cast(pl.Float64)  # Handle "3.0" style strings
        .cast(pl.Int64)
        .alias(col_name)
    )


def clean_string_column(col_name: str) -> pl.Expr:
    """Strip whitespace and normalize empty strings to null."""
    return (
        pl.col(col_name)
        .cast(pl.Utf8)
        .str.strip_chars()
        .replace("", None)
        .alias(col_name)
    )


def clean_float_column(col_name: str) -> pl.Expr:
    """Convert to float, handling commas and string representation."""
    return (
        pl.col(col_name)
        .cast(pl.Utf8)
        .str.replace_all(",", "")
        .str.strip_chars()
        .cast(pl.Float64)
        .alias(col_name)
    )


def apply_cleaning(
    df: pl.DataFrame,
    currency_cols: list[str],
    percentage_cols: list[str],
    datetime_cols: list[str],
    date_cols: list[str],
    integer_cols: list[str],
    float_cols: list[str] | None = None,
) -> pl.DataFrame:
    """Apply all cleaning transformations to DataFrame.

    Only cleans columns that exist in the DataFrame.
    """
    existing_cols = set(df.columns)
    schema = df.schema
    exprs: list[pl.Expr] = []

    for col in currency_cols:
        if col in existing_cols:
            exprs.append(clean_currency_column(col))

    for col in percentage_cols:
        if col in existing_cols:
            exprs.append(clean_percentage_column(col))

    for col in datetime_cols:
        if col in existing_cols:
            exprs.append(clean_datetime_column(col, schema[col]))

    for col in date_cols:
        if col in existing_cols:
            exprs.append(clean_date_column(col, schema[col]))

    for col in integer_cols:
        if col in existing_cols:
            exprs.append(clean_integer_column(col))

    for col in float_cols or []:
        if col in existing_cols:
            exprs.append(clean_float_column(col))

    if exprs:
        return df.with_columns(exprs)
    return df
