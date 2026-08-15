---
title: Project Memory
type: memory
status: active
owner: "Trading Journal"
created: 2026-08-13
updated: 2026-08-13
ai_access: internal
ai_generated: true
review_status: draft
---

# Project Memory

Store only approved durable decisions, constraints, terminology, compatibility requirements, and lessons.

## Excel Source Knowledge

The source workbook `My Strategy Backtesting Template (2024) - V1.2.xlsx` has 4 sheets. It is a **reference only** for the data model and formula logic. The web application is a **standalone trading journal** with its own UI; the Excel is not replicated visually.

| Sheet | Purpose | Key Content |
| --- | --- | --- |
| Trades | Per-trade log (35 data rows; ~1193 XML rows include empty formula templates) | DATE, ENTRY TIME, SESSION, PAIR, SETUP, PROBABILITY, MTF PHASE, ENTRY/MGMT NEWS, ENTRY CANDLE SIZE, MAE SL BUFFER, MFE, calculated MAX R, FIXED R TARGET, SCREENSHOTS, COMMENTS, derived DAY/MONTH/YEAR/QUARTER, TOTAL R, WINS, WIN STREAK, LOSSES, LOSS STREAK, PEAK R, DRAWDOWN, MAX DRAWDOWN |
| SUMMARY | Aggregated stats | COUNTIFS/SUMIFS/AVERAGEIFS by year, instrument, session |
| Yearly Analysis | Monthly/quarterly breakdown | IF/COUNTIFS/SUMIFS/SUM/MAXIFS per year |
| Settings | Parameters lookup | SESSIONS, INSTRUMENTS, STRATEGIES, PROBABILITIES, MTF PHASES, YEARS; per-instrument SL BUFFER (J4:J8) and FIXED R TARGET (K4:K8) |

### Trades Column Headers (Row 2)

A: DATE (DD/MM/YY) | B: ENTRY TIME | C: SESSION | D: PAIR | E: SETUP | F: PROBABILITY | G: MTF PHASE | H: ENTRY NEWS | I: MANAGEMENT NEWS | J: ENTRY CANDLE SIZE | K: MAE SL BUFFER | L: MFE | M: MAX R | N: FIXED R TARGET | O: SCREENSHOT 1 | P: SCREENSHOT 2 | Q: SCREENSHOT 3 | R: COMMENTS | S: DAY | T: DAY (duplicate or related) | U: MONTH NUMBER | V: MONTH NAME | W: YEAR | X: QUARTER | Y: TOTAL R | Z: WINS | AA: WIN STREAK | AB: LOSSES | AC: LOSS STREAK | AD: PEAK R | AE: DRAWDOWN | AF: MAX DRAWDOWN

### Core Formulas

- **MAX R (M)**: `IF(L="","",IFS(D=Settings!C4, IF(K>=Settings!J4, -1, L/(J+Settings!J4)), ... D=Settings!C8 ...))`
  - Computes R-multiple from MFE / (entry candle size + SL buffer for that instrument)
  - Returns `-1` if the MAE SL buffer was hit (stop loss)
  - Varies per instrument (Settings C4:C8)
- **FIXED R TARGET (N)**: `IFS(... IF(M>=Settings!K4, Settings!K4, -1) ...)`
  - Caps MAX R at the fixed R target for that instrument (Settings K4:K8)
  - Returns `-1` if the trade was a loss
- **Derived**: TOTAL R (running sum of M), WINS/LOSSES counters, streaks, PEAK R (running max), DRAWDOWN (peak - total R), MAX DRAWDOWN (`MIN(AE:AE)`)

### Settings Mapping

Settings B4:B9: SESSION names (LDN, LDN LULL, NY, NY LULL, ASIA, ASIA LULL)
Settings C4:C8: INSTRUMENT names (BTCUSD, ETHUSD, SOLUSD, Instrument 4, Instrument 5)
Settings D4:D11: STRATEGY names
Settings E4:E8: PROBABILITY labels
Settings F4:F8: MTF PHASE labels
Settings G4:G6: YEARS (2022, 2023, 2024)
Settings J4:J8: SL BUFFER per instrument (1.5, 2.0, 0.5, 3.0, 2.0)
Settings K4:K8: FIXED R TARGET per instrument (2.2, 3.0, 3.3, 5.0, 2.0)

## Tech Stack Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Language | Python | Fast ecosystem, easy AI integration |
| Web framework | FastAPI | Modern, async, type-safe, good Jinja2 support |
| Database | PostgreSQL | Relational, robust, handles trade history well |
| Frontend | Jinja2 + minimal JS | Simple, server-rendered, fewer moving parts |
| AI | Ollama (local) | Data privacy, no cloud costs, learn from trade data |
| Media | Local `media/screenshots/` | Simple file storage, DB stores paths |
| ORM mode | Synchronous SQLAlchemy | Python 3.14 + Windows has async driver incompatibilities (asyncpg MissingGreenlet, psycopg ProactorEventLoop). Sync avoids entire class of errors; FastAPI runs sync routes in threadpool. |

## Python 3.14 Async Driver Compatibility

Python 3.14.6 on Windows is bleeding-edge and not fully compatible with async PostgreSQL drivers:
- `asyncpg` + SQLAlchemy async → `MissingGreenlet` (greenlet bridge incompatibility)
- `psycopg` async → `ProactorEventLoop` unsupported (requires `SelectorEventLoop`)

Resolution: use **synchronous SQLAlchemy** (`create_engine` + `sessionmaker` + `psycopg` sync mode). This is stable and fully functional for a solo local project. If Python 3.15 or newer drivers resolve this, the architecture can be revisited in an ADR.

## Privacy & Security Rules

- Database credentials and Ollama config live only in `.env` (gitignored)
- `.env.example` contains placeholder values for documentation
- Never commit credentials, secrets, or operational state
- Trade data is personal and sensitive; local processing only

## AI Use Cases (Future)

- Identify highest-expectancy setups/sessions/instruments from historical data
- Detect psychology patterns (tilt after losses, revenge trading, overtrading after drawdown)
- Risk management analysis: stop adherence, R:R discipline, sizing consistency
- Monthly/quarterly performance vs plan
