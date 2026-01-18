"""Analytical Engine - main calculator class for ad campaign data analysis."""

from dataclasses import dataclass
from datetime import datetime

import polars as pl

from ..models.stat_pack import StatPack
from .expressions import (
    anomaly_direction_expr,
    anomaly_flag_expr,
    campaign_kpi_expr,
    ctr_vs_avg_expr,
    day_of_week_aggregates_expr,
    domain_aggregates_expr,
    impression_share_expr,
    platform_aggregates_expr,
    spend_pct_of_total_expr,
    vcr_percentile_expr,
    weekly_totals_expr,
    weekend_weekday_ctr_expr,
    wow_change_expr,
    z_score_expr,
)
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
from .stats import detect_trend, pearson_correlation, weekend_lift


@dataclass
class AnalyticalEngine:
    """Main analytics calculator for ad campaign data.

    All methods are pure functions - they do not mutate the input DataFrame.

    Attributes:
        df: Cleaned and enriched Polars DataFrame from ingestion pipeline
        campaign_goal: Target impressions for the campaign (optional)
        anomaly_threshold: Z-score threshold for anomaly detection (default 1.5)
        spike_threshold: WoW change threshold for spike detection (default 0.50)
        backload_threshold: Threshold for back-loaded delivery (default 0.40)
    """

    df: pl.DataFrame
    campaign_goal: int | None = None
    anomaly_threshold: float = 1.5
    spike_threshold: float = 0.50
    backload_threshold: float = 0.40

    def __post_init__(self) -> None:
        """Validate input DataFrame has required columns."""
        required = {"impressions", "clicks", "spend", "ctr", "week_start", "report_day"}
        available = set(self.df.columns)
        missing = required - available
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    # =========================================================================
    # TEMPORAL ANALYSIS
    # =========================================================================

    def get_temporal_stats(self) -> TemporalStats:
        """Calculate weekly aggregates and week-over-week changes.

        Returns:
            TemporalStats containing weekly totals, WoW deltas, and spikes.
        """
        # Weekly totals
        weekly_df = (
            self.df.group_by("week_start").agg(weekly_totals_expr()).sort("week_start")
        )

        # Calculate WoW changes for key metrics
        metrics = ["total_impressions", "total_clicks", "total_spend", "avg_ctr"]
        weekly_with_wow = weekly_df.with_columns(
            [wow_change_expr(m) for m in metrics]
        )

        # Build WeeklyStats objects
        weekly_totals = [
            WeeklyStats(
                week_start=row["week_start"],
                impressions=row["total_impressions"],
                clicks=row["total_clicks"],
                spend=row["total_spend"],
                avg_ctr=row["avg_ctr"],
                avg_cpm=row["avg_cpm"],
                avg_vcr=row.get("avg_vcr"),
                avg_viewability=row.get("avg_viewability"),
            )
            for row in weekly_df.to_dicts()
        ]

        # Extract WoW changes and detect spikes
        wow_changes: list[WeekOverWeekChange] = []
        for row in weekly_with_wow.to_dicts():
            for metric in metrics:
                change_col = f"{metric}_wow_change"
                pct_change = row.get(change_col)
                if pct_change is not None:
                    current_val = row[metric]
                    # Calculate previous value from change
                    prev_val = (
                        current_val / (1 + pct_change) if pct_change != -1 else 0
                    )
                    wow_changes.append(
                        WeekOverWeekChange(
                            week_start=row["week_start"],
                            metric_name=metric,
                            current_value=current_val,
                            previous_value=prev_val,
                            pct_change=pct_change,
                            is_spike=abs(pct_change) >= self.spike_threshold,
                        )
                    )

        spikes = [w for w in wow_changes if w.is_spike]

        return TemporalStats(
            weekly_totals=weekly_totals,
            wow_changes=wow_changes,
            spikes=spikes,
        )

    # =========================================================================
    # EFFICIENCY METRICS
    # =========================================================================

    def get_efficiency_metrics(self) -> EfficiencyMetrics:
        """Calculate domain and platform efficiency metrics.

        Returns:
            EfficiencyMetrics with domain rankings, correlations, and gaps.
        """
        # Domain-level metrics
        domain_df = self.df.group_by("domain").agg(domain_aggregates_expr())

        # Weekend vs weekday CTR by domain
        weekend_weekday_df = self.df.group_by("domain").agg(weekend_weekday_ctr_expr())

        # Combine domain metrics
        domain_combined = domain_df.join(weekend_weekday_df, on="domain")

        domain_metrics: list[DomainEfficiency] = []
        for row in domain_combined.to_dicts():
            # Calculate CTR/VCR correlation for this domain
            domain_data = self.df.filter(pl.col("domain") == row["domain"])
            correlation = pearson_correlation(
                domain_data, "ctr", "video_complete_pct", min_samples=5
            )

            # Weekend lift
            weekday_ctr = row.get("weekday_ctr")
            weekend_ctr = row.get("weekend_ctr")
            lift = None
            if weekday_ctr and weekday_ctr > 0 and weekend_ctr is not None:
                lift = (weekend_ctr - weekday_ctr) / weekday_ctr

            domain_metrics.append(
                DomainEfficiency(
                    domain=row["domain"],
                    avg_ctr=row["avg_ctr"],
                    avg_vcr=row["avg_vcr"],
                    total_impressions=row["total_impressions"],
                    total_spend=row["total_spend"],
                    ctr_vcr_correlation=correlation,
                    weekend_lift=lift,
                    weekday_avg_ctr=weekday_ctr or 0,
                    weekend_avg_ctr=weekend_ctr or 0,
                )
            )

        # Platform-level metrics
        platform_df = self.df.group_by("platform_device_type").agg(
            platform_aggregates_expr()
        )

        platform_metrics = [
            PlatformPerformance(
                platform=row["platform_device_type"],
                avg_ctr=row["avg_ctr"],
                avg_vcr=row["avg_vcr"],
                total_impressions=row["total_impressions"],
                total_spend=row["total_spend"],
            )
            for row in platform_df.to_dicts()
        ]

        # Performance gaps
        performance_gaps: list[PerformanceGap] = []
        for metric in ["avg_ctr", "total_impressions"]:
            max_val = platform_df[metric].max()
            min_val = platform_df[metric].min()

            if max_val and max_val > 0:
                max_rows = platform_df.filter(pl.col(metric) == max_val).to_dicts()
                min_rows = platform_df.filter(pl.col(metric) == min_val).to_dicts()

                if max_rows and min_rows:
                    gap_pct = (max_val - min_val) / max_val
                    performance_gaps.append(
                        PerformanceGap(
                            metric_name=metric,
                            max_platform=max_rows[0]["platform_device_type"],
                            max_value=max_val,
                            min_platform=min_rows[0]["platform_device_type"],
                            min_value=min_val,
                            gap_pct=gap_pct,
                        )
                    )

        # Overall correlations and weekend lift
        overall_correlation = pearson_correlation(
            self.df, "ctr", "video_complete_pct", min_samples=10
        )

        weekend_data = self.df.filter(pl.col("is_weekend"))
        weekday_data = self.df.filter(~pl.col("is_weekend"))
        overall_lift = None
        if len(weekend_data) > 0 and len(weekday_data) > 0:
            overall_lift = weekend_lift(
                weekend_data["ctr"].to_list(),
                weekday_data["ctr"].to_list(),
            )

        return EfficiencyMetrics(
            domain_metrics=domain_metrics,
            platform_metrics=platform_metrics,
            performance_gaps=performance_gaps,
            overall_ctr_vcr_correlation=overall_correlation,
            overall_weekend_lift=overall_lift,
        )

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================

    def detect_anomalies(self, metric: str = "ctr") -> AnomalyReport:
        """Detect anomalies using z-score analysis per week.

        Args:
            metric: Column name to analyze (default: "ctr")

        Returns:
            AnomalyReport with flagged weeks and z-scores.
        """
        # Aggregate metric by week
        agg_col = "avg_ctr" if metric == "ctr" else metric
        weekly = (
            self.df.group_by("week_start")
            .agg(pl.col(metric).mean().alias(agg_col))
            .sort("week_start")
        )

        # Calculate mean and std for z-score
        mean_val = weekly[agg_col].mean()
        std_val = weekly[agg_col].std()

        if std_val is None or std_val == 0:
            return AnomalyReport(
                anomalies=[],
                threshold_used=self.anomaly_threshold,
                total_weeks_analyzed=len(weekly),
            )

        # Add z-score first, then anomaly flags (they depend on z-score column)
        weekly_with_z = (
            weekly.with_columns(z_score_expr(agg_col, mean_val, std_val))
            .with_columns(
                [
                    anomaly_flag_expr(agg_col, self.anomaly_threshold),
                    anomaly_direction_expr(agg_col),
                ]
            )
        )

        # Extract anomalies
        anomalies: list[Anomaly] = []
        anomaly_rows = weekly_with_z.filter(pl.col(f"{agg_col}_is_anomaly")).to_dicts()
        for row in anomaly_rows:
            anomalies.append(
                Anomaly(
                    week_start=row["week_start"],
                    metric_name=metric,
                    value=row[agg_col],
                    mean=mean_val,
                    std=std_val,
                    z_score=row[f"{agg_col}_z_score"],
                    direction=row[f"{agg_col}_anomaly_direction"],
                )
            )

        return AnomalyReport(
            anomalies=anomalies,
            threshold_used=self.anomaly_threshold,
            total_weeks_analyzed=len(weekly),
        )

    # =========================================================================
    # NORMALIZED METRICS
    # =========================================================================

    def get_normalized_df(self) -> pl.DataFrame:
        """Add normalized metric columns to the DataFrame.

        Adds columns:
            - impressions_wow_delta: WoW change for impressions (per week)
            - ctr_vs_avg: CTR deviation from overall mean (z-score)
            - vcr_percentile: VCR percentile rank (0-1)
            - spend_pct_of_total: Row's spend as % of total

        Returns:
            New DataFrame with added columns (original unchanged).
        """
        # Get overall stats for normalization
        overall_ctr_mean = self.df["ctr"].mean()
        overall_ctr_std = self.df["ctr"].std()
        total_spend = self.df["spend"].sum()

        # Calculate weekly impressions for WoW delta
        weekly_impressions = (
            self.df.group_by("week_start")
            .agg(pl.col("impressions").sum().alias("weekly_impressions"))
            .sort("week_start")
            .with_columns(wow_change_expr("weekly_impressions"))
        )

        # Join and add normalized columns
        result = self.df.join(
            weekly_impressions.select(
                ["week_start", "weekly_impressions_wow_change"]
            ),
            on="week_start",
            how="left",
        ).rename({"weekly_impressions_wow_change": "impressions_wow_delta"})

        # Handle edge case of zero std
        if overall_ctr_std and overall_ctr_std > 0:
            result = result.with_columns(
                ctr_vs_avg_expr(overall_ctr_mean, overall_ctr_std)
            )
        else:
            result = result.with_columns(pl.lit(0.0).alias("ctr_vs_avg"))

        # Add VCR percentile if column exists
        if "video_complete_pct" in self.df.columns:
            result = result.with_columns(vcr_percentile_expr())
        else:
            result = result.with_columns(pl.lit(None).alias("vcr_percentile"))

        # Add spend percentage
        if total_spend and total_spend > 0:
            result = result.with_columns(spend_pct_of_total_expr(total_spend))
        else:
            result = result.with_columns(pl.lit(0.0).alias("spend_pct_of_total"))

        return result

    # =========================================================================
    # GOAL TRACKING
    # =========================================================================

    def get_goal_progress(self) -> GoalProgress:
        """Calculate campaign goal completion.

        Returns:
            GoalProgress with completion % and on-track status.

        Raises:
            ValueError: If campaign_goal not set.
        """
        if self.campaign_goal is None:
            raise ValueError("campaign_goal must be set to calculate goal progress")

        total_impressions = self.df["impressions"].sum()
        completion_pct = (total_impressions / self.campaign_goal) * 100

        # Calculate projected completion based on time elapsed
        date_stats = self.df.select(
            [
                pl.col("report_day").min().alias("data_start"),
                pl.col("report_day").max().alias("data_end"),
                pl.col("campaign_end").max().alias("campaign_end"),
            ]
        ).to_dicts()[0]

        data_start = date_stats["data_start"]
        data_end = date_stats["data_end"]
        campaign_end = date_stats["campaign_end"]

        days_elapsed = (data_end - data_start).days + 1
        total_days = (campaign_end - data_start).days + 1

        time_pct_elapsed = days_elapsed / total_days if total_days > 0 else 1
        projected_pct = (
            (completion_pct / time_pct_elapsed) if time_pct_elapsed > 0 else completion_pct
        )

        return GoalProgress(
            total_impressions=total_impressions,
            campaign_goal=self.campaign_goal,
            completion_pct=completion_pct,
            is_on_track=completion_pct >= (time_pct_elapsed * 100),
            projected_completion_pct=min(projected_pct, 200),  # Cap at 200%
        )

    # =========================================================================
    # DELIVERY PATTERN
    # =========================================================================

    def get_delivery_pattern(self) -> DeliveryPattern:
        """Analyze delivery timing to detect back-loading.

        Returns:
            DeliveryPattern with back-loading detection.
        """
        # Daily impressions sorted by date
        daily = (
            self.df.group_by("report_day")
            .agg(pl.col("impressions").sum().alias("daily_impressions"))
            .sort("report_day")
        )

        total_days = len(daily)
        total_impressions = daily["daily_impressions"].sum()

        if total_days == 0 or total_impressions == 0:
            return DeliveryPattern(
                is_back_loaded=False,
                last_quarter_delivery_pct=0,
                threshold_used=self.backload_threshold,
                daily_trend="stable",
            )

        # Get last 25% of days
        last_quarter_start = int(total_days * 0.75)
        last_quarter_impressions = daily[last_quarter_start:]["daily_impressions"].sum()
        last_quarter_pct = last_quarter_impressions / total_impressions

        # Detect trend
        daily_values = daily["daily_impressions"].to_list()
        trend = detect_trend(daily_values)

        return DeliveryPattern(
            is_back_loaded=last_quarter_pct > self.backload_threshold,
            last_quarter_delivery_pct=last_quarter_pct,
            threshold_used=self.backload_threshold,
            daily_trend=trend,
        )

    # =========================================================================
    # CAMPAIGN KPIs (RECOMPUTED)
    # =========================================================================

    def get_campaign_kpis(self) -> CampaignKPIs:
        """Calculate campaign-level KPIs from raw data.

        All metrics are recomputed, not taken from Excel aggregates.

        Returns:
            CampaignKPIs with impressions, clicks, spend, CTR, CPM,
            viewability, and VCR.
        """
        kpis = self.df.select(campaign_kpi_expr()).to_dicts()[0]

        return CampaignKPIs(
            total_impressions=kpis["total_impressions"],
            total_clicks=kpis["total_clicks"],
            total_spend=kpis["total_spend"],
            ctr=kpis["ctr"],
            cpm=kpis["cpm"],
            viewability_pct=kpis["viewability_pct"],
            vcr_pct=kpis["vcr_pct"],
        )

    # =========================================================================
    # DAY OF WEEK ANALYSIS
    # =========================================================================

    def get_dow_performance(self) -> list[DayOfWeekStats]:
        """Calculate performance breakdown by day of week.

        Returns:
            List of DayOfWeekStats for Mon-Sun with impressions, CTR, VCR, spend.
        """
        dow_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        dow_df = self.df.group_by("day_of_week").agg(day_of_week_aggregates_expr())

        # Sort by day of week order
        dow_df = dow_df.with_columns(
            pl.col("day_of_week")
            .replace_strict(dow_order, list(range(7)), default=7)
            .alias("dow_order")
        ).sort("dow_order")

        return [
            DayOfWeekStats(
                day_of_week=row["day_of_week"],
                impressions=row["total_impressions"],
                clicks=row["total_clicks"],
                spend=row["total_spend"],
                avg_ctr=row["avg_ctr"],
                avg_vcr=row["avg_vcr"],
            )
            for row in dow_df.to_dicts()
        ]

    # =========================================================================
    # ENHANCED DOMAIN ANALYSIS
    # =========================================================================

    def get_domain_stats(
        self,
        top_n: int = 10,
        underperform_share_threshold: float = 0.05,
        underperform_ctr_percentile: float = 0.25,
    ) -> tuple[list[DomainStats], float]:
        """Calculate domain stats with share and underperforming flags.

        Args:
            top_n: Number of top domains to return (default 10)
            underperform_share_threshold: Min share to consider for underperforming
            underperform_ctr_percentile: CTR below this percentile = underperforming

        Returns:
            Tuple of (list of DomainStats sorted by impressions, top_n_share)
        """
        total_impressions = self.df["impressions"].sum()

        # Get domain aggregates
        domain_df = self.df.group_by("domain").agg(domain_aggregates_expr())

        # Add impression share
        domain_df = domain_df.with_columns(
            impression_share_expr(total_impressions)
        )

        # Calculate CTR threshold for underperforming
        ctr_threshold = domain_df["avg_ctr"].quantile(underperform_ctr_percentile)

        # Add underperforming flag
        domain_df = domain_df.with_columns(
            (
                (pl.col("impression_share") >= underperform_share_threshold)
                & (pl.col("avg_ctr") < ctr_threshold)
            ).alias("is_underperforming")
        )

        # Sort by impressions descending
        domain_df = domain_df.sort("total_impressions", descending=True)

        # Calculate top-N share
        top_n_df = domain_df.head(top_n)
        top_n_share = top_n_df["total_impressions"].sum() / total_impressions

        domain_stats = [
            DomainStats(
                domain=row["domain"],
                impressions=row["total_impressions"],
                clicks=row["total_clicks"],
                spend=row["total_spend"],
                avg_ctr=row["avg_ctr"],
                avg_cpm=row["avg_cpm"],
                avg_vcr=row["avg_vcr"],
                avg_viewability=row["avg_viewability"],
                impression_share=row["impression_share"],
                is_underperforming=row["is_underperforming"],
            )
            for row in top_n_df.to_dicts()
        ]

        return domain_stats, top_n_share

    def get_platform_stats(self) -> list[PlatformPerformance]:
        """Calculate platform/device breakdown with impression share.

        Returns:
            List of PlatformPerformance with share calculations.
        """
        total_impressions = self.df["impressions"].sum()

        platform_df = self.df.group_by("platform_device_type").agg(
            platform_aggregates_expr()
        )

        # Add impression share
        platform_df = platform_df.with_columns(
            impression_share_expr(total_impressions)
        )

        # Sort by impressions descending
        platform_df = platform_df.sort("total_impressions", descending=True)

        return [
            PlatformPerformance(
                platform=row["platform_device_type"],
                avg_ctr=row["avg_ctr"],
                avg_vcr=row["avg_vcr"],
                total_impressions=row["total_impressions"],
                total_spend=row["total_spend"],
            )
            for row in platform_df.to_dicts()
        ]

    # =========================================================================
    # STAT PACK (CONSOLIDATED OUTPUT)
    # =========================================================================

    def get_stat_pack(self) -> StatPack:
        """Generate consolidated analytics for LLM consumption.

        Runs all analyses and packages results into StatPack.

        Returns:
            StatPack with all aggregates, trends, and anomalies.
        """
        # Run all analyses
        temporal = self.get_temporal_stats()
        efficiency = self.get_efficiency_metrics()
        anomalies = self.detect_anomalies("ctr")
        delivery = self.get_delivery_pattern()

        # Goal progress (with fallback if goal not set)
        if self.campaign_goal:
            goal = self.get_goal_progress()
            goal_dict = {
                "total": goal.total_impressions,
                "goal": goal.campaign_goal,
                "completion_pct": round(goal.completion_pct, 2),
                "is_on_track": goal.is_on_track,
                "projected_pct": round(goal.projected_completion_pct, 2),
            }
        else:
            goal_dict = {
                "total": self.df["impressions"].sum(),
                "goal": None,
                "completion_pct": None,
                "is_on_track": None,
                "projected_pct": None,
            }

        # Get date range
        date_range = (
            self.df["report_day"].min(),
            self.df["report_day"].max(),
        )

        # Get average VCR and viewability
        avg_vcr = None
        if "video_complete_pct" in self.df.columns:
            avg_vcr = self.df["video_complete_pct"].mean()

        avg_viewability = None
        if "viewability_pct" in self.df.columns:
            avg_viewability = self.df["viewability_pct"].mean()

        # Build weekly performance dicts
        weekly_performance = [
            {
                "week": w.week_start.isoformat(),
                "impressions": w.impressions,
                "clicks": w.clicks,
                "spend": round(w.spend, 2),
                "ctr": round(w.avg_ctr * 100, 4),  # as percentage
                "cpm": round(w.avg_cpm, 2),
            }
            for w in temporal.weekly_totals
        ]

        # Build WoW changes dicts
        wow_changes = [
            {
                "week": w.week_start.isoformat(),
                "metric": w.metric_name,
                "pct_change": round(w.pct_change * 100, 2),  # as percentage
            }
            for w in temporal.wow_changes
            if w.pct_change is not None
        ]

        # Build spikes dicts
        spikes = [
            {
                "week": s.week_start.isoformat(),
                "metric": s.metric_name,
                "pct_change": round(s.pct_change * 100, 2),
                "description": f"{abs(s.pct_change) * 100:.1f}% {'spike' if s.pct_change > 0 else 'drop'}",
            }
            for s in temporal.spikes
        ]

        # Domain rankings (sorted by CTR)
        domain_rankings = [
            {
                "domain": d.domain,
                "avg_ctr": round(d.avg_ctr * 100, 4),
                "avg_vcr": round(d.avg_vcr * 100, 2) if d.avg_vcr else None,
                "impressions": d.total_impressions,
                "weekend_lift": round(d.weekend_lift * 100, 2) if d.weekend_lift else None,
            }
            for d in sorted(
                efficiency.domain_metrics, key=lambda x: x.avg_ctr, reverse=True
            )
        ]

        # Platform comparison
        platform_comparison = [
            {
                "platform": p.platform,
                "avg_ctr": round(p.avg_ctr * 100, 4),
                "avg_vcr": round(p.avg_vcr * 100, 2) if p.avg_vcr else None,
                "impressions": p.total_impressions,
                "spend": round(p.total_spend, 2),
            }
            for p in efficiency.platform_metrics
        ]

        # Performance gaps
        performance_gaps = [
            {
                "metric": g.metric_name,
                "max_platform": g.max_platform,
                "max_value": g.max_value,
                "min_platform": g.min_platform,
                "min_value": g.min_value,
                "gap_pct": round(g.gap_pct * 100, 2),
            }
            for g in efficiency.performance_gaps
        ]

        # Weekend vs weekday
        weekend_vs_weekday = {
            "lift": (
                round(efficiency.overall_weekend_lift * 100, 2)
                if efficiency.overall_weekend_lift
                else None
            ),
            "ctr_vcr_correlation": (
                round(efficiency.overall_ctr_vcr_correlation, 4)
                if efficiency.overall_ctr_vcr_correlation
                else None
            ),
        }

        # Anomalies
        anomalies_list = [
            {
                "week": a.week_start.isoformat(),
                "metric": a.metric_name,
                "value": round(a.value * 100, 4),  # as percentage for CTR
                "z_score": round(a.z_score, 2),
                "direction": a.direction,
            }
            for a in anomalies.anomalies
        ]

        # Correlations
        correlations = {
            "ctr_vcr": efficiency.overall_ctr_vcr_correlation,
            "ctr_viewability": pearson_correlation(
                self.df, "ctr", "viewability_pct", min_samples=10
            ),
        }

        # Normalized metrics summary
        normalized_df = self.get_normalized_df()
        normalized_metrics = {
            "ctr_vs_avg_mean": round(normalized_df["ctr_vs_avg"].mean(), 4),
            "vcr_percentile_median": (
                round(normalized_df["vcr_percentile"].median(), 2)
                if "vcr_percentile" in normalized_df.columns
                and normalized_df["vcr_percentile"].null_count() < len(normalized_df)
                else None
            ),
        }

        return StatPack(
            generated_at=datetime.now(),
            campaign_id=self.df["campaign_id"].unique()[0],
            date_range=date_range,
            total_rows=len(self.df),
            total_impressions=self.df["impressions"].sum(),
            total_clicks=self.df["clicks"].sum(),
            total_spend=self.df["spend"].sum(),
            avg_ctr=self.df["ctr"].mean(),
            avg_cpm=self.df["cpm"].mean(),
            avg_vcr=avg_vcr,
            avg_viewability=avg_viewability,
            goal_progress=goal_dict,
            delivery_pattern={
                "is_back_loaded": delivery.is_back_loaded,
                "last_quarter_pct": round(delivery.last_quarter_delivery_pct * 100, 2),
                "trend": delivery.daily_trend,
            },
            weekly_performance=weekly_performance,
            wow_changes=wow_changes,
            spikes=spikes,
            domain_rankings=domain_rankings,
            platform_comparison=platform_comparison,
            performance_gaps=performance_gaps,
            weekend_vs_weekday=weekend_vs_weekday,
            anomalies=anomalies_list,
            correlations=correlations,
            normalized_metrics=normalized_metrics,
        )
