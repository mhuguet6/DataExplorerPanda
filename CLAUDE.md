# Data Explorer Panda — Project Context

> **For future Claude sessions.** This file is auto-loaded when Claude Code
> opens this project. Read it before doing anything substantial so you have
> the same mental model as the user — especially the architecture choices,
> naming conventions, and gotchas that aren't obvious from the code alone.

---

## 1. Elevator pitch

A two-part learning project that loads, cleans, analyzes, and visualizes the
**seaborn Titanic dataset** in Python (pandas + seaborn), then displays the
results in a **React dashboard**.

It's structured to *teach* pandas, not just *use* it — every cleaning and
feature-engineering step is documented in the Pipeline tab of the dashboard
with code snippets and reasoning. The user is treating it as a portfolio /
study project.

The Dashboard / Pipeline tabs run **without an API server** — the backend
writes static files and the frontend reads them. The **Upload & Clean**
tab is the one exception: it needs runtime pandas (arbitrary CSVs can't be
pre-baked), so a small FastAPI service runs at `localhost:8000` and Vite
proxies `/api/*` to it.

---

## 2. Tech stack

| Layer | Tool | Version | Role |
|---|---|---|---|
| Data | pandas | >=2.0 | Load, clean, transform |
| Math | numpy | >=1.24 | Log, z-scores, np.inf bins |
| Dataset source | seaborn | >=0.13 | Provides Titanic via `sns.load_dataset` |
| Charts | matplotlib + seaborn | >=3.7 / >=0.13 | Static PNGs into `outputs/charts/` |
| Frontend | React | ^18.3.1 | Dashboard SPA |
| Build | Vite | ^5.4.10 | Dev server + bundler |
| Styling | Plain CSS Modules | — | One `.module.css` per component, no Tailwind/UI lib |

**No** databases, **no** API server, **no** state management library,
**no** routing library (two tabs, kept as local React state).

---

## 3. Architecture (the one diagram that explains everything)

```
seaborn.load_dataset
        │
        ▼
┌──────────────────┐
│   data/raw/      │  ← cached on first run
│   titanic.csv    │
└────────┬─────────┘
         │  load_data.py → clean_data.py → analyze.py → visualize.py
         ▼
┌──────────────────┐
│ data/processed/  │
│ titanic_clean.csv│
└────────┬─────────┘
         │
         ▼   export.py orchestrates everything ↓
┌──────────────────────────────────────────────┐
│        backend/outputs/                      │
│   ├─ insights.json  (~22 KB, single source)  │
│   └─ charts/*.png   (7 files)                │
└─────────────────┬────────────────────────────┘
                  │
                  │  npm run sync  (predev + prebuild hook)
                  ▼
┌──────────────────┐
│ frontend/public/ │  ← React reads from here
└────────┬─────────┘
         │
         ▼
  React Dashboard  (http://localhost:5173)
```

**The contract between the two halves is `insights.json`.** Its schema is
the architectural backbone — change it carefully.

---

## 4. Folder structure

```
DataExplorerPanda/
├── CLAUDE.md                ← this file
├── README.md                ← end-user docs (setup, learning goals, examples)
├── .gitignore
│
├── backend/
│   ├── requirements.txt     ← pandas, numpy, matplotlib, seaborn
│   ├── .venv/               ← virtualenv (gitignored)
│   ├── data/
│   │   ├── raw/titanic.csv             ← cached on first run
│   │   └── processed/titanic_clean.csv ← after cleaning pipeline
│   ├── outputs/             ← consumed by the frontend
│   │   ├── charts/          ← 7 PNGs, regenerated on every export
│   │   └── insights.json    ← single payload for the dashboard
│   └── src/
│       ├── load_data.py     ← Phase 1: load + cache raw CSV
│       ├── clean_data.py    ← Phase 2: impute, drop, filter, feature engineer, encode
│       ├── analyze.py       ← Phase 3: groupby/crosstab/correlation. Returns dataframes, never prints
│       ├── visualize.py     ← Phase 4: 7 charts. Each function returns {filename,title,caption}
│       ├── export.py        ← Phase 5: orchestrator + writes insights.json
│       ├── suggest_clean.py ← Upload & Clean: suggestion engine + step applier (pure pandas)
│       └── api.py           ← Upload & Clean: FastAPI service (/api/upload, /api/clean, /api/download)
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── scripts/
    │   └── sync-backend-outputs.js   ← runs on `predev` / `prebuild`
    ├── public/              ← gitignored, populated by sync script
    └── src/
        ├── main.jsx
        ├── index.css        ← global theme tokens (CSS variables)
        ├── App.jsx          ← single fetch, tab dispatch
        ├── App.module.css
        └── components/      ← one folder, all components
            ├── TabBar.{jsx,module.css}            ← horizontal tab nav
            ├── KeyMetrics.{jsx,module.css}        ← 6-card top row (Dashboard)
            ├── DatasetOverview.{jsx,module.css}   ← shape + missing + transformations
            ├── KeyFindings.{jsx,module.css}       ← numbered insight bullets
            ├── ChartsGrid.{jsx,module.css}        ← 2-col grid of <figure>s with PNGs
            ├── TablesGrid.{jsx,module.css}        ← handles BOTH row-tables AND matrix-tables
            ├── PipelineView.{jsx,module.css}      ← Pipeline tab: 5 sections, 18 step cards
            └── UploadClean.{jsx,module.css}       ← Upload tab: state machine (idle → suggested → cleaned)
```

