# Decisions

| ID | Date | Decision | Status | Consequence |
| --- | --- | --- | --- | --- |
| DEC-001 | 2026-08-13 | Python + FastAPI stack | Approved | Enables async, type-safe backend with easy Jinja2 frontend |
| DEC-002 | 2026-08-13 | PostgreSQL database | Approved | Relational persistence for trades, settings, and calculations |
| DEC-003 | 2026-08-13 | Ollama local AI integration | Approved | Trade data and AI analysis remain private; no cloud costs |
| DEC-004 | 2026-08-13 | Import existing ~1193 trades from Excel | Approved | Preserves historical data; validates calculation accuracy against Excel |
| DEC-005 | 2026-08-13 | Screenshot storage in local `media/screenshots/` | Approved | Simple file storage; DB stores paths for linking to trades |
| DEC-006 | 2026-08-13 | Jinja2 server-rendered frontend | Approved | Fewer moving parts; suitable for solo project |
| DEC-007 | 2026-08-13 | Web UI is not Excel-like | Approved | The system is a standalone trading journal; the Excel is only a reference for data model and formulas |
| DEC-008 | 2026-08-13 | Switch to synchronous SQLAlchemy | Approved | Python 3.14 + Windows has async driver compatibility issues (asyncpg MissingGreenlet, psycopg ProactorEventLoop). Sync avoids entire class of errors. FastAPI runs sync routes in threadpool. |

Do not mark proposed decisions accepted without owner approval.
