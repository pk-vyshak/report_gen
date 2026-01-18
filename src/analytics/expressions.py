"""Reusable Polars expressions for analytics calculations."""

import polars as pl


# =============================================================================
# TEMPORAL AGGREGATIONS
# =============================================================================


def weekly_totals_expr() -> list[pl.Expr]:
    """Expressions for weekly aggregate metrics."""
    return [
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        pl.col("ctr").mean().alias("avg_ctr"),
        pl.col("cpm").mean().alias("avg_cpm"),
    ]


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
    """Expressions for per-domain aggregates."""
    return [
        pl.col("ctr").mean().alias("avg_ctr"),
        pl.col("video_complete_pct").mean().alias("avg_vcr"),
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("spend").sum().alias("total_spend"),
    ]


def platform_aggregates_expr() -> list[pl.Expr]:
    """Expressions for per-platform aggregates."""
    return [
        pl.col("ctr").mean().alias("avg_ctr"),
        pl.col("video_complete_pct").mean().alias("avg_vcr"),
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("spend").sum().alias("total_spend"),
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