---

## 5. The data: dataset & dimensions

- **Source:** `seaborn.load_dataset("titanic")` — 891 rows × 15 columns
- **After pipeline:** 888 rows × 25 columns
  - Rows: −3 (dropped fare > $300 outliers)
  - Cols: −4 dropped (`class`, `alive`, `embark_town`, `adult_male`)
  - Cols: +14 engineered (see below)

**Engineered columns** (their existence is part of the contract):

| Column | Source | Step |
|---|---|---|
| `family_size` | `sibsp + parch + 1` | feature eng |
| `has_family` | `family_size > 1` (int) | feature eng |
| `is_minor` | `age < 18` (int) | feature eng |
| `age_group` | `pd.cut(age, [0,12,17,59,inf])` → Child/Teen/Adult/Senior | feature eng |
| `fare_per_person` | `fare / family_size` | feature eng |
| `fare_tier` | `pd.qcut(fare, q=4)` → Low/Mid/High/Premium | feature eng |
| `cabin_known` | `deck != 'Unknown'` (int) | feature eng |
| `is_female` | `sex == 'female'` (int) | encoding |
| `emb_C`, `emb_Q`, `emb_S` | `pd.get_dummies(embarked)` | encoding |
| `log_fare` | `np.log1p(fare)` | encoding |
| `age_z`, `fare_z` | z-score normalization | encoding |

---

## 6. Backend pipeline (5 layers)

Run order (chained automatically by `export.py`):

1. **`load_data.py`** — `load_titanic()` returns a DataFrame; caches a CSV on first run.
2. **`clean_data.py`** — `clean(df)` runs:
   - Fill embarked (mode) → fill deck ("Unknown") → impute age (groupby median) → filter fare outliers → drop redundant cols → add derived features → encode & normalize.
3. **`analyze.py`** — pure functions returning DataFrames or dicts. **No prints, no plots inside any function.** This separation is load-bearing: it lets `visualize.py` and `export.py` reuse the same numbers without recomputing.
4. **`visualize.py`** — builds 7 PNG charts. Each chart function returns `{filename, title, caption}` so the same metadata can be embedded in `insights.json`.
5. **`export.py`** — orchestrator. Calls everything, builds the payload, writes `insights.json`. Also home to two big constants:
   - `TRANSFORMATIONS` — metadata about what cleaning did (used by Dataset Overview component)
   - `PIPELINE_SECTIONS` — the annotated walkthrough rendered in the Pipeline tab. Each step has `{title, why, code, result}`. **This is documentation that lives next to the pipeline so it can't drift out of sync.**

**Entrypoint:** `python src/export.py` runs the full pipeline end-to-end. There is no `main.py` — `export.py` is the orchestrator.

---

## 7. `insights.json` schema (the contract)

```jsonc
{
  "dataset": {
    "name": "Titanic",
    "source": "seaborn.load_dataset('titanic')",
    "raw_shape": [891, 15],
    "final_shape": [888, 25],
    "columns": [...],
    "missing_before": { "age": 177, "deck": 688, ... },
    "missing_after": {},
    "transformations": {
      "dropped": [...],
      "added": [...],
      "imputed": [{ "column": ..., "method": ... }],
      "filtered": [{ "rule": ..., "rows_removed": ..., "reason": ... }]
    }
  },
  "metrics": {            // 6 headline numbers for KeyMetrics row
    "total_passengers", "survival_rate", "avg_age", "avg_fare",
    "pct_female", "pct_first_class"
  },
  "tables": {             // dispatched on shape by TablesGrid
    "<key>": { "title", "rows": [{...}] },      // row-table
    "<key>": { "title", "matrix": { row: { col: value } } }  // matrix-table
  },
  "key_findings": [ "...", "..." ],   // 6 sentences for KeyFindings
  "charts": [
    { "filename": "01_age_histogram.png", "title": "...", "caption": "..." }
  ],
  "pipeline_sections": [
    {
      "id": "loading", "title": "1. Loading", "summary": "...",
      "steps": [{ "title", "why", "code", "result" }]
    }
  ]
}
```

The frontend imports this *one* file. No other fetches happen.

---

