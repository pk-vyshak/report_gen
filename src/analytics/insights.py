"""Rule-based insight generation for ad campaign analysis."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import polars as pl


class Severity(str, Enum):
    """Insight severity levels."""

    GREEN = "green"  # Good / On track
    AMBER = "amber"  # Warning / Needs attention
    RED = "red"  # Critical / Action required


@dataclass(frozen=True)
class Insight:
    """Single insight with description, severity, and recommendation."""

    rule_id: str
    description: str
    severity: Severity
    recommendation: str
    metrics: dict[str, Any] | None = None


@dataclass
class InsightThresholds:
    """Configurable thresholds for insight rules.

    All percentage values are expressed as decimals (0.5 = 50%).
    """

    # Pacing Spike: Week impressions >= +X% vs average week
    pacing_spike_pct: float = 0.50  # 50%

    # CTR Anomaly: Week CTR <= X% of campaign average
    ctr_anomaly_pct: float = 0.70  # 70%

    # CTR Recovery: Later week CTR >= X% of average
    ctr_recovery_pct: float = 1.10  # 110%

    # VCR Drop: >= X percentage point decline
    vcr_drop_points: float = 0.03  # 3 percentage points

    # Platform/Device Concentration: Single platform >= X% of impressions
    platform_concentration_pct: float = 0.80  # 80%

    # Domain Concentration: Top domain >= X% impressions
    top_domain_concentration_pct: float = 0.40  # 40%

    # Domain Concentration: Top-5 >= X% impressions
    top5_domain_concentration_pct: float = 0.70  # 70%


class InsightEngine:
    """Rule-based insight generator.

    Applies business rules to detect patterns and generate actionable insights.

    Usage:
        engine = InsightEngine(df, thresholds=InsightThresholds())
        insights = engine.generate_all_insights()
    """

    def __init__(
        self,
        df: pl.DataFrame,
        thresholds: InsightThresholds | None = None,
    ):
        self.df = df
        self.thresholds = thresholds or InsightThresholds()

    def generate_all_insights(self) -> list[Insight]:
        """Run all insight rules and return detected insights."""
        insights: list[Insight] = []

        insights.extend(self._check_pacing_spike())
        insights.extend(self._check_ctr_anomaly())
        insights.extend(self._check_ctr_recovery())
        insights.extend(self._check_vcr_drop())
        insights.extend(self._check_platform_concentration())
        insights.extend(self._check_domain_concentration())

        return insights

    def _check_pacing_spike(self) -> list[Insight]:
        """Check for weeks with impressions >= +50% vs average week."""
        insights: list[Insight] = []

        weekly = (
            self.df.group_by("week_start")
            .agg(pl.col("impressions").sum().alias("weekly_impressions"))
            .sort("week_start")
        )

        avg_impressions = weekly["weekly_impressions"].mean()
        if avg_impressions is None or avg_impressions == 0:
            return insights

        threshold = avg_impressions * (1 + self.thresholds.pacing_spike_pct)

        for row in weekly.to_dicts():
            week_imps = row["weekly_impressions"]
            pct_vs_avg = (week_imps - avg_impressions) / avg_impressions

            if week_imps >= threshold:
                insights.append(
                    Insight(
                        rule_id="pacing_spike",
                        description=(
                            f"Week {row['week_start']} had a {pct_vs_avg * 100:.1f}% "
                            f"spike in impressions vs campaign average"
                        ),
                        severity=Severity.AMBER,
                        recommendation=(
                            "Review pacing strategy. High-volume weeks may indicate "
                            "back-loaded delivery or opportunistic bidding. Consider "
                            "smoothing delivery for more consistent performance."
                        ),
                        metrics={
                            "week": row["week_start"].isoformat(),
                            "impressions": week_imps,
                            "avg_impressions": round(avg_impressions),
                            "pct_vs_avg": round(pct_vs_avg * 100, 1),
                        },
                    )
                )

        return insights

    def _check_ctr_anomaly(self) -> list[Insight]:
        """Check for weeks with CTR <= 70% of campaign average."""
        insights: list[Insight] = []

        weekly = (
            self.df.group_by("week_start")
            .agg(
                [
                    pl.col("clicks").sum().alias("total_clicks"),
                    pl.col("impressions").sum().alias("total_impressions"),
                ]
            )
            .with_columns(
                (pl.col("total_clicks") / pl.col("total_impressions")).alias(
                    "weekly_ctr"
                )
            )
            .sort("week_start")
        )

        # Campaign average CTR (recomputed)
        total_clicks = self.df["clicks"].sum()
        total_impressions = self.df["impressions"].sum()
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0

        if avg_ctr == 0:
            return insights

        threshold = avg_ctr * self.thresholds.ctr_anomaly_pct

        for row in weekly.to_dicts():
            weekly_ctr = row["weekly_ctr"]
            if weekly_ctr is None:
                continue

            pct_of_avg = weekly_ctr / avg_ctr if avg_ctr > 0 else 0

            if weekly_ctr <= threshold:
                insights.append(
                    Insight(
                        rule_id="ctr_anomaly",
                        description=(
                            f"Week {row['week_start']} CTR ({weekly_ctr * 100:.3f}%) "
                            f"was {(1 - pct_of_avg) * 100:.1f}% below campaign average"
                        ),
                        severity=Severity.RED,
                        recommendation=(
                            "Investigate creative fatigue, audience saturation, or "
                            "inventory quality issues. Consider A/B testing new "
                            "creatives or adjusting targeting parameters."
                        ),
                        metrics={
                            "week": row["week_start"].isoformat(),
                            "weekly_ctr": round(weekly_ctr * 100, 4),
                            "avg_ctr": round(avg_ctr * 100, 4),
                            "pct_of_avg": round(pct_of_avg * 100, 1),
                        },
                    )
                )

        return insights

    def _check_ctr_recovery(self) -> list[Insight]:
        """Check for later weeks with CTR >= 110% of average (recovery)."""
        insights: list[Insight] = []

        weekly = (
            self.df.group_by("week_start")
            .agg(
                [
                    pl.col("clicks").sum().alias("total_clicks"),
                    pl.col("impressions").sum().alias("total_impressions"),
                ]
            )
            .with_columns(
                (pl.col("total_clicks") / pl.col("total_impressions")).alias(
                    "weekly_ctr"
                )
            )
            .sort("week_start")
        )

        if len(weekly) < 2:
            return insights

        # Campaign average CTR
        total_clicks = self.df["clicks"].sum()
        total_impressions = self.df["impressions"].sum()
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0

        if avg_ctr == 0:
            return insights

        threshold = avg_ctr * self.thresholds.ctr_recovery_pct

        # Only check later weeks (skip first half)
        weeks_list = weekly.to_dicts()
        midpoint = len(weeks_list) // 2

        for row in weeks_list[midpoint:]:
            weekly_ctr = row["weekly_ctr"]
            if weekly_ctr is None:
                continue

            pct_of_avg = weekly_ctr / avg_ctr if avg_ctr > 0 else 0

            if weekly_ctr >= threshold:
                insights.append(
                    Insight(
                        rule_id="ctr_recovery",
                        description=(
                            f"Week {row['week_start']} showed CTR recovery at "
                            f"{pct_of_avg * 100:.1f}% of campaign average"
                        ),
                        severity=Severity.GREEN,
                        recommendation=(
                            "Positive trend detected. Analyze what changed "
                            "(creative refresh, targeting adjustments, inventory mix) "
                            "and apply learnings to future campaigns."
                        ),
                        metrics={
                            "week": row["week_start"].isoformat(),
                            "weekly_ctr": round(weekly_ctr * 100, 4),
                            "avg_ctr": round(avg_ctr * 100, 4),
                            "pct_of_avg": round(pct_of_avg * 100, 1),
                        },
                    )
                )

        return insights

    def _check_vcr_drop(self) -> list[Insight]:
        """Check for >= 3 percentage point VCR decline week-over-week."""
        insights: list[Insight] = []

        if "video_complete_pct" not in self.df.columns:
            return insights

        weekly = (
            self.df.group_by("week_start")
            .agg(
                [
                    (
                        pl.col("video_complete_pct").fill_null(0) * pl.col("impressions")
                    )
                    .sum()
                    .alias("weighted_vcr_sum"),
                    pl.col("impressions").sum().alias("total_impressions"),
                ]
            )
            .with_columns(
                (pl.col("weighted_vcr_sum") / pl.col("total_impressions")).alias(
                    "weekly_vcr"
                )
            )
            .sort("week_start")
        )

        weeks_list = weekly.to_dicts()
        for i in range(1, len(weeks_list)):
            prev_vcr = weeks_list[i - 1]["weekly_vcr"]
            curr_vcr = weeks_list[i]["weekly_vcr"]

            if prev_vcr is None or curr_vcr is None:
                continue

            drop_points = prev_vcr - curr_vcr  # In decimal form

            if drop_points >= self.thresholds.vcr_drop_points:
                insights.append(
                    Insight(
                        rule_id="vcr_drop",
                        description=(
                            f"Week {weeks_list[i]['week_start']} had a "
                            f"{drop_points * 100:.1f} percentage point VCR drop "
                            f"from previous week"
                        ),
                        severity=Severity.AMBER,
                        recommendation=(
                            "Video completion rate declined significantly. "
                            "Review video creative length, placement quality, "
                            "and consider skip-ad patterns in inventory."
                        ),
                        metrics={
                            "week": weeks_list[i]["week_start"].isoformat(),
                            "current_vcr": round(curr_vcr * 100, 2),
                            "previous_vcr": round(prev_vcr * 100, 2),
                            "drop_points": round(drop_points * 100, 1),
                        },
                    )
                )

        return insights

    def _check_platform_concentration(self) -> list[Insight]:
        """Check if single platform/device >= 80% of impressions."""
        insights: list[Insight] = []

        total_impressions = self.df["impressions"].sum()
        if total_impressions == 0:
            return insights

        platform_df = self.df.group_by("platform_device_type").agg(
            pl.col("impressions").sum().alias("platform_impressions")
        )

        for row in platform_df.to_dicts():
            share = row["platform_impressions"] / total_impressions

            if share >= self.thresholds.platform_concentration_pct:
                insights.append(
                    Insight(
                        rule_id="platform_concentration",
                        description=(
                            f"Platform '{row['platform_device_type']}' accounts for "
                            f"{share * 100:.1f}% of total impressions"
                        ),
                        severity=Severity.AMBER,
                        recommendation=(
                            "High platform concentration detected. Consider "
                            "diversifying across devices to reduce risk and "
                            "reach broader audiences. Test performance on "
                            "underrepresented platforms."
                        ),
                        metrics={
                            "platform": row["platform_device_type"],
                            "impressions": row["platform_impressions"],
                            "share_pct": round(share * 100, 1),
                        },
                    )
                )

        return insights

    def _check_domain_concentration(self) -> list[Insight]:
        """Check for domain concentration issues."""
        insights: list[Insight] = []

        total_impressions = self.df["impressions"].sum()
        if total_impressions == 0:
            return insights

        domain_df = (
            self.df.group_by("domain")
            .agg(pl.col("impressions").sum().alias("domain_impressions"))
            .sort("domain_impressions", descending=True)
        )

        domain_list = domain_df.to_dicts()

        # Check top domain concentration
        if domain_list:
            top_domain = domain_list[0]
            top_share = top_domain["domain_impressions"] / total_impressions

            if top_share >= self.thresholds.top_domain_concentration_pct:
                insights.append(
                    Insight(
                        rule_id="top_domain_concentration",
                        description=(
                            f"Top domain '{top_domain['domain']}' accounts for "
                            f"{top_share * 100:.1f}% of total impressions"
                        ),
                        severity=Severity.RED,
                        recommendation=(
                            "Single domain dominance creates inventory risk. "
                            "Diversify supply sources to improve reach and "
                            "reduce dependency on one publisher."
                        ),
                        metrics={
                            "domain": top_domain["domain"],
                            "impressions": top_domain["domain_impressions"],
                            "share_pct": round(top_share * 100, 1),
                        },
                    )
                )

        # Check top-5 concentration
        if len(domain_list) >= 5:
            top5_impressions = sum(d["domain_impressions"] for d in domain_list[:5])
            top5_share = top5_impressions / total_impressions

            if top5_share >= self.thresholds.top5_domain_concentration_pct:
                insights.append(
                    Insight(
                        rule_id="top5_domain_concentration",
                        description=(
                            f"Top 5 domains account for {top5_share * 100:.1f}% "
                            f"of total impressions"
                        ),
                        severity=Severity.AMBER,
                        recommendation=(
                            "Inventory is concentrated in few domains. "
                            "Consider expanding domain allowlist or "
                            "testing programmatic deals with more publishers."
                        ),
                        metrics={
                            "top5_domains": [d["domain"] for d in domain_list[:5]],
                            "top5_impressions": top5_impressions,
                            "share_pct": round(top5_share * 100, 1),
                        },
                    )
                )

        return insights

    def to_dict(self, insights: list[Insight]) -> list[dict[str, Any]]:
        """Convert insights list to JSON-serializable format."""
        return [
            {
                "rule_id": i.rule_id,
                "description": i.description,
                "severity": i.severity.value,
                "recommendation": i.recommendation,
                "metrics": i.metrics,
            }
            for i in insights
        ]
