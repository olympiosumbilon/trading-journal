# Changelog

## v0.6.0 — 2026-08-13

### Added
- `services/automation_service.py` — CSV export, weekly report, alert checker
- `routers/automations.py` — automation endpoints (`/automations/`)
- `templates/automations/index.html` — automation registry + alert display
- `templates/automations/weekly_report.html` — weekly performance report
- APScheduler background job (every 30 min) for alert monitoring
- Dashboard alerts banner (shows active drawdown/streak warnings)
- `apscheduler` library for scheduled tasks
- CSV export with full trade history (all columns)

### Notes
- Alerts check: max drawdown <-3R, loss streak ≥3, win streak ≥5, negative total R
- Weekly report covers last 7 days

## v0.5.0 — 2026-08-13

### Added
- `services/ai_service.py` — trade stats summarizer + Ollama API caller
- `routers/ai.py` — AI review endpoint (`/ai/`)
- `templates/ai/review.html` — AI insights page (Setup, Session, Risk, Actions)
- AI Review navigation link in base template
- `requests` library for Ollama HTTP calls
- `.env` updated with `OLLAMA_MODEL=phi3`

### Notes
- AI analysis powered by local Ollama (`phi3` model). No cloud, no data leaves the machine.

## v0.4.0 — 2026-08-13

### Added
- Full trade CRUD web UI (`routers/trades.py`)
- Filterable trade list (year, month, session, instrument, setup, probability)
- Trade entry/edit form (`templates/trades/form.html`)
- Trade detail page with stats and screenshot viewer (`templates/trades/detail.html`)
- Dashboard with summary cards, cumulative R chart (Chart.js), monthly/session/instrument breakdowns (`routers/dashboard.py`)
- Screenshot upload endpoint (3 slots per trade)
- Responsive CSS (`static/style.css`)

## v0.3.0 — 2026-08-13

### Added
- `services/calculation_service.py` — MAX R, FIXED R TARGET, portfolio stats engine
- `tests/test_calculations.py` — validation suite against Excel cached values
- `recalculate.py` — batch recalculation script for all trades
- All 35 trades recalculated with derived fields (TOTAL R, streaks, drawdown, peak)

### Changed
- `handoff.md` updated with Phase 2 status and validation results

## v0.2.0 — 2026-08-13

### Added
- Python venv with FastAPI, SQLAlchemy (sync), psycopg, Jinja2, openpyxl
- PostgreSQL `trading_journal` database + lookup tables + trades table
- `.env` and `.env.example` (credentials via environment only)
- `config.py`, `database.py`, `models.py`, `main.py`
- `routers/trades.py` — trade list endpoint with eager-loaded relationships
- `services/import_service.py` + `run_import.py` — Excel importer
- `templates/` (base, index, trades/list) + `static/style.css`
- `requirements.txt`
- 35 trades imported from Excel with cached values
- Homepage and trade list page working

### Changed
- Switched from async SQLAlchemy (asyncpg) to **synchronous SQLAlchemy** (psycopg sync) due to Python 3.14 + Windows async driver incompatibilities (DEC-008)
- Updated `handoff.md`, `memory.md`, `DECISIONS.md` with Phase 1 status and driver compatibility notes

## v0.1.0 — 2026-08-13

### Added
- KOS project scaffold: README, AGENTS, PROJECT-CONTEXT, memory, handoff, DECISIONS, requirements, architecture, roadmap, backlog, changelog
- Excel source reference mapping all sheets, columns, and formulas
- ADR decision template under `docs/decisions/`
- `.gitignore` for secrets, media, and local state

### Notes
- Application code not yet started. This release is documentation-only.