## 8. Frontend structure

### Tabs

The dashboard has **3 tabs**, controlled by local `useState` in `App.jsx`:

| Tab | id | Content | Backend |
|---|---|---|---|
| **Dashboard** | `dashboard` | KeyMetrics + (DatasetOverview ∥ KeyFindings) + ChartsGrid + TablesGrid | static `insights.json` |
| **Pipeline** | `pipeline` | PipelineView — 5 sections, 18 numbered step cards | static `insights.json` |
| **Upload & Clean** | `upload` | UploadClean — drop-zone → suggestion list → cleaned preview + download | FastAPI on :8000 |

`TabBar` component renders the nav; it's just buttons with `aria-selected` and an underline on the active tab. No routing.

### Data flow inside React

```
App.jsx
  ├─ useEffect → fetch('/insights.json') → setInsights
  ├─ TabBar (active, onChange)
  ├─ [if dashboard]
  │    ├─ KeyMetrics      (insights.metrics)
  │    ├─ DatasetOverview (insights.dataset)
  │    ├─ KeyFindings     (insights.key_findings)
  │    ├─ ChartsGrid      (insights.charts)
  │    └─ TablesGrid      (insights.tables)
  └─ [if pipeline]
       └─ PipelineView    (insights.pipeline_sections)
```

### Component-level notes

- **`KeyMetrics`** — has a hardcoded `METRIC_DEFS` array (label + formatter per metric). If a new metric key is added to the JSON, it won't show until added here.
- **`DatasetOverview`** — renders `transformations.dropped|added|imputed|filtered`. Tolerant of `filtered` being missing (conditional render).
- **`TablesGrid`** — dispatches on `{rows}` vs `{matrix}` keys. Adding a third shape would require extending this component.
- **`PipelineView`** — iterates `pipeline_sections`, increments a `stepCounter` across sections so users see "Step 1" through "Step 18".

---

## 9. Color palette & theme

### CSS variables (defined in `frontend/src/index.css`)

```css
--bg:        #0f172a   /* page background, dark slate */
--panel:     #1e293b   /* card / panel background */
--panel-2:   #273549   /* inline code, deeper panel */
--border:    #334155   /* card borders, separators */
--text:      #e2e8f0   /* primary text */
--text-dim:  #94a3b8   /* secondary text, labels */
--accent:    #38bdf8   /* cyan — links, active tab, numbers */
--good:      #4ade80   /* green — success states, "Result" tag */
--bad:       #f87171   /* red — error states */
```

