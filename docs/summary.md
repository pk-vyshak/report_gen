## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           POST-CAMPAIGN INSIGHTS                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│   UPLOAD     │ ──▶ │   INGEST     │ ──▶ │   ANALYZE    │ ──▶ │   OUTPUT    │
│  Excel Files │     │  & Clean     │     │  & Insights  │     │  UI + DOCX  │
└──────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
```

### 1. **Input** (Streamlit UI)
- Upload **Domain Report.xlsx** (required) + **Campaign Report.xlsx** (optional)
- Select **Campaign ID** from auto-detected dropdown
- Click **Generate Report**

### 2. **Ingestion** (`src/ingestion/`)
- Load Excel → Rename columns via schema → Clean types (currency, %, dates) → Enrich (week_start, is_weekend) → Validate with Pydantic

### 3. **Analytics** (`src/analytics/`)
|       Output           |                     What It Computes                                    |
|------------------------|-------------------------------------------------------------------------|
| **Campaign KPIs**      | Impressions, Clicks, Spend, CTR, CPM, Viewability, VCR (all recomputed) |
| **Weekly Performance** | Week-by-week breakdown with weighted metrics                            |
| **Platform Breakdown** | Device type share + CTR/VCR/CPM per platform                            |
| **Day-of-Week**        | Mon-Sun performance pattern                                             |
| **Top Domains**        | Impression share, underperforming flags                                 |
| **Insights**           | Rule-based alerts (🔴 Red / 🟠 Amber / 🟢 Green)                         |

### 4. **Insight Rules** (`src/analytics/insights.py`)
|           Rule         |           Trigger                |
|------------------------|----------------------------------|
| Pacing Spike           | Week impressions ≥ +50% vs avg   |
| CTR Anomaly            | Week CTR ≤ 70% of avg            |
| CTR Recovery           | Later week CTR ≥ 110% of avg     |
| VCR Drop               | ≥ 3pp week-over-week decline     |
| Platform Concentration | Single platform ≥ 80%            |
| Domain Concentration   | Top domain ≥ 40% OR Top-5 ≥ 70%  |

### 5. **Output**
- **Streamlit UI** → 4 tabs with KPI tiles, charts, tables, insights
- **DOCX Export** → Full report with embedded charts (PNG) + tables + recommendations

### Key Files
```
app.py                      ← Streamlit UI
src/
├── services/report_service.py  ← Orchestrator
├── ingestion/loader.py         ← Excel → DataFrame
├── analytics/
│   ├── calculator.py           ← All aggregations
│   ├── insights.py             ← Rule-based insights
│   └── expressions.py          ← Polars expressions
└── config/schema_registry.yaml ← Column mappings
```

### Run It
```bash
streamlit run app.py
```