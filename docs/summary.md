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


### Calculations

## Calculations Rundown

### Campaign Total KPIs (Recomputed from raw data)

|     Metric      |                   Formula                       |        Note         |
|-----------------|-------------------------------------------------|---------------------|
| **Impressions** | `sum(impressions)`                              | Raw sum             |
| **Clicks**      | `sum(clicks)`                                   | Raw sum             |
| **Spend**       | `sum(spend)`                                    | Raw sum             |
| **CTR**         | `sum(clicks) / sum(impressions)`                | Not averaged!       |
| **CPM**         | `(sum(spend) / sum(impressions)) × 1000`        | Cost per mille      |
| **Viewability** | `sum(viewable_impressions) / sum(impressions)`  | Weighted            |
| **VCR**         | `sum(vcr_pct × impressions) / sum(impressions)` | Weighted by volume  |-------------------------------------------------------------------------------------------

### Weekly Performance (Per week_start)

```
GROUP BY week_start:
  impressions     = sum(impressions)
  clicks          = sum(clicks)
  spend           = sum(spend)
  CTR             = sum(clicks) / sum(impressions)
  CPM             = (sum(spend) / sum(impressions)) × 1000
  VCR             = sum(vcr_pct × impressions) / sum(impressions)
  Viewability     = sum(viewable_impressions) / sum(impressions)
```

**Week-over-Week Change:**
```
WoW % = (current_week - previous_week) / previous_week × 100
```
---

### Platform/Device Breakdown (Per platform_device_type)

```
GROUP BY platform_device_type:
  impressions       = sum(impressions)
  clicks            = sum(clicks)
  spend             = sum(spend)
  impression_share  = platform_impressions / total_impressions
  CTR               = sum(clicks) / sum(impressions)
  CPM               = (sum(spend) / sum(impressions)) × 1000
  VCR               = sum(vcr_pct × impressions) / sum(impressions)
```
---

### Day-of-Week Performance (Per day_of_week)

```
GROUP BY day_of_week:  # Monday → Sunday
  impressions  = sum(impressions)
  clicks       = sum(clicks)
  spend        = sum(spend)
  CTR          = sum(clicks) / sum(impressions)
  VCR          = sum(vcr_pct × impressions) / sum(impressions)
```

---

### Top Domains (Per domain)

```
GROUP BY domain:
  impressions       = sum(impressions)
  clicks            = sum(clicks)
  spend             = sum(spend)
  CTR               = sum(clicks) / sum(impressions)
  CPM               = (sum(spend) / sum(impressions)) × 1000
  VCR               = sum(vcr_pct × impressions) / sum(impressions)
  Viewability       = sum(viewable_impressions) / sum(impressions)
  impression_share  = domain_impressions / total_impressions

Top-N Share = sum(top_N_domain_impressions) / total_impressions
```

**Underperforming Flag:**
```python
is_underperforming = (
    impression_share >= 5%  AND
    CTR < 25th_percentile_CTR
)
```

---

### Insight Rule Calculations

|         Rule                 |                     Calculation                     |
|------------------------------|-----------------------------------------------------|
| **Pacing Spike**             | `week_imps >= avg_weekly_imps × 1.5`                |
| **CTR Anomaly**              | `week_CTR <= campaign_CTR × 0.70`                   |
| **CTR Recovery**             | `week_CTR >= campaign_CTR × 1.10` (later half only) |
| **VCR Drop**                 | `prev_week_VCR - curr_week_VCR >= 0.03` (3 pp)      |
| **Platform Concentration**   | `platform_share >= 80%`                             |
| **Top Domain Concentration** | `top1_share >= 40%`                                 |
| **Top-5 Concentration**      | `top5_share >= 70%`                                 |

---

### Key Principle

> **All rollup metrics are RECOMPUTED** from raw row-level data.  
> Excel pre-aggregated values are ignored to ensure accuracy.