**Aesthetic:** dark mode with a single cyan accent (#38bdf8). High contrast, monochrome panels, accent reserved for interactive / important elements.

### Chart palette (defined in `backend/src/visualize.py`)

- Default seaborn theme: `style="whitegrid"`, `context="talk"`, `palette="deep"`
- DPI: 110 (saved at default)
- **`SURVIVED_PALETTE = {0: "#d9534f", 1: "#5cb85c"}`** — red = died, green = survived. Used consistently across the histogram, scatter, and any chart involving survived. **If you add a new chart involving survival, reuse this palette.**

---

## 10. Conventions & design decisions

These are the conventions baked into the codebase. Follow them when adding code.

### Backend

- **Analysis functions return data, never print or plot.** This is the single most important convention. `analyze.py` has zero `plt.` or `print()` calls inside functions. The same numbers flow into both the JSON (via export) and the charts (via visualize).
- **`observed=True` on every groupby** with a categorical column (`age_group`, `fare_tier`). Without it, pandas emits rows for empty categories.
- **DataFrame → JSON conversion goes through `df.to_json()`, not `df.to_dict()`.** `to_dict()` leaves NaN as float('nan') (json.dumps can't serialize) and numpy types (also can't serialize). `to_json` handles both; `json.loads` brings the result back to native Python.
- **Use `np.inf` for open-ended bin edges**, never hardcoded max values.
- **`PIPELINE_SECTIONS` lives in `export.py`**, not next to each src file. The pipeline is documented as one story, not as scattered docstrings.

### Frontend

- **Single fetch, single state.** All UI props come from one `insights.json`. No second fetch, no per-component data loading.
- **Plain CSS Modules.** No utility classes, no styled-components, no Tailwind. One `.module.css` per component.
- **No routing library.** Tab state is local React state in `App.jsx`.
- **Tables auto-iterate columns.** Adding a numeric column to the backend will show up in tables automatically. Adding a new *metric* requires editing `KeyMetrics.METRIC_DEFS`.

---

## 11. How to run

### First time setup

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### Daily run

The app now needs **two terminals running concurrently**:

```bash
# Terminal A — API server (required for the Upload & Clean tab)
cd backend
source .venv/bin/activate
uvicorn api:app --app-dir src --reload --port 8000

# Terminal B — frontend
cd frontend
npm run dev                 # http://localhost:5173
```

The Dashboard / Pipeline tabs work without Terminal A (they read static
`insights.json`). The Upload tab will throw `HTTP 500` if Terminal A is
missing — Vite's proxy logs it as `ECONNREFUSED` to :8000.

If you change the Titanic pipeline, regenerate static artifacts:

```bash
cd backend && source .venv/bin/activate && python src/export.py
```

### Running individual phases

Each backend script is independently runnable:

```bash
python src/load_data.py     # prints dataset overview
python src/clean_data.py    # prints before/after of cleaning
python src/analyze.py       # prints every analysis table
python src/visualize.py     # regenerates 7 PNGs
python src/export.py        # chains all of the above + writes insights.json
```

### Re-syncing after backend changes (without restarting Vite)

```bash
cd frontend && npm run sync
```

---

## 12. Where to find things — file index

| Looking for… | File |
|---|---|
| The full pipeline orchestrator | `backend/src/export.py` |
| Cleaning + feature engineering | `backend/src/clean_data.py` |
| Groupby / crosstab / correlation logic | `backend/src/analyze.py` |
| Chart generation | `backend/src/visualize.py` |
| The Pipeline tab's step content | `backend/src/export.py` → `PIPELINE_SECTIONS` |
| The Dashboard tab's metric definitions | `frontend/src/components/KeyMetrics.jsx` → `METRIC_DEFS` |
| Color palette | `frontend/src/index.css` (CSS vars) |
| Chart palette (red/green) | `backend/src/visualize.py` → `SURVIVED_PALETTE` |
| Tab state / dispatch | `frontend/src/App.jsx` |
| Sync script (backend → frontend) | `frontend/scripts/sync-backend-outputs.js` |
| Upload & Clean: suggestion rules | `backend/src/suggest_clean.py` → `suggest()` |
| Upload & Clean: API endpoints | `backend/src/api.py` |
| Upload & Clean: state machine | `frontend/src/components/UploadClean.jsx` |
| Vite → uvicorn proxy | `frontend/vite.config.js` → `server.proxy` |

---

## 13. Gotchas & non-obvious things

- **`adult_male` derivation has a NaN-handling quirk.** Seaborn's `adult_male` assumes "adult" when age is missing. So you can't reproduce it with `(sex=='male') & (age>=16)` — you need `(sex=='male') & ((age>=16) | age.isna())`. The threshold is **16**, not 18.
- **CSV round-trip casts ints to floats.** When `analyze.py` reads from `titanic_clean.csv` instead of running cleaning in-memory, count columns come back as floats. The chart label formatter handles this by casting `int(row['n'])` for display.
- **Sync script wipes `public/`.** Every `npm run sync` does `rmSync(publicDir)` then `cpSync(...)`. That's intentional (guarantees consistency) but means anything dropped manually into `frontend/public/` will be deleted.
- **Vite caches.** After backend changes, if the page looks stale, the issue is almost always that `sync` didn't run. `npm run dev` does it via `predev`; manual changes need `npm run sync`.
- **`pd.qcut` can fail on ties.** If a column has many repeated values (not currently an issue but could be after a swap), `pd.qcut` raises `ValueError: Bin edges must be unique`. Fix: `pd.qcut(..., duplicates='drop')`.
- **The PNG charts include the `is_female` column in the correlation heatmap.** The heatmap is sized at `figsize=(11, 9)` specifically because of the 11×11 matrix — if you add more cols to `CORRELATION_COLS` in `analyze.py`, bump this size or labels will overlap.

---

## 14. What's NOT in scope (skip-list)

The user explicitly chose to keep the project simple. **Don't add these** without asking:

- ~~A real backend API~~ — we added a small FastAPI service for the Upload & Clean tab (May 2026). Anything beyond that surface should still be questioned.
- A UI library (MUI, Mantine, Tailwind) — chose plain CSS Modules
- A state management library (Redux, Zustand) — single useState is enough
- A router (react-router) — only 2 tabs
- A `main.py` orchestrator — `export.py` already does this
- ML / modeling — out of scope for this iteration (called out as a future extension in README)
- Interactive charts (Plotly, Recharts) — static PNGs were chosen for simplicity

If the user asks for any of the above, fine — but don't pre-emptively add them.

---

## 15. User collaboration notes

- The user is comfortable with technical detail and Q&A — they ask "explain step #N" style questions about the Pipeline tab. When answering, show real numbers from the dataset to back up claims; don't just describe abstractly.
- They prefer **proceeding phase-by-phase** with explicit checkpoints. When making big changes, summarize what you're about to do *before* doing it.
- They notice mismatches between claims and reality — if the Pipeline tab text says "X happens", the code should actually do X. Keep these in sync.
- They value honest caveats over confident-sounding lies. When you can't visually inspect a UI change, **say so**.
