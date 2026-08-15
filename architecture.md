# Architecture

## Overview

A Python FastAPI web application with PostgreSQL persistence, Jinja2 server-rendered frontend, and local Ollama AI integration. The system uses the Excel backtesting template as the formula and data-model reference but presents trades, analytics, and settings through a clean web journal UI — not as a spreadsheet replica.

## Technology Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Backend | Python 3.11+, FastAPI, Uvicorn | Async API server, routing, request handling |
| ORM | SQLAlchemy 2.x + asyncpg | Database models and async queries |
| DB | PostgreSQL 14+ | Relational persistence |
| Frontend | Jinja2 + minimal JS + Chart.js | Server-rendered pages, charts |
| AI | Ollama (local) | LLM-based trade analysis |
| Media | Local filesystem (`media/screenshots/`) | Screenshot storage |

## Data Model

### Trade
```
id: PK int
entry_date: date
entry_time: time
session: FK -> Session
pair: FK -> Instrument
setup: FK -> Strategy
probability: FK -> ProbabilityLevel
mtf_phase: FK -> MTFPhase
entry_news: str (optional)
management_news: str (optional)
entry_candle_size: float
mae_sl_buffer: float
mfe: float
max_r: float (computed)
fixed_r_target: float (computed)
screenshot_1: str (path, optional)
screenshot_2: str (path, optional)
screenshot_3: str (path, optional)
comments: str (optional)
day: int (derived)
day_name: str (derived)
month_number: int (derived)
month_name: str (derived)
year: int (derived)
quarter: int (derived)
total_r: float (computed)
is_win: bool (computed)
is_loss: bool (computed)
win_streak: int (computed)
loss_streak: int (computed)
peak_r: float (computed)
drawdown: float (computed)
max_drawdown: float (computed, global)
created_at: datetime
updated_at: datetime
```

### Lookup Tables
- **Session**: id, name, slug
- **Instrument**: id, name, slug, sl_buffer, fixed_r_target
- **Strategy**: id, name, slug
- **ProbabilityLevel**: id, name, slug
- **MTFPhase**: id, name, slug

### Settings (single-row config)
- **AppSettings**: id, current_year, default_analysis_period, etc.

## Calculation Engine

A dedicated `calculation_service.py` module:

1. **Per-trade calc**: Given `instrument.sl_buffer`, `entry_candle_size`, `mfe`, compute `max_r`.
   - If `mfe` is None or 0: return None.
   - If `mae_sl_buffer >= mfe`: return `-1`.
   - Else: `mfe / (entry_candle_size + instrument.sl_buffer)`.
   - Then cap at `instrument.fixed_r_target`; if negative return `-1`.
2. **Portfolio calc**: After any trade change, recalculate running `total_r`, streaks, `peak_r`, `drawdown`, `max_drawdown` for the affected sequence.
3. **Excel parity**: Unit test the first 100 imported trades against Excel cached values.

## Application Structure

```
trading-journal/
├── main.py                 # FastAPI app entry
├── config.py               # Settings from .env (Pydantic BaseSettings)
├── database.py             # SQLAlchemy engine/session
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── routers/
│   ├── trades.py           # Trade CRUD + list + filters
│   ├── settings.py         # Settings CRUD
│   ├── dashboard.py        # Summary stats, charts data
│   ├── analysis.py         # Yearly/monthly analysis endpoints
│   └── ai.py               # Ollama integration (future)
├── services/
│   ├── calculation_service.py
│   ├── import_service.py   # Excel importer
│   └── ai_service.py       # Ollama caller
├── templates/              # Jinja2 HTML
│   ├── base.html
│   ├── trades/
│   ├── dashboard/
│   └── analysis/
├── static/                 # CSS, JS, chart libraries
├── media/screenshots/      # Uploaded images
├── tests/
│   ├── test_calculations.py
│   └── test_import.py
├── .env                    # Secrets (gitignored)
├── .env.example
└── requirements.txt
```

## AI Integration (Future)

- Ollama endpoint: `POST /api/ai/insights`
- Input: summarized trade statistics (win rate per setup, session R, streak lengths, drawdown periods)
- Output: LLM-generated text insights (best setups, psychology flags, risk suggestions)
- Data sanitization: trade data is summarized before sending to Ollama; no raw P&L or identifying details leave the local machine.

## Environment & Secrets

- `.env` file (gitignored) stores:
  - `DATABASE_URL=postgresql+asyncpg://admin:admin@localhost:5432/trading_journal`
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `OLLAMA_MODEL=llama3`
- `.env.example` contains placeholder values for onboarding.

## Deployment Model

Local development only for now. Run with `uvicorn main:app --reload`. Access via `http://localhost:8000`.
