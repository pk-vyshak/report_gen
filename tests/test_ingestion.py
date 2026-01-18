from pathlib import Path
import sys

CURRENT_FILE = Path(__file__).resolve()
sys.path.append(str(CURRENT_FILE.parent.parent))

from src.ingestion.loader import DataIngestionPipeline

pipeline = DataIngestionPipeline(Path('src/config/schema_registry.yaml'))


try:
    df = pipeline.ingest(Path('Files/Input/Domain Report.xlsx'), validate=True)
    print('SUCCESS! All rows validated')
    print(f'Rows: {len(df)}, Columns: {len(df.columns)}')
    print()
    print('=== Schema ===')
    for name, dtype in df.schema.items():
        print(f'  {name}: {dtype}')
        
except Exception as e:
    print('VALIDATION FAILED!')
    print(e)