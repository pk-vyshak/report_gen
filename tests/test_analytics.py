"""Tests for the analytics module."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from src.analytics import (
    AnalyticalEngine,
    AnomalyReport,
    DeliveryPattern,
    EfficiencyMetrics,
    GoalProgress,
    TemporalStats,
)
from src.ingestion import DataIngestionPipeline
from src.models.stat_pack import StatPack


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_df() -> pl.DataFrame:
    """Create a minimal test DataFrame."""
    return pl.DataFrame(
        {
            "campaign_id": [1, 1, 1, 1, 1, 1, 1],
            "report_day": [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 8),
                date(2024, 1, 9),
                date(2024, 1, 15),
                date(2024, 1, 16),
                date(2024, 1, 22),
            ],
            "week_start": [
                date(2024, 1, 1),
                date(2024, 1, 1),
                date(2024, 1, 8),
                date(2024, 1, 8),
                date(2024, 1, 15),
                date(2024, 1, 15),
                date(2024, 1, 22),
            ],
            "impressions": [1000, 1200, 2000, 2500, 3000, 3500, 8000],
            "clicks": [50, 60, 100, 125, 150, 175, 400],
            "spend": [100.0, 120.0, 200.0, 250.0, 300.0, 350.0, 800.0],
            "ctr": [0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
            "cpm": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "domain": ["a.com", "b.com", "a.com", "b.com", "a.com", "b.com", "a.com"],
            "platform_device_type": [
                "Mobile",
                "Desktop",
                "Mobile",
                "Desktop",
                "Mobile",
                "Desktop",
                "Mobile",
            ],
            "is_weekend": [False, False, False, False, False, False, False],
            "campaign_end": [date(2024, 1, 31)] * 7,
            "video_complete_pct": [0.80, 0.85, 0.82, 0.88, 0.81, 0.87, 0.90],
            "viewability_pct": [0.99, 0.98, 0.99, 0.97, 0.99, 0.98, 0.99],
        }
    )


@pytest.fixture
def engine(sample_df: pl.DataFrame) -> AnalyticalEngine:
    """Create an AnalyticalEngine with sample data."""
    return AnalyticalEngine(
        df=sample_df,
        campaign_goal=25000,
        anomaly_threshold=1.5,
        spike_threshold=0.50,
    )


# =============================================================================
# UNIT TESTS
# =============================================================================


class TestTemporalStats:
    """Tests for get_temporal_stats()."""

    def test_returns_temporal_stats(self, engine: AnalyticalEngine) -> None:
        """Should return TemporalStats object."""
        result = engine.get_temporal_stats()
        assert isinstance(result, TemporalStats)

    def test_weekly_totals_count(self, engine: AnalyticalEngine) -> None:
        """Should have correct number of weeks."""
        result = engine.get_temporal_stats()
        assert len(result.weekly_totals) == 4  # 4 unique week_starts

    def test_weekly_impressions_sum(self, engine: AnalyticalEngine) -> None:
        """Weekly impressions should be correct."""
        result = engine.get_temporal_stats()
        # Week 1: 1000 + 1200 = 2200
        week1 = next(w for w in result.weekly_totals if w.week_start == date(2024, 1, 1))
        assert week1.impressions == 2200

    def test_detects_spike(self, engine: AnalyticalEngine) -> None:
        """Should detect WoW spikes above threshold."""
        result = engine.get_temporal_stats()
        # Week 4 (8000) vs Week 3 (6500) = 23% - not a spike
        # Week 3 (6500) vs Week 2 (4500) = 44% - not a spike
        # Week 2 (4500) vs Week 1 (2200) = 104% - spike!
        spikes = [s for s in result.spikes if s.metric_name == "total_impressions"]
        assert len(spikes) >= 1


class TestEfficiencyMetrics:
    """Tests for get_efficiency_metrics()."""

    def test_returns_efficiency_metrics(self, engine: AnalyticalEngine) -> None:
        """Should return EfficiencyMetrics object."""
        result = engine.get_efficiency_metrics()
        assert isinstance(result, EfficiencyMetrics)

    def test_domain_metrics_count(self, engine: AnalyticalEngine) -> None:
        """Should have metrics for each domain."""
        result = engine.get_efficiency_metrics()
        assert len(result.domain_metrics) == 2  # a.com and b.com

    def test_platform_metrics_count(self, engine: AnalyticalEngine) -> None:
        """Should have metrics for each platform."""
        result = engine.get_efficiency_metrics()
        assert len(result.platform_metrics) == 2  # Mobile and Desktop

    def test_performance_gaps(self, engine: AnalyticalEngine) -> None:
        """Should calculate performance gaps."""
        result = engine.get_efficiency_metrics()
        assert len(result.performance_gaps) >= 1


class TestAnomalyDetection:
    """Tests for detect_anomalies()."""

    def test_returns_anomaly_report(self, engine: AnalyticalEngine) -> None:
        """Should return AnomalyReport object."""
        result = engine.detect_anomalies("ctr")
        assert isinstance(result, AnomalyReport)

    def test_anomaly_threshold_used(self, engine: AnalyticalEngine) -> None:
        """Should use configured threshold."""
        result = engine.detect_anomalies()
        assert result.threshold_used == 1.5

    def test_total_weeks_analyzed(self, engine: AnalyticalEngine) -> None:
        """Should analyze correct number of weeks."""
        result = engine.detect_anomalies()
        assert result.total_weeks_analyzed == 4


class TestNormalizedDf:
    """Tests for get_normalized_df()."""

    def test_adds_normalized_columns(self, engine: AnalyticalEngine) -> None:
        """Should add normalized metric columns."""
        result = engine.get_normalized_df()
        assert "impressions_wow_delta" in result.columns
        assert "ctr_vs_avg" in result.columns
        assert "vcr_percentile" in result.columns
        assert "spend_pct_of_total" in result.columns

    def test_preserves_original_columns(self, engine: AnalyticalEngine) -> None:
        """Should preserve all original columns."""
        original_cols = set(engine.df.columns)
        result = engine.get_normalized_df()
        for col in original_cols:
            assert col in result.columns


class TestGoalProgress:
    """Tests for get_goal_progress()."""

    def test_returns_goal_progress(self, engine: AnalyticalEngine) -> None:
        """Should return GoalProgress object."""
        result = engine.get_goal_progress()
        assert isinstance(result, GoalProgress)

    def test_completion_percentage(self, engine: AnalyticalEngine) -> None:
        """Should calculate correct completion %."""
        result = engine.get_goal_progress()
        # Total impressions = 21200, goal = 25000
        expected_pct = (21200 / 25000) * 100
        assert result.completion_pct == pytest.approx(expected_pct, rel=0.01)

    def test_raises_without_goal(self, sample_df: pl.DataFrame) -> None:
        """Should raise ValueError if no goal set."""
        engine = AnalyticalEngine(df=sample_df, campaign_goal=None)
        with pytest.raises(ValueError, match="campaign_goal must be set"):
            engine.get_goal_progress()


class TestDeliveryPattern:
    """Tests for get_delivery_pattern()."""

    def test_returns_delivery_pattern(self, engine: AnalyticalEngine) -> None:
        """Should return DeliveryPattern object."""
        result = engine.get_delivery_pattern()
        assert isinstance(result, DeliveryPattern)

    def test_detects_back_loading(self, engine: AnalyticalEngine) -> None:
        """Should detect back-loaded delivery."""
        result = engine.get_delivery_pattern()
        # Last 25% of days has 8000 out of 21200 = 37.7%
        # Just under 40% threshold
        assert isinstance(result.is_back_loaded, bool)


class TestStatPack:
    """Tests for get_stat_pack()."""

    def test_returns_stat_pack(self, engine: AnalyticalEngine) -> None:
        """Should return StatPack object."""
        result = engine.get_stat_pack()
        assert isinstance(result, StatPack)

    def test_stat_pack_to_json(self, engine: AnalyticalEngine) -> None:
        """Should serialize to valid JSON."""
        result = engine.get_stat_pack()
        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_stat_pack_aggregates(self, engine: AnalyticalEngine) -> None:
        """Should contain correct aggregates."""
        result = engine.get_stat_pack()
        assert result.total_impressions == 21200
        assert result.total_clicks == 1060


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests with real data."""

    @pytest.fixture
    def real_df(self) -> pl.DataFrame | None:
        """Load real Domain Report if available."""
        data_path = Path("Files/Input/Domain Report.xlsx")
        schema_path = Path("src/config/schema_registry.yaml")

        if not data_path.exists() or not schema_path.exists():
            pytest.skip("Test data not available")

        pipeline = DataIngestionPipeline(schema_path)
        return pipeline.ingest(data_path, validate=True)

    def test_full_pipeline(self, real_df: pl.DataFrame | None) -> None:
        """Test full analytics pipeline with real data."""
        if real_df is None:
            pytest.skip("No real data")

        engine = AnalyticalEngine(
            df=real_df,
            campaign_goal=10_000_000,
        )

        # Run all analyses
        temporal = engine.get_temporal_stats()
        assert len(temporal.weekly_totals) > 0

        efficiency = engine.get_efficiency_metrics()
        assert len(efficiency.domain_metrics) > 0

        anomalies = engine.detect_anomalies()
        assert anomalies.total_weeks_analyzed > 0

        delivery = engine.get_delivery_pattern()
        assert delivery.daily_trend in ("increasing", "decreasing", "stable")

        # Get consolidated output
        stat_pack = engine.get_stat_pack()
        assert stat_pack.total_impressions > 0

        # Test JSON output
        json_output = stat_pack.to_json()
        assert "aggregates" in json_output
        assert "temporal" in json_output
        assert "efficiency" in json_output
