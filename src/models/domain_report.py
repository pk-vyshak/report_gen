"""Pydantic models for domain report validation."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DomainReportRow(BaseModel):
    """Single row from domain report after cleaning.

    All percentages stored as decimals (0.05 not 5%).
    All currency values stored as floats without formatting.
    """

    model_config = ConfigDict(strict=True)

    # Campaign info
    advertiser_name: str
    campaign_id: int
    campaign_start: date
    campaign_end: date
    campaign_budget: float

    # Creative info
    creative_size: str
    creative_name: str
    creative_id: int

    # Flight info (optional - often empty)
    flight_end: Optional[date] = None
    flight_name: Optional[str] = None
    flight_start: Optional[date] = None
    flight_id: int

    # Line item info
    line_item_budget_type: str
    line_item_daily_budget: float
    line_item_end: date
    line_item_name: str
    line_item_id: int
    line_item_start: date

    # Temporal fields
    report_day: date
    day_of_week: str
    month: str
    week: date
    year: int

    # Inventory info
    inventory_source: str
    platform_device_type: str
    domain: str

    # Performance metrics
    cpm: float
    impressions: int
    clicks: int
    ctr: float  # Decimal: 0.05 = 5%
    spend: float
    frequency: Optional[int] = None  # Can be null
    reach: int
    video_complete_pct: Optional[float] = None  # Often empty
    video_completes: int
    viewability_pct: Optional[float] = None  # Can be null
    viewable_impressions: int

    # Enriched fields (added by pipeline)
    week_start: date
    is_weekend: bool
