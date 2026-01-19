"""Output models for analytics calculations."""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class WeeklyStats:
    """Aggregated stats for a single week."""

    week_start: date
    impressions: int
    clicks: int
    spend: float
    avg_ctr: float
    avg_cpm: float
    avg_vcr: float | None = None
    avg_viewability: float | None = None


@dataclass(frozen=True)
class WeekOverWeekChange:
    """WoW delta for a single metric."""

    week_start: date
    metric_name: str
    current_value: float
    previous_value: float
    pct_change: float  # (current - previous) / previous
    is_spike: bool  # abs(pct_change) > spike_threshold


@dataclass(frozen=True)
class TemporalStats:
    """Complete temporal analysis output."""

    weekly_totals: list[WeeklyStats]
    wow_changes: list[WeekOverWeekChange]
    spikes: list[WeekOverWeekChange]  # Filtered to is_spike=True


@dataclass(frozen=True)
class DomainEfficiency:
    """Efficiency metrics for a single domain."""

    domain: str
    avg_ctr: float
    avg_vcr: float | None
    total_impressions: int
    total_spend: float
    ctr_vcr_correlation: float | None  # None if insufficient data
    weekend_lift: float | None  # (weekend - weekday) / weekday
    weekday_avg_ctr: float
    weekend_avg_ctr: float


@dataclass(frozen=True)
class PlatformPerformance:
    """Performance metrics by platform/device."""

    platform: str
    avg_ctr: float
    avg_vcr: float | None
    total_impressions: int
    total_spend: float


@dataclass(frozen=True)
class PerformanceGap:
    """Gap between best and worst performers."""

    metric_name: str
    max_platform: str
    max_value: float
    min_platform: str
    min_value: float
    gap_pct: float  # (max - min) / max


@dataclass(frozen=True)
class EfficiencyMetrics:
    """Complete efficiency analysis output."""

    domain_metrics: list[DomainEfficiency]
    platform_metrics: list[PlatformPerformance]
    performance_gaps: list[PerformanceGap]
    overall_ctr_vcr_correlation: float | None
    overall_weekend_lift: float | None


@dataclass(frozen=True)
class Anomaly:
    """Single anomaly detection result."""

    week_start: date
    metric_name: str
    value: float
    mean: float
    std: float
    z_score: float
    direction: Literal["above", "below"]


@dataclass(frozen=True)
class AnomalyReport:
    """Complete anomaly detection output."""

    anomalies: list[Anomaly]
    threshold_used: float  # z-score threshold (default 1.5)
    total_weeks_analyzed: int


@dataclass(frozen=True)
class GoalProgress:
    """Campaign goal completion status."""

    total_impressions: int
    campaign_goal: int
    completion_pct: float
    is_on_track: bool
    projected_completion_pct: float  # Based on time elapsed


@dataclass(frozen=True)
class DeliveryPattern:
    """Delivery pattern analysis."""

    is_back_loaded: bool
    last_quarter_delivery_pct: float  # Impressions in last 25% of time
    threshold_used: float  # Default 0.40
    daily_trend: Literal["increasing", "decreasing", "stable"]


@dataclass(frozen=True)
class CampaignKPIs:
    """Campaign-level KPIs (recomputed from raw data)."""

    total_impressions: int
    total_clicks: int
    total_spend: float
    ctr: float  # clicks / impressions
    cpm: float  # (spend / impressions) * 1000
    viewability_pct: float  # viewable_impressions / impressions
    vcr_pct: float | None  # weighted VCR


@dataclass(frozen=True)
class DayOfWeekStats:
    """Performance metrics for a single day of week."""

    day_of_week: str
    impressions: int
    clicks: int
    spend: float
    avg_ctr: float
    avg_vcr: float | None


@dataclass(frozen=True)
class DomainStats:
    """Enhanced domain stats with share calculations."""

    domain: str
    impressions: int
    clicks: int
    spend: float
    avg_ctr: float
    avg_cpm: float
    avg_vcr: float | None
    avg_viewability: float | None
    impression_share: float  # domain_impressions / total_impressions
    is_underperforming: bool  # high share + low metrics
