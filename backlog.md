# Backlog

## Phase 1 — Setup & Excel Import
- [ ] Create Python virtual environment and install dependencies
- [ ] Create `.env` and `.env.example`
- [ ] Create PostgreSQL `trading_journal` database
- [ ] Design and run initial Alembic migration for all models
- [ ] Build Excel import service (openpyxl or pandas)
- [ ] Map Trades columns A:AF to model fields
- [ ] Map Settings sheet to Instrument lookup table + parameters
- [ ] Import ~1193 trades with validation
- [ ] Create basic trade list HTML view

## Phase 2 — Calculation Engine (COMPLETE)
- [x] Implement MAX R formula per instrument
- [x] Implement FIXED R TARGET cap
- [x] Implement running TOTAL R, WINS, LOSSES
- [x] Implement streak counters (WIN STREAK, LOSS STREAK)
- [x] Implement PEAK R, DRAWDOWN, MAX DRAWDOWN
- [x] Add recalculation script (`recalculate.py`)
- [x] Unit test first 10 trades against Excel cached values (±0.0001)
- [x] Recalculate all 35 trades in DB

## Phase 3 — Dashboard & UI (COMPLETE)
- [x] Summary cards template + data endpoint
- [x] Trade filter UI (year, month, session, instrument, setup, probability)
- [x] Chart.js integration for cumulative R curve
- [x] Monthly / session / instrument breakdown tables
- [x] Screenshot upload handler (`/media/screenshots/`)
- [x] Trade detail page with inline screenshots + upload form
- [x] Trade entry/edit form
- [x] Responsive CSS styling

## Phase 4 — AI Insights (COMPLETE)
- [x] Add Ollama client module (`ai_service.py`)
- [x] Build trade statistics summarizer
- [x] Create insights prompt templates
- [x] Add `/ai/` endpoint
- [x] AI review page in UI
- [ ] Cache AI responses to avoid redundant calls (future)

## Phase 5 — Automations (COMPLETE)
- [x] Scheduled task runner (APScheduler background job)
- [ ] Auto-import from new Excel files (future enhancement)
- [x] Weekly performance report generator
- [x] Drawdown/streak alert rules
- [x] Export trades + stats to CSV
