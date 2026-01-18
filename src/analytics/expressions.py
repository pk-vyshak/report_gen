"""Reusable Polars expressions for analytics calculations."""

import polars as pl


# =============================================================================
# TEMPORAL AGGREGATIONS
# =============================================================================


def weekly_totals_expr() -> list[pl.Expr]:
    """Expressions for weekly aggregate metrics.

    Uses weighted averages for CTR, VCR, and Viewability.
    CTR = total_clicks / total_impressions
    VCR = sum(vcr * impressions) / sum(impressions)
    Viewability = sum(viewable_impressions) / sum(impressions)
    """
    return [
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        pl.col("viewable_impressions").sum().alias("total_viewable_impressions"),
        pl.col("video_completes").sum().alias("total_video_completes"),
        # Recomputed CTR: clicks / impressions
        (pl.col("clicks").sum() / pl.col("impressions").sum()).alias("avg_ctr"),
        # Recomputed CPM: (spend / impressions) * 1000
        (pl.col("spend").sum() / pl.col("impressions").sum() * 1000).alias("avg_cpm"),
        # Weighted VCR: sum(vcr * impressions) / sum(impressions)
        weighted_vcr_expr().alias("avg_vcr"),
        # Viewability: sum(viewable_impressions) / sum(impressions)
        (pl.col("viewable_impressions").sum() / pl.col("impressions").sum()).alias(
            "avg_viewability"
        ),
    ]


def weighted_vcr_expr() -> pl.Expr:
    """Weighted VCR calculation: sum(vcr_pct * impressions) / sum(impressions).

    Handles null VCR values by treating them as 0 contribution.
    """
    return (
        (pl.col("video_complete_pct").fill_null(0) * pl.col("impressions")).sum()
        / pl.col("impressions").sum()
    )


def weighted_viewability_expr() -> pl.Expr:
    """Viewability rollup: sum(viewable_impressions) / sum(impressions)."""
    return pl.col("viewable_impressions").sum() / pl.col("impressions").sum()


def wow_change_expr(metric: str) -> pl.Expr:
    """Calculate week-over-week percentage change.

    Formula: (current - previous) / previous
    Uses shift(1) to get previous week's value.
    """
    return (
        (pl.col(metric) - pl.col(metric).shift(1)) / pl.col(metric).shift(1)
    ).alias(f"{metric}_wow_change")


# =============================================================================
# NORMALIZED METRICS
# =============================================================================


def ctr_vs_avg_expr(mean: float, std: float) -> pl.Expr:
    """CTR deviation from overall mean (z-score)."""
    return ((pl.col("ctr") - mean) / std).alias("ctr_vs_avg")


def vcr_percentile_expr() -> pl.Expr:
    """VCR percentile rank (0-1 scale)."""
    return (
        pl.col("video_complete_pct").rank("ordinal")
        / pl.col("video_complete_pct").count()
    ).alias("vcr_percentile")


def spend_pct_of_total_expr(total: float) -> pl.Expr:
    """Row spend as percentage of total spend."""
    return (pl.col("spend") / total).alias("spend_pct_of_total")


# =============================================================================
# EFFICIENCY METRICS
# =============================================================================


def domain_aggregates_expr() -> list[pl.Expr]:
    """Expressions for per-domain aggregates with weighted metrics."""
    return [
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        pl.col("viewable_impressions").sum().alias("total_viewable_impressions"),
        # Recomputed CTR
        (pl.col("clicks").sum() / pl.col("impressions").sum()).alias("avg_ctr"),
        # Recomputed CPM
        (pl.col("spend").sum() / pl.col("impressions").sum() * 1000).alias("avg_cpm"),
        # Weighted VCR
        weighted_vcr_expr().alias("avg_vcr"),
        # Viewability
        weighted_viewability_expr().alias("avg_viewability"),
    ]


def platform_aggregates_expr() -> list[pl.Expr]:
    """Expressions for per-platform aggregates with weighted metrics."""
    return [
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        pl.col("viewable_impressions").sum().alias("total_viewable_impressions"),
        # Recomputed CTR
        (pl.col("clicks").sum() / pl.col("impressions").sum()).alias("avg_ctr"),
        # Recomputed CPM
        (pl.col("spend").sum() / pl.col("impressions").sum() * 1000).alias("avg_cpm"),
        # Weighted VCR
        weighted_vcr_expr().alias("avg_vcr"),
        # Viewability
        weighted_viewability_expr().alias("avg_viewability"),
    ]


def day_of_week_aggregates_expr() -> list[pl.Expr]:
    """Expressions for day-of-week aggregates with weighted metrics."""
    return [
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        # Recomputed CTR
        (pl.col("clicks").sum() / pl.col("impressions").sum()).alias("avg_ctr"),
        # Weighted VCR
        weighted_vcr_expr().alias("avg_vcr"),
    ]


def weekend_weekday_ctr_expr() -> list[pl.Expr]:
    """Expressions for weekend vs weekday CTR comparison."""
    return [
        pl.col("ctr").filter(pl.col("is_weekend")).mean().alias("weekend_ctr"),
        pl.col("ctr").filter(~pl.col("is_weekend")).mean().alias("weekday_ctr"),
    ]


# =============================================================================
# ANOMALY DETECTION
# =============================================================================


def z_score_expr(metric: str, mean: float, std: float) -> pl.Expr:
    """Calculate z-score for a metric given mean and std."""
    if std == 0:
        return pl.lit(0.0).alias(f"{metric}_z_score")
    return ((pl.col(metric) - mean) / std).alias(f"{metric}_z_score")


def anomaly_flag_expr(metric: str, threshold: float = 1.5) -> pl.Expr:
    """Flag rows where z-score exceeds threshold."""
    z_col = f"{metric}_z_score"
    return (pl.col(z_col).abs() > threshold).alias(f"{metric}_is_anomaly")


def anomaly_direction_expr(metric: str) -> pl.Expr:
    """Determine anomaly direction (above/below mean)."""
    z_col = f"{metric}_z_score"
    return (
        pl.when(pl.col(z_col) > 0).then(pl.lit("above")).otherwise(pl.lit("below"))
    ).alias(f"{metric}_anomaly_direction")


# =============================================================================
# CAMPAIGN KPI EXPRESSIONS
# =============================================================================


def campaign_kpi_expr() -> list[pl.Expr]:
    """Expressions for campaign-level KPIs (recomputed from raw data).

    All metrics are recomputed, not taken from Excel aggregates.
    """
    return [
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        pl.col("viewable_impressions").sum().alias("total_viewable_impressions"),
        pl.col("video_completes").sum().alias("total_video_completes"),
        # CTR = clicks / impressions
        (pl.col("clicks").sum() / pl.col("impressions").sum()).alias("ctr"),
        # CPM = (spend / impressions) * 1000
        (pl.col("spend").sum() / pl.col("impressions").sum() * 1000).alias("cpm"),
        # Viewability = viewable_impressions / impressions
        (pl.col("viewable_impressions").sum() / pl.col("impressions").sum()).alias(
            "viewability_pct"
        ),
        # VCR = weighted average
        (
            (pl.col("video_complete_pct").fill_null(0) * pl.col("impressions")).sum()
            / pl.col("impressions").sum()
        ).alias("vcr_pct"),
    ]


def impression_share_expr(total_impressions: int) -> pl.Expr:
    """Calculate impression share as percentage of total."""
    return (pl.col("total_impressions") / total_impressions).alias("impression_share")
