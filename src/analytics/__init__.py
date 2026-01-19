"""Analytics module for ad campaign data analysis."""

from .calculator import AnalyticalEngine
from .insights import Insight, InsightEngine, InsightThresholds, Severity
from .models import (
    Anomaly,
    AnomalyReport,
    CampaignKPIs,
    DayOfWeekStats,
    DeliveryPattern,
    DomainEfficiency,
    DomainStats,
    EfficiencyMetrics,
    GoalProgress,
    PerformanceGap,
    PlatformPerformance,
    TemporalStats,
    WeeklyStats,
    WeekOverWeekChange,
)

__all__ = [
    "AnalyticalEngine",
    "Anomaly",
    "AnomalyReport",
    "CampaignKPIs",
    "DayOfWeekStats",
    "DeliveryPattern",
    "DomainEfficiency",
    "DomainStats",
    "EfficiencyMetrics",
    "GoalProgress",
    "Insight",
    "InsightEngine",
    "InsightThresholds",
    "PerformanceGap",
    "PlatformPerformance",
    "Severity",
    "TemporalStats",
    "WeeklyStats",
    "WeekOverWeekChange",
]
