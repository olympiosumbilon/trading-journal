# Requirements

## Functional Requirements

### Data Import (One-time Migration)
- **FR-001**: Import all existing trades from the Excel workbook (`My Strategy Backtesting Template (2024) - V1.2.xlsx`) into PostgreSQL as a one-time migration. Source sheets: Trades, SUMMARY, Yearly Analysis, Settings.
- **FR-002**: Preserve all raw columns from the Trades sheet (A:AF) including DATE, ENTRY TIME, SESSION, PAIR, SETUP, PROBABILITY, MTF PHASE, ENTRY NEWS, MANAGEMENT NEWS, ENTRY CANDLE SIZE, MAE SL BUFFER, MFE, SCREENSHOT 1-3, COMMENTS.
- **FR-003**: Import Settings table (instruments, sessions, strategies, probabilities, MTF phases, years, per-instrument SL BUFFER and FIXED R TARGET).

### Trade Management
- **FR-004**: CRUD operations for trades (create, read, update, delete) via the web UI.
- **FR-004a**: Trade entry form in the web UI — fields map to the Excel Trades columns but presented as a clean journal form, not a spreadsheet grid.
- **FR-005**: CRUD operations for Settings (update session/instrument/strategy lists and per-instrument SL BUFFER / FIXED R TARGET).

### Calculation Engine
- **FR-006**: Compute `MAX R` per trade using the instrument-specific formula from Excel: `MFE / (ENTRY CANDLE SIZE + SL BUFFER)`. Return `-1` if MAE SL BUFFER >= MFE (stop hit).
- **FR-007**: Compute `FIXED R TARGET` per trade: cap `MAX R` at the instrument-specific FIXED R TARGET; return `-1` for losses.
- **FR-008**: Compute running `TOTAL R` (cumulative sum of MAX R).
- **FR-009**: Compute `WINS` and `LOSSES` counters.
- **FR-010**: Compute `WIN STREAK` and `LOSS STREAK` (consecutive counts).
- **FR-011**: Compute `PEAK R` (running maximum of TOTAL R).
- **FR-012**: Compute `DRAWDOWN` (`PEAK R - TOTAL R`).
- **FR-013**: Compute `MAX DRAWDOWN` (global minimum of DRAWDOWN).
- **FR-014**: Recalculate derived fields automatically on trade create/update/delete or Settings change.

### Dashboard & Analytics
- **FR-015**: Summary cards: win rate, total R, profit factor, expectancy, average R per trade.
- **FR-016**: Filterable trade list and summary by YEAR, MONTH, QUARTER, SESSION, PAIR, SETUP, PROBABILITY. Displayed as a web table with filters, not a spreadsheet grid.
- **FR-017**: Charts: cumulative R curve, drawdown curve, win/loss streak timeline, monthly/yearly performance bars, session/pair performance.
- **FR-018**: Yearly Analysis view (monthly/quarterly breakdowns matching Excel Yearly Analysis).
- **FR-019**: SUMMARY view (aggregated stats by year/instrument/session matching Excel SUMMARY).

### Media & Screenshots
- **FR-020**: Upload and associate up to 3 screenshots per trade.
- **FR-021**: Display screenshots inline in trade detail and review views.
- **FR-022**: Store screenshot files in `media/screenshots/`; persist file paths in the database.

### AI Integration (Future)
- **FR-023**: Endpoint to feed trade statistics to local Ollama for pattern analysis.
- **FR-024**: AI-generated insights: highest-expectancy setups, session performance, psychology flags (tilt detection), risk management alerts.

## Non-Functional Requirements

- **NFR-001**: Database: PostgreSQL. Credentials and connection strings read from environment variables (`.env`); never hardcoded or stored in Markdown.
- **NFR-002**: Frontend: Jinja2 server-rendered templates with minimal JavaScript.
- **NFR-003**: AI: Ollama local REST API only (`localhost:11434`). No cloud AI services for sensitive trade data.
- **NFR-004**: Security: input validation, SQL injection prevention via SQLAlchemy ORM, XSS prevention via Jinja2 auto-escaping.
- **NFR-005**: Data integrity: calculation results must match Excel exactly for the first ~100 manually verified trades before full import.
- **NFR-006**: Version control: Git repository for the project; `.env` and `media/` ignored.
