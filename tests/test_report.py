import json
from pathlib import Path
from src.services import ReportService

service = ReportService()
output = service.generate_report(
    campaign_id=4512,
    domain_report_path=Path('Files/Input/Domain Report.xlsx'),
    campaign_report_path=Path('Files/Input/Campaign Report.xlsx')
)

summary = service.generate_summary_dict(output)
print(json.dumps(summary, indent=2))