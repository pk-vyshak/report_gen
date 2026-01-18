"""Analytics module for ad campaign data analysis."""

from .calculator import AnalyticalEngine
from .models import (
    Anomaly,
    AnomalyReport,
    DeliveryPattern,
    DomainEfficiency,
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
    "DeliveryPattern",
    "DomainEfficiency",
    "EfficiencyMetrics",
    "GoalProgress",
    "PerformanceGap",
    "PlatformPerformance",
    "TemporalStats",
    "WeeklyStats",
    "WeekOverWeekChange",
]
