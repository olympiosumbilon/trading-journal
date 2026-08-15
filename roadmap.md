# Roadmap

## Phase 1 — Setup & Excel Import
**Goal**: Working FastAPI skeleton, PostgreSQL schema, and all ~1193 trades imported from Excel.

- Python venv + FastAPI + SQLAlchemy + asyncpg + Jinja2
- `.env` and `.env.example`
- PostgreSQL `trading_journal` database
- SQLAlchemy models (Trade, Session, Instrument, Strategy, ProbabilityLevel, MTFPhase)
- Excel import service (reads all 4 sheets, maps columns, inserts rows)
- Validation: first 100 trades match Excel cached values
- Trade CRUD API + basic list view

## Phase 2 — Calculation Engine
**Goal**: Replicate all Excel formulas exactly.

- `calculation_service.py`: MAX R, FIXED R TARGET, TOTAL R, WINS/LOSSES, streaks, PEAK R, DRAWDOWN, MAX DRAWDOWN
- Trigger recalculation on trade create/update/delete or Settings change
- Unit tests against Excel
- Settings CRUD and per-instrument parameter management

## Phase 3 — Dashboard & UI
**Goal**: Replace SUMMARY and Yearly Analysis sheets with interactive web views.

- Summary cards (win rate, total R, profit factor, expectancy, avg R)
- Filterable trade table (by year, month, quarter, session, pair, setup, probability)
- Charts: cumulative R, drawdown, monthly/yearly bars, session/pair performance
- Screenshot upload and inline display
- Trade detail page with all fields + screenshots

## Phase 4 — AI Insights (Ollama)
**Goal**: Local AI analyzes trade history and surfaces patterns.

- Ollama integration module
- Summarize trade stats into structured prompts
- Insights endpoint: best setups, worst sessions, tilt detection, risk management flags
- AI review page in the UI

## Phase 5 — Automations
**Goal**: Reduce manual work and add proactive alerts.

- Scheduled import from new Excel exports
- Weekly/monthly automated report generation
- Alert rules (e.g., drawdown threshold, streak limit)
- Export to PDF/CSV
