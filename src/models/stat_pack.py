"""StatPack - consolidated analytics output for LLM consumption."""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class StatPack:
    """Consolidated analytics output structured for LLM consumption.

    All data is pre-computed and JSON-serializable.
    """

    # Metadata
    generated_at: datetime
    campaign_id: int
    date_range: tuple[date, date]
    total_rows: int

    # Top-line aggregates
    total_impressions: int
    total_clicks: int
    total_spend: float
    avg_ctr: float
    avg_cpm: float
    avg_vcr: float | None
    avg_viewability: float | None

    # Goal tracking
    goal_progress: dict[str, Any]
    delivery_pattern: dict[str, Any]

    # Temporal analysis
    weekly_performance: list[dict[str, Any]]
    wow_changes: list[dict[str, Any]]
    spikes: list[dict[str, Any]]

    # Efficiency analysis
    domain_rankings: list[dict[str, Any]]
    platform_comparison: list[dict[str, Any]]
    performance_gaps: list[dict[str, Any]]
    weekend_vs_weekday: dict[str, Any]

    # Anomalies
    anomalies: list[dict[str, Any]]

    # Correlations
    correlations: dict[str, float | None]

    # Normalized metrics summary
    normalized_metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "meta": {
                "generated_at": self.generated_at.isoformat(),
                "campaign_id": self.campaign_id,
                "date_range": {
                    "start": self.date_range[0].isoformat(),
                    "end": self.date_range[1].isoformat(),
                },
                "total_rows": self.total_rows,
            },
            "aggregates": {
                "total_impressions": self.total_impressions,
                "total_clicks": self.total_clicks,
                "total_spend": round(self.total_spend, 2),
                "avg_ctr": round(self.avg_ctr * 100, 4),  # Convert to percentage
                "avg_cpm": round(self.avg_cpm, 2),
                "avg_vcr": round(self.avg_vcr * 100, 2) if self.avg_vcr else None,
                "avg_viewability": (
                    round(self.avg_viewability * 100, 2)
                    if self.avg_viewability
                    else None
                ),
            },
            "goal_tracking": {
                "progress": self.goal_progress,
                "delivery_pattern": self.delivery_pattern,
            },
            "temporal": {
                "weekly": self.weekly_performance,
                "wow_changes": self.wow_changes,
                "spikes": self.spikes,
            },
            "efficiency": {
                "top_domains": self.domain_rankings[:10],
                "bottom_domains": self.domain_rankings[-10:]
                if len(self.domain_rankings) > 10
                else [],
                "platforms": self.platform_comparison,
                "gaps": self.performance_gaps,
                "weekend_lift": self.weekend_vs_weekday,
            },
            "anomalies": self.anomalies,
            "correlations": {
                k: round(v, 4) if v is not None else None
                for k, v in self.correlations.items()
            },
            "normalized": self.normalized_metrics,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def get_executive_summary(self) -> dict[str, Any]:
        """Get condensed summary for executive overview.

        Returns key metrics only, suitable for report headers.
        """
        return {
            "campaign_id": self.campaign_id,
            "total_impressions": self.total_impressions,
            "total_spend": round(self.total_spend, 2),
            "goal_completion_pct": self.goal_progress.get("completion_pct"),
            "avg_ctr_pct": round(self.avg_ctr * 100, 2),
            "avg_vcr_pct": round(self.avg_vcr * 100, 2) if self.avg_vcr else None,
            "is_back_loaded": self.delivery_pattern.get("is_back_loaded"),
            "anomaly_count": len(self.anomalies),
            "top_spike": self.spikes[0] if self.spikes else None,
        }

    def get_insights_triggers(self) -> list[dict[str, str]]:
        """Generate insight triggers based on calculated metrics.

        Returns list of triggered insights with type and message.
        """
        triggers = []

        # Goal completion trigger
        completion_pct = self.goal_progress.get("completion_pct", 0)
        if completion_pct > 100:
            triggers.append(
                {
                    "type": "delivery_success",
                    "message": f"Campaign exceeded impression goal by {completion_pct - 100:.1f}%",
                }
            )
        elif completion_pct < 90:
            triggers.append(
                {
                    "type": "delivery_warning",
                    "message": f"Campaign at {completion_pct:.1f}% of goal",
                }
            )

        # Back-loaded delivery trigger
        if self.delivery_pattern.get("is_back_loaded"):
            last_q_pct = self.delivery_pattern.get("last_quarter_pct", 0)
            triggers.append(
                {
                    "type": "pacing_insight",
                    "message": f"Back-loaded delivery: {last_q_pct * 100:.1f}% in last 25% of campaign",
                }
            )

        # Weekend lift trigger
        lift = self.weekend_vs_weekday.get("lift")
        if lift and lift > 0.05:  # >5% lift
            triggers.append(
                {
                    "type": "timing_insight",
                    "message": f"Weekend engagement {lift * 100:.1f}% higher than weekdays",
                }
            )

        # Spike triggers
        for spike in self.spikes[:3]:  # Top 3 spikes
            pct = spike.get("pct_change", 0)
            direction = "spike" if pct > 0 else "drop"
            triggers.append(
                {
                    "type": "temporal_spike",
                    "message": f"{abs(pct) * 100:.1f}% {direction} in {spike.get('metric')} on {spike.get('week')}",
                }
            )

        # Anomaly triggers
        for anomaly in self.anomalies[:2]:  # Top 2 anomalies
            triggers.append(
                {
                    "type": "anomaly",
                    "message": f"Anomalous {anomaly.get('metric')} ({anomaly.get('direction')}) on {anomaly.get('week')}",
                }
            )

        # Platform gap trigger
        for gap in self.performance_gaps:
            if gap.get("gap_pct", 0) > 0.5:  # >50% gap
                triggers.append(
                    {
                        "type": "platform_gap",
                        "message": f"{gap.get('gap_pct') * 100:.0f}% {gap.get('metric')} gap between {gap.get('max_platform')} and {gap.get('min_platform')}",
                    }
                )

        return triggers
