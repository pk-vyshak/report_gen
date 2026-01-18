from pathlib import Path
import sys

CURRENT_FILE = Path(__file__).resolve()
sys.path.append(str(CURRENT_FILE.parent.parent))

from src.ingestion.loader import DataIngestionPipeline
from src.analytics import AnalyticalEngine

# Load data
pipeline = DataIngestionPipeline(Path('src/config/schema_registry.yaml'))
df = pipeline.ingest(Path('Files/Input/Domain Report.xlsx'), validate=True)

# Create engine
engine = AnalyticalEngine(df=df, campaign_goal=10_000_000)

print('=== StatPack Summary ===')
stat_pack = engine.get_stat_pack()
print(f'Campaign ID: {stat_pack.campaign_id}')
print(f'Date Range: {stat_pack.date_range[0]} to {stat_pack.date_range[1]}')
print(f'Total Impressions: {stat_pack.total_impressions:,}')
print(f'Total Clicks: {stat_pack.total_clicks:,}')
print(f'Avg CTR: {stat_pack.avg_ctr * 100:.4f}%')
print()

print('=== Temporal Stats ===')
temporal = engine.get_temporal_stats()
print(f'Weeks analyzed: {len(temporal.weekly_totals)}')
print(f'Spikes detected: {len(temporal.spikes)}')
for spike in temporal.spikes[:3]:
    print(f'  {spike.week_start}: {spike.pct_change*100:.1f}% in {spike.metric_name}')
print()

print('=== Anomaly Detection ===')
anomalies = engine.detect_anomalies('ctr')
print(f'Threshold: {anomalies.threshold_used} std')
print(f'Anomalies found: {len(anomalies.anomalies)}')
for a in anomalies.anomalies:
    print(f'  {a.week_start}: CTR {a.direction} mean (z={a.z_score:.2f})')
print()

print('=== Delivery Pattern ===')
delivery = engine.get_delivery_pattern()
print(f'Back-loaded: {delivery.is_back_loaded}')
print(f'Last 25% delivered: {delivery.last_quarter_delivery_pct*100:.1f}%')
print(f'Trend: {delivery.daily_trend}')
print()

print('=== Weekend Lift ===')
efficiency = engine.get_efficiency_metrics()
if efficiency.overall_weekend_lift:
    print(f'CTR Lift: {efficiency.overall_weekend_lift*100:.2f}%')
else:
    print('No weekend data')
print()

print('=== Platform Gaps ===')
for gap in efficiency.performance_gaps:
    print(f'  {gap.metric_name}: {gap.gap_pct*100:.1f}% gap')
    print(f'    Best: {gap.max_platform} ({gap.max_value:.4f})')
    print(f'    Worst: {gap.min_platform} ({gap.min_value:.4f})')
