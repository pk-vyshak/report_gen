"""Custom exceptions for the ingestion pipeline."""

from typing import Any


class IngestionError(Exception):
    """Base exception for ingestion errors."""

    pass


class SchemaLoadError(IngestionError):
    """Failed to load schema configuration."""

    pass


class DataValidationError(IngestionError):
    """Data validation failed against Pydantic model."""

    def __init__(self, errors: list[dict[str, Any]], row_count: int):
        self.errors = errors
        self.row_count = row_count
        super().__init__(
            f"Validation failed for {len(errors)} of {row_count} rows. "
            f"First error: {errors[0] if errors else 'N/A'}"
        )


class ColumnMappingError(IngestionError):
    """Required column not found in source data."""

    def __init__(self, missing_columns: list[str], available_columns: list[str]):
        self.missing_columns = missing_columns
        self.available_columns = available_columns
        super().__init__(
            f"Missing required columns: {missing_columns}. "
            f"Available: {available_columns[:10]}..."
        )
