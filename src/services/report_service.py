"""Report service - orchestrates data ingestion and analytics."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from ..analytics import (
    AnalyticalEngine,
    CampaignKPIs,
    DayOfWeekStats,
    DomainStats,
    Insight,
    InsightEngine,
    InsightThresholds,
)
from ..ingestion import DataIngestionPipeline
from ..models.stat_pack import StatPack

DEFAULT_SCHEMA_PATH = Path(__file__).parent.parent / "config" / "schema_registry.yaml"


@dataclass
class ReportOutput:
    """Consolidated output from report generation."""

    campaign_id: int
    campaign_kpis: CampaignKPIs
    weekly_performance: list[dict[str, Any]]
    platform_breakdown: list[dict[str, Any]]
    dow_performance: list[DayOfWeekStats]
    top_domains: list[DomainStats]
    top_n_domain_share: float
    insights: list[Insight] = field(default_factory=list)
    stat_pack: StatPack | None = None


class ReportService:
    """Service for generating campaign reports from Excel files.

    Orchestrates:
    1. Ingestion of Campaign Report and Domain Report
    2. Filtering by campaign_id
    3. Running all analytics
    4. Returning consolidated output

    Usage:
        service = ReportService()
        output = service.generate_report(
            campaign_id=4512,
            domain_report_path=Path("Files/Input/Domain Report.xlsx"),
            campaign_report_path=Path("Files/Input/Campaign Report.xlsx"),  # optional
        )
    """

    def __init__(self, schema_path: Path | None = None):
        """Initialize service with schema configuration.

        Args:
            schema_path: Path to schema_registry.yaml. Defaults to bundled config.
        """
        self.schema_path = schema_path or DEFAULT_SCHEMA_PATH
        self.pipeline = DataIngestionPipeline(self.schema_path)

    def generate_report(
        self,
        campaign_id: int,
        domain_report_path: Path,
        campaign_report_path: Path | None = None,
        campaign_goal: int | None = None,
        validate: bool = False,
    ) -> ReportOutput:
        """Generate comprehensive campaign report.

        Args:
            campaign_id: Campaign ID to filter data
            domain_report_path: Path to Domain Report Excel file
            campaign_report_path: Path to Campaign Report Excel file (optional)
            campaign_goal: Target impressions for goal tracking (optional)
            validate: Whether to run Pydantic validation (default False for speed)

        Returns:
            ReportOutput with all aggregations and analytics

        Raises:
            ValueError: If campaign_id not found in data
        """
        # Ingest domain report (primary data source)
        domain_df = self.pipeline.ingest(
            domain_report_path,
            schema_name="domain_report",
            validate=validate,
        )

        # Filter by campaign_id
        domain_df = domain_df.filter(pl.col("campaign_id") == campaign_id)

        if len(domain_df) == 0:
            available_ids = (
                self.pipeline.ingest(
                    domain_report_path, schema_name="domain_report", validate=False
                )["campaign_id"]
                .unique()
                .to_list()
            )
            raise ValueError(
                f"Campaign ID {campaign_id} not found. Available: {available_ids}"
            )

        # Optionally ingest campaign report for metadata
        campaign_df = None
        if campaign_report_path and campaign_report_path.exists():
            campaign_df = self.pipeline.ingest(
                campaign_report_path,
                schema_name="campaign_report",
                validate=validate,
            )
            campaign_df = campaign_df.filter(pl.col("campaign_id") == campaign_id)

        # Initialize analytics engine
        engine = AnalyticalEngine(
            df=domain_df,
            campaign_goal=campaign_goal,
        )

        # Run all analytics
        kpis = engine.get_campaign_kpis()
        temporal = engine.get_temporal_stats()
        dow_stats = engine.get_dow_performance()
        top_domains, top_n_share = engine.get_domain_stats(top_n=10)
        platform_stats = engine.get_platform_stats()
        stat_pack = engine.get_stat_pack()

        # Generate rule-based insights
        insight_engine = InsightEngine(domain_df, InsightThresholds())
        insights = insight_engine.generate_all_insights()

        # Build weekly performance output
        weekly_performance = [
            {
                "week": w.week_start.isoformat(),
                "impressions": w.impressions,
                "clicks": w.clicks,
                "spend": round(w.spend, 2),
                "ctr": round(w.avg_ctr * 100, 4) if w.avg_ctr else None,
                "cpm": round(w.avg_cpm, 2) if w.avg_cpm else None,
                "vcr": round(w.avg_vcr * 100, 2) if w.avg_vcr else None,
                "viewability": (
                    round(w.avg_viewability * 100, 2) if w.avg_viewability else None
                ),
            }
            for w in temporal.weekly_totals
        ]

        # Build platform breakdown output
        total_impressions = domain_df["impressions"].sum()
        platform_breakdown = [
            {
                "platform": p.platform,
                "impressions": p.total_impressions,
                "impression_share": round(
                    p.total_impressions / total_impressions * 100, 2
                ),
                "spend": round(p.total_spend, 2),
                "ctr": round(p.avg_ctr * 100, 4) if p.avg_ctr else None,
                "vcr": round(p.avg_vcr * 100, 2) if p.avg_vcr else None,
                "cpm": (
                    round(p.total_spend / p.total_impressions * 1000, 2)
                    if p.total_impressions > 0
                    else None
                ),
            }
            for p in platform_stats
        ]

        return ReportOutput(
            campaign_id=campaign_id,
            campaign_kpis=kpis,
            weekly_performance=weekly_performance,
            platform_breakdown=platform_breakdown,
            dow_performance=dow_stats,
            top_domains=top_domains,
            top_n_domain_share=top_n_share,
            insights=insights,
            stat_pack=stat_pack,
        )

    def get_available_campaigns(self, domain_report_path: Path) -> list[int]:
        """Get list of available campaign IDs from domain report.

        Args:
            domain_report_path: Path to Domain Report Excel file

        Returns:
            List of unique campaign IDs
        """
        df = self.pipeline.ingest(
            domain_report_path,
            schema_name="domain_report",
            validate=False,
        )
        return sorted(df["campaign_id"].unique().to_list())

    def generate_summary_dict(self, output: ReportOutput) -> dict[str, Any]:
        """Convert ReportOutput to JSON-serializable dictionary.

        Args:
            output: ReportOutput from generate_report()

        Returns:
            Dictionary suitable for JSON serialization or LLM consumption
        """
        return {
            "campaign_id": output.campaign_id,
            "kpis": {
                "total_impressions": output.campaign_kpis.total_impressions,
                "total_clicks": output.campaign_kpis.total_clicks,
                "total_spend": round(output.campaign_kpis.total_spend, 2),
                "ctr_pct": round(output.campaign_kpis.ctr * 100, 4),
                "cpm": round(output.campaign_kpis.cpm, 2),
                "viewability_pct": round(output.campaign_kpis.viewability_pct * 100, 2),
                "vcr_pct": (
                    round(output.campaign_kpis.vcr_pct * 100, 2)
                    if output.campaign_kpis.vcr_pct
                    else None
                ),
            },
            "weekly_performance": output.weekly_performance,
            "platform_breakdown": output.platform_breakdown,
            "day_of_week_performance": [
                {
                    "day": d.day_of_week,
                    "impressions": d.impressions,
                    "clicks": d.clicks,
                    "spend": round(d.spend, 2),
                    "ctr_pct": round(d.avg_ctr * 100, 4) if d.avg_ctr else None,
                    "vcr_pct": round(d.avg_vcr * 100, 2) if d.avg_vcr else None,
                }
                for d in output.dow_performance
            ],
            "top_domains": [
                {
                    "domain": d.domain,
                    "impressions": d.impressions,
                    "impression_share_pct": round(d.impression_share * 100, 2),
                    "ctr_pct": round(d.avg_ctr * 100, 4) if d.avg_ctr else None,
                    "vcr_pct": round(d.avg_vcr * 100, 2) if d.avg_vcr else None,
                    "cpm": round(d.avg_cpm, 2) if d.avg_cpm else None,
                    "viewability_pct": (
                        round(d.avg_viewability * 100, 2) if d.avg_viewability else None
                    ),
                    "is_underperforming": d.is_underperforming,
                }
                for d in output.top_domains
            ],
            "top_10_domain_share_pct": round(output.top_n_domain_share * 100, 2),
            "insights": [
                {
                    "rule_id": i.rule_id,
                    "description": i.description,
                    "severity": i.severity.value,
                    "recommendation": i.recommendation,
                    "metrics": i.metrics,
                }
                for i in output.insights
            ],
        }
