# Post-Campaign Insights POC — Demo Scope & Implementation Plan

---

## 🎯 Demo Goal

Develop a **working local POC** that:

- Uploads **Campaign Report.xlsx** + **Domain Report.xlsx**
- Lets the user **select a Campaign ID**
- Generates a **4-tab reporting experience** (as per UI concept)
- Produces a **downloadable report artifact** (DOCX preferred, or at least a clean on-screen report ready for copy/paste)

---

## ✅ What “Success” Means (Today)

- End-to-end flow works (upload → select → generate → export)
- KPIs, tables, and charts render correctly
- Narrative text is generated (rule-based is acceptable)
- Export functionality works (**DOCX highly recommended**)

---

## 🧱 Work Breakdown

### 1. Local Streamlit App Skeleton
- Simple UI flow:
  1. Upload **2 Excel files**
  2. Select **Campaign ID**
  3. Click **Generate Report**

---

### 2. Input Parsing & Normalization
- Read both Excel files into **pandas DataFrames**
- Standardize column names
- Validate required columns
- Convert:
  - Dates → datetime
  - Metrics → numeric
- Fail fast with clear error messages if schema is invalid

---

### 3. Aggregations (Derived DataFrames)

Generate the following rollups:

1. **Campaign Total KPIs**
   - Impressions
   - Clicks
   - CTR
   - Spend
   - CPM
   - Viewability %
   - VCR %

2. **Weekly Performance**
   - Week
   - Impressions
   - CTR
   - Viewability
   - VCR
   - Spend
   - CPM

3. **Platform / Device Breakdown**
   - Platform
   - Device
   - Impressions share
   - CTR / VCR / CPM / Viewability

4. **Day-of-Week Performance**
   - Mon → Sun
   - Impressions
   - CTR
   - VCR
   - Spend

5. **Top Domains**
   - Domain
   - Impressions
   - CTR / VCR / CPM / Viewability
   - Impression share

---

## 📐 Data Logic (Recomputed Metrics)

> **All rollups must be recomputed** (do not trust Excel aggregates)

- **CTR** = `clicks / impressions`
- **CPM** = `(spend / impressions) * 1000`
- **Viewability % (rollup)**  
  `sum(viewable_impressions) / sum(impressions)`
- **VCR (proxy rollup)**  
  `sum(vcr_pct * impressions) / sum(impressions)`
  > Until true denominator is confirmed

### Domain-Specific Logic
- **Domain Share** = `domain_impressions / total_impressions`
- **Top-5 Share** = `sum(top_5_domain_impressions) / total_impressions`
- **Weekly Mix Shift**
  - `mix_week = impressions_week_domain / impressions_week_total`
  - `delta = mix_week - mix_prev_week`
- **Underperforming Domain Flag**
  - High impression share **AND**
  - Low CTR / VCR / Viewability or high CPM

---

## 🧠 Insight Rules (Rule-Based)

Thresholds defined in a **config file**:

- **Pacing Spike**
  - Week impressions ≥ **+50%** vs average week
- **CTR Anomaly**
  - Week CTR ≤ **70%** of campaign average
- **CTR Recovery**
  - Later week CTR ≥ **110%** of average
- **VCR Drop**
  - ≥ **3 percentage point** decline
- **Platform / Device Concentration**
  - Single platform/device ≥ **80%** of impressions
- **Domain Concentration**
  - Top domain ≥ **40%** impressions  
  - OR Top-5 ≥ **70%** impressions

Each insight should output:
- Description
- Severity (Green / Amber / Red)
- Recommendation snippet

---

## 🧩 UI Requirements (Streamlit)

### Core Interaction
- Upload **2 Excel files**
- Auto-detect available **Campaign IDs**
- Dropdown selection
- Single **“Generate Report”** button

### Color Semantics
- 🟢 Green = Good
- 🟠 Amber = Warning
- 🔴 Red = Critical

---

## 🗂️ Required Tabs (Must Have)

### **Tab 1 — Campaign Performance**
- KPI summary tiles
- Overall totals
- Weekly trend charts

---

### **Tab 2 — Platform & Temporal**
- Platform / device performance tables
- Day-of-week analysis
- Concentration warnings

---

### **Tab 3 — Inventory / Domain Pulse**
- Top domains table
- Domain concentration metrics
- Underperforming domain flags
- Mix shift commentary

---

### **Tab 4 — Generated Report**
- DOCX-like preview (structured text)
- Copy/paste-ready narrative
- **Export to DOCX button**

---

## 📤 Export (Recommended for Demo Impact)

Generate a **DOCX** using `python-docx`

**Document Title**  
> *Post Campaign Insights & Recommendations*

### Sections
1. Executive Snapshot
2. Performance Trends
3. Key Insights
4. Recommendations
5. Supporting Tables

---

## 📥 Inputs

- `Campaign Report.xlsx`
- `Domain Report.xlsx`

---

## 📤 Outputs

- Streamlit dashboard with:
  - KPIs
  - Charts
  - Tables
  - Narrative insights
- Downloadable **DOCX report**

---

## 🚫 Non-Scope (Explicitly Out)

- Cloud deployment
- GAM API integration
- Beeswax reconciliation
- Alerts or notifications
- Authentication / RBAC
- LLM Q&A layer

---

## 🧪 Functional Requirements Checklist

- [ ] Upload two Excel inputs
- [ ] Detect Campaign IDs
- [ ] Campaign selection
- [ ] KPI summary tiles
- [ ] Weekly trends
- [ ] Platform / device & DOW views
- [ ] Domain concentration analysis
- [ ] Narrative insights & recommendations
- [ ] DOCX export

---

## 🏁 End State (Demo-Ready)

A local Streamlit app that:
- Feels like a real post-campaign reporting product
- Generates insights deterministically
- Produces a clean, client-ready narrative artifact
- Can later be upgraded to LLM-powered reasoning

---