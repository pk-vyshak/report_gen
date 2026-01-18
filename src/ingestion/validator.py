"""Validation utilities for the ingestion pipeline."""

from typing import Any

import polars as pl
from pydantic import ValidationError

from ..exceptions import DataValidationError
from ..models.domain_report import DomainReportRow


def validate_dataframe(df: pl.DataFrame) -> None:
    """Validate each row against Pydantic model.

    Args:
        df: Cleaned and enriched DataFrame

    Raises:
        DataValidationError: If any rows fail validation
    """
    errors: list[dict[str, Any]] = []
    rows = df.to_dicts()

    for i, row in enumerate(rows):
        try:
            DomainReportRow.model_validate(row)
        except ValidationError as e:
            errors.append({"row": i, "errors": e.errors()})

    if errors:
        raise DataValidationError(errors, len(rows))


def validate_sample(df: pl.DataFrame, sample_size: int = 100) -> None:
    """Validate a random sample for quick sanity checks.

    Useful for large datasets where full validation is slow.
    """
    sample = df.sample(min(sample_size, len(df)))
    validate_dataframe(sample)
