# BPCR Review App (MVP)

Reads executed/handwritten Batch Production Control Record (BPCR) pages,
compares each recorded value against the digitized master specification,
and produces an observation report (page no., instruction, written value,
status).

## Pipeline
Capture (upload or phone camera) → Preprocess (deskew/contrast) →
Extract (vision LLM via OpenRouter, with fallback) → Compare (range/text
rule engine) → Report (in-app table + Excel export)

## Local setup
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit secrets.toml and add your real OPENROUTER_API_KEY, SUPABASE_URL, SUPABASE_KEY
streamlit run app.py
```

## Supabase setup (one-time)
1. Create a project at supabase.com
2. Go to **Project Settings → API**, copy the **Project URL** and the
   **anon/public** key (not `service_role` — never use that one here)
3. Go to **SQL Editor → New Query**, paste the contents of
   `supabase_schema.sql`, and run it once — this creates the `batches`
   and `operations` tables with permissive RLS policies (fine for a
   single-user internal tool; tighten before wider use)
4. Add `SUPABASE_URL` and `SUPABASE_KEY` to your secrets (see above)

## Deploy to Streamlit Community Cloud
1. Push this repo to GitHub (private recommended)
2. Go to share.streamlit.io → New app → select this repo → `app.py`
3. In App settings → Secrets, paste:
   ```
   OPENROUTER_API_KEY = "your-key-here"
   ```
4. Deploy — Streamlit Cloud builds and hosts automatically on every push

## Current scope — real-case build
Rebuilt around an actual uploaded master BPCR (multi-material charging
steps, IPC decision branch, repeating temperature logs, signature table):

- **Master spec**: `data/master_specs/apple_orange_batch.json` — 10
  operations, 4 materials (KSM/GRM typed), 3 known personnel
- Multi-material-per-operation extraction (e.g. APPLE + Orange charged
  in one step)
- Start/end time windows per operation (not just one instant)
- **Material reconciliation**: type-based two-sided tolerance (KSM ±2%,
  GRM ±5% per the BPCR's own notes), plus a widened acceptable range
  for the conditional Orange +10 kg addition, since whether that branch
  fires depends on an IPC lab result
- **Chronology check**: flags overlapping start/end *windows* for the
  same operator, not just identical single timestamps
- **Time-series log check** (`core/timeseries_checker.py`): validates
  Table-1/Table-2 style repeating readings against spec range and
  interval (e.g. every 30±5 min), flags missed/late readings
- **Personnel validation** (`core/personnel_validator.py`): cross-checks
  handwritten operator names against the master BPCR's Signature Table,
  fuzzy-matches minor handwriting variance, flags unrecognized names
- Supabase persistence extended: `operation_materials` and
  `timeseries_readings` tables (see `supabase_schema_v2.sql` — run
  after the original `supabase_schema.sql`)
- Process flow diagram: `apple_orange_process_flow.pdf` — visual
  reference showing the operation sequence and the IPC-1 decision
  branch, for human verification that the spec JSON matches the actual
  document. This is a human-readable companion, not what the app reads
  at runtime — the app always works from the structured spec JSON.

## Not yet built (post-MVP)
- Per-field cropping for higher extraction precision
- Full IPC lab-result-value extraction feeding the conditional branch
  automatically (currently the reconciler tolerates either branch
  outcome via a widened range, rather than confirming which branch
  actually occurred)
- Cross-batch chronology check (same operator, overlapping time,
  different batches)
- Model fallback chain testing at scale (router supports it, needs
  live validation)
- "Original" ALCOA pillar — overwrite/correction detection on raw
  images
- Tightening Supabase RLS policies if this moves beyond single-user use

## Repo structure
```
app.py                  Main Streamlit entry point
config/settings.py      Constants + secrets access
core/
  model_router.py         OpenRouter calls with model fallback chain
  preprocessor.py         Deskew + contrast enhancement
  extractor.py            Prompt building + vision extraction (fields + operations)
  comparator.py           Spec comparison rule engine
  report_builder.py       Observation table + Excel export
  chronology_checker.py   ALCOA attributability/contemporaneous check
  material_reconciler.py  ALCOA material quantity reconciliation
ui/
  upload_view.py          File upload / camera capture
  review_view.py          Results table + export button
  alcoa_view.py           Chronology conflicts + reconciliation display
data/master_specs/        Digitized BPCR specs (JSON)
tests/                     Unit tests
```
