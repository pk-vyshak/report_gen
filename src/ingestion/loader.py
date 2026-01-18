"""Main data ingestion pipeline."""

from pathlib import Path
from typing import Any

import polars as pl
import yaml
from pydantic import ValidationError

from ..exceptions import ColumnMappingError, DataValidationError, SchemaLoadError
from ..models.domain_report import DomainReportRow
from .cleaner import apply_cleaning
from .enricher import enrich


class DataIngestionPipeline:
    """Pipeline for loading, cleaning, validating, and enriching ad data.

    Usage:
        pipeline = DataIngestionPipeline(Path("src/config/schema_registry.yaml"))
        df = pipeline.ingest(Path("Files/Input/Domain Report.xlsx"))
    """

    def __init__(self, schema_path: Path):
        self.schema = self._load_schema(schema_path)

    def _load_schema(self, path: Path) -> dict[str, Any]:
        """Load schema configuration from YAML."""
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise SchemaLoadError(f"Failed to load schema from {path}: {e}") from e

    def ingest(
        self,
        file_path: Path,
        schema_name: str = "domain_report",
        validate: bool = True,
    ) -> pl.DataFrame:
        """Full pipeline: Load -> Rename -> Clean -> Enrich -> Validate.

        Args:
            file_path: Path to Excel or CSV file
            schema_name: Key in schema registry (default: domain_report)
            validate: Whether to run Pydantic validation (default: True)

        Returns:
            Cleaned and enriched Polars DataFrame
        """
        schema = self.schema[schema_name]

        # Load raw data
        df = self._load(file_path)

        # Rename columns to internal names
        df = self._rename_columns(df, schema["column_map"])

        # Apply type-specific cleaning
        df = self._clean(df, schema)

        # Add derived columns
        df = enrich(df)

        # Validate against Pydantic model
        if validate:
            self._validate(df)

        return df

    def _load(self, path: Path) -> pl.DataFrame:
        """Load data from Excel or CSV."""
        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            # Provide schema overrides for columns that can't be inferred
            # (typically empty or sparse columns in Excel files)
            schema_overrides = {
                "Line Items Flight End Date": pl.String,
                "Line Items Flight Name": pl.String,
                "Line Items Flight Start Date": pl.String,
                "Domain Report Video Complete Percent": pl.String,
            }
            return pl.read_excel(path, schema_overrides=schema_overrides)
        elif suffix == ".csv":
            return pl.read_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _rename_columns(
        self, df: pl.DataFrame, column_map: dict[str, str]
    ) -> pl.DataFrame:
        """Rename columns from raw names to internal names.

        column_map: {internal_name: raw_column_name}
        """
        # Invert map: {raw_name: internal_name}
        raw_to_internal = {v: k for k, v in column_map.items()}

        # Check for missing required columns
        available = set(df.columns)
        expected = set(raw_to_internal.keys())
        missing = expected - available

        if missing:
            raise ColumnMappingError(list(missing), list(available))

        # Rename only columns that exist in the map
        rename_dict = {
            raw: internal
            for raw, internal in raw_to_internal.items()
            if raw in available
        }

        return df.rename(rename_dict)

    def _clean(self, df: pl.DataFrame, schema: dict[str, Any]) -> pl.DataFrame:
        """Apply cleaning transformations based on schema."""
        return apply_cleaning(
            df,
            currency_cols=schema.get("currency_columns", []),
            percentage_cols=schema.get("percentage_columns", []),
            datetime_cols=schema.get("date_columns", []),
            date_cols=schema.get("date_only_columns", []),
            integer_cols=schema.get("integer_columns", []),
        )

    def _validate(self, df: pl.DataFrame) -> None:
        """Validate each row against Pydantic model.

        Collects all errors before raising, for better debugging.
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
