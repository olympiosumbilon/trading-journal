# Source Reference

## Excel Workbook
`My Strategy Backtesting Template (2024) - V1.2.xlsx`

## Sheets

### 1. Trades
Per-trade log with ~1193 rows. Columns A:AF.

| Column | Header | Type | Notes |
| --- | --- | --- | --- |
| A | DATE (DD/MM/YY) | date | Excel serial date |
| B | ENTRY TIME | time | Fraction of day |
| C | SESSION | string | Lookup: Settings B4:B9 |
| D | PAIR | string | Lookup: Settings C4:C8 (instrument) |
| E | SETUP | string | Lookup: Settings D4:D11 (strategy) |
| F | PROBABILITY | string | Lookup: Settings E4:E8 |
| G | MTF PHASE | string | Lookup: Settings F4:F8 |
| H | ENTRY NEWS | string | Optional text |
| I | MANAGEMENT NEWS | string | Optional text |
| J | ENTRY CANDLE SIZE | float | Pips or price units |
| K | MAE SL BUFFER | float | Max adverse excursion buffer |
| L | MFE | float | Max favorable excursion |
| M | MAX R | computed | `MFE / (J + instrument.SL_BUFFER)`; `-1` if stop hit |
| N | FIXED R TARGET | computed | Cap M at instrument.FIXED_R_TARGET; `-1` for losses |
| O | SCREENSHOT 1 | string | Path or URL |
| P | SCREENSHOT 2 | string | Path or URL |
| Q | SCREENSHOT 3 | string | Path or URL |
| R | COMMENTS | string | Free text |
| S | DAY | int/derived | Day number (exact semantics to verify during import) |
| T | DAY | int/derived | Possibly day-of-week or duplicate (verify during import) |
| U | MONTH NUMBER | int | Derived from date |
| V | MONTH NAME | string | Derived from date |
| W | YEAR | int | Derived from date |
| X | QUARTER | int | Derived from date |
| Y | TOTAL R | computed | Running sum of column M |
| Z | WINS | computed | Counter when M > 0 |
| AA | WIN STREAK | computed | Consecutive wins count |
| AB | LOSSES | computed | Counter when M < 0 |
| AC | LOSS STREAK | computed | Consecutive losses count |
| AD | PEAK R | computed | Running max of TOTAL R |
| AE | DRAWDOWN | computed | PEAK R - TOTAL R |
| AF | MAX DRAWDOWN | computed | Global min of DRAWDOWN |

### 2. SUMMARY
Aggregated stats using COUNTIFS/SUMIFS/AVERAGEIFS by:
- Year (Settings G4:G6)
- Instrument (Settings C4:C8)
- Session (Settings B4:B9)

### 3. Yearly Analysis
Monthly and quarterly breakdowns per year using:
- IF, COUNTIFS, SUMIFS, SUM, AVERAGEIFS, MAXIFS

### 4. Settings
Parameter lookup and per-instrument risk settings.

| Row | B (Session) | C (Instrument) | D (Strategy) | E (Probability) | F (MTF Phase) | G (Year) | I (Instrument ref) | J (SL BUFFER) | K (FIXED R TARGET) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | LDN | BTCUSD | LC-1 | HIGH | A | 2022 | BTCUSD | 1.5 | 2.2 |
| 5 | LDN LULL | ETHUSD | LC-2A | MED | A2 | 2023 | ETHUSD | 2.0 | 3.0 |
| 6 | NY | SOLUSD | LC-IC1 | LOW | B | 2024 | SOLUSD | 0.5 | 3.3 |
| 7 | NY LULL | Instrument 4 | OB | — | C | — | — | 3.0 | 5.0 |
| 8 | ASIA | Instrument 5 | STRATEGY 5 | — | D | — | — | 2.0 | 2.0 |
| 9 | ASIA LULL | — | — | — | — | — | — | — | — |

## Formulas

### MAX R (Column M)
```
IF(L="","",
   IFS(D=Settings!$C$4, IF(K>=Settings!$J$4, -1, L/(J+Settings!$J$4)),
       D=Settings!$C$5, IF(K>=Settings!$J$5, -1, L/(J+Settings!$J$5)),
       D=Settings!$C$6, IF(K>=Settings!$J$6, -1, L/(J+Settings!$J$6)),
       D=Settings!$C$7, IF(K>=Settings!$J$7, -1, L/(J+Settings!$J$7)),
       D=Settings!$C$8, IF(K>=Settings!$J$8, -1, L/(J+Settings!$J$8))))
```

### FIXED R TARGET (Column N)
```
IF(M="","",
   IFS(D=Settings!$C$4, IF(M>=Settings!$K$4, Settings!$K$4, -1),
       D=Settings!$C$5, IF(M>=Settings!$K$5, Settings!$K$5, -1),
       D=Settings!$C$6, IF(M>=Settings!$K$6, Settings!$K$6, -1),
       D=Settings!$C$7, IF(M>=Settings!$K$7, Settings!$K$7, -1),
       D=Settings!$C$8, IF(M>=Settings!$K$8, Settings!$K$8, -1)))
```

### Streaks and Running Stats
- TOTAL R: cumulative SUM of MAX R
- WINS: COUNTIF(MAX R > 0)
- LOSSES: COUNTIF(MAX R < 0)
- WIN STREAK: consecutive positive MAX R count
- LOSS STREAK: consecutive negative MAX R count
- PEAK R: running MAX of TOTAL R
- DRAWDOWN: PEAK R - TOTAL R
- MAX DRAWDOWN: MIN of DRAWDOWN column

## Notes
- Columns S and T are both labeled DAY in shared strings; one may be day-of-week, the other day-of-month. Verify during import.
- The Excel uses shared formulas (`t="shared"`) for many cells; the canonical formula is the one shown above.
