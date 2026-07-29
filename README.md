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

## Current MVP scope
- One master spec (`data/master_specs/sample_product_A.json`)
- One page at a time (upload or camera); operations persist to Supabase
  keyed by batch number, so they accumulate across pages AND across
  sessions/days for the same batch
- Whole-page extraction (single vision call, structured JSON response)
- Numeric range check + text/vocabulary match
- ALCOA checks:
  - **Chronology/attributability**: flags an operator recorded at identical timestamps across different operations (physically impossible)
  - **Material reconciliation**: sums quantity used per material across operations, compares to quantity indented within a loss tolerance
- Excel export of results

## ALCOA coverage
- **Accurate** — range/text comparator
- **Legible** — ILLEGIBLE flag on extraction
- **Attributable** — operator captured per operation; chronology conflicts surface attribution problems
- **Contemporaneous** — timestamp sequence check (chronology_checker.py)
- **Original** — not yet built; would need visual overwrite/correction detection on the raw image, beyond transcription

## Not yet built (post-MVP)
- Multi-product spec selection
- Per-field cropping for higher extraction precision
- Unit conversion (°F↔°C, mL↔L, etc.)
- Fuzzy text matching for handwriting variants
- Batch/multi-page processing UI polish (works, but no batch list/browse view yet)
- Cross-batch chronology check (same operator, overlapping time, different batches) — `storage.load_operations_by_operator()` exists but isn't wired into the UI yet
- Model fallback chain testing at scale (router supports it, needs live validation)
- "Original" ALCOA pillar — overwrite/correction detection on raw images
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
