# Project Handoff

## Current Objective
Completed the **Watchlist Convert Modal & Classification Selectors**, **Watchlist Kanban & Card Toolbar Redesign**, and **3 Action Icon Buttons (View, Edit, Delete)** across Active Pipeline, Setup History, and Cards. The system is fully operational, thoroughly tested, and backwards-compatible with existing global stylesheets.

---

## Current Status & Summary of Recent Implementations

### 0. 📊 Market Analytics Terminal & Heatmap Refusal Fix (Latest)
- **Root Cause Identified**:
  - `coinglass.com`, `forexfactory.com`, and `cryptocraft.com` enforce strict browser security headers (`X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'`) and Cloudflare bot protection, causing browsers to refuse iframe embedding (`www.coinglass.com refused to connect`).
- **Live TradingView Integration**:
  - Replaced broken iframes with embedded, cross-origin supported, official TradingView widgets:
    - **🔥 Live Crypto Heatmap**: Interactive, real-time market cap & 24h change coin map with top bar controls.
    - **📊 Technicals & RSI Screener**: Live crypto market screener featuring technical ratings, RSI, oscillators, and volume.
    - **📅 Macro Economic Calendar**: Live economic calendar with high-impact volatility event tracking.
- **External Pro Launchpads**:
  - Built dedicated, Bloomberg/TradingView-styled Launchpad cards for **Coinglass RSI**, **Coinglass Liquidations**, **ForexFactory**, and **CryptoCraft**:
    - High-visibility 1-click Pro Launch buttons (`target="_blank"`).
    - Clear technical indicators guide (e.g. RSI > 75 overbought, RSI < 25 oversold, liquidity magnet zones, red folder news protocols).
    - Quick-access direct links for specific timeframes and data views.
  - Dynamic `🔗 Open Fullscreen ↗` button syncing to the active tool URL.
- **Cache-Buster & Verification**:
  - Bumped stylesheet query version to `v=20260818i` in `templates/base.html`.
  - Smoke tests and full test suite passing (57/57 tests pass, `GET /` returns 200).

### 1. 🎨 Dashboard Card Spacing & Zero-Padding Fix
- **Trade Outcome & Exit Distribution (`.outcome-matrix-grid`)**:
  - Added proper padding (`padding: 0.85rem 1rem 1rem 1rem;`) to `.outcome-matrix-grid` in `static/style.css`, resolving cards touching outer borders.
- **Psychology & Mindset Edge (`.psych-tab-bar` & `.psychology-breakdown-list`)**:
  - Added dedicated styling for `.psych-tab-bar` (`padding: 0.85rem 1rem 0.5rem 1rem;`) and `.psychology-breakdown-list` (`padding: 0 1rem 1rem 1rem;`) in `static/style.css`.
  - Removed colored left indicator bars (`.psych-good` and `.psych-bad` left borders) so cards maintain clean uniform `1px solid #e2e8f0` borders on all 4 sides.
  - Removed redundant inline style from `templates/dashboard/index.html` to maintain clean separation of concerns.
  - Bumped CSS cache-buster in `templates/base.html` to `v=20260818h`.
  - Verified 57/57 tests pass and endpoint returns HTTP 200.

### 1. 🎯 Watchlist UI Redesign & 3-Icon Actions
- **Typography System (Space Grotesk + Manrope)**:
  - Header font: Integrated **Space Grotesk** (`400`, `500`, `600`, `700`) for all headings (`h1` - `h6`), section titles, and brand banners.
  - Text & Body font: Integrated **Manrope** (`300`, `400`, `500`, `600`, `700`, `800`) for body copy, paragraphs, table rows, form inputs, badges, and toolbars.
  - Loaded via Google Fonts preconnect in `templates/base.html` and `@import` fallback in `static/style.css`.
- **Watchlist Form Layout & Spacing Polish (`form.html` & `static/watchlist.css`)**:
  - Reduced the oversized `max-width: 1560px` container to a well-proportioned `max-width: 980px` centered layout.
  - Wrapped the form in a unified white card panel with a subtle border (`#e2e8f0`) and soft shadow, eliminating double-spaced gaps between sections.
  - Streamlined grid spacing (`gap: 0.85rem`) and normalized input heights (38px) across Instrument, Direction, Stage, Strategy, Session, Probability, Phase, and Geometry levels.
  - Added responsive breakpoints for 2-column (tablet) and 1-column (mobile) rendering without horizontal distortion.
- **Watchlist Form Live Execution Timing (`form.html` & `routers/watchlist.py`)**:
  - Dynamically displays and enforces **Start Date** (`entry_date`) and **Start Time** (`entry_time`) in `/watchlist/new` and `/watchlist/{id}/edit` when Pipeline Stage is switched to `Live / Executed` (`EXECUTED`).
  - Auto-prefills current date and time (PHT) when revealed, requiring Start Time before submission.
  - Automatically creates and links the corresponding live trade in `trades` table upon saving an idea with `status=EXECUTED`.
- **Modal Validation & Classification Fields (`_convert_modal.html`)**:
  - Integrated required Start Date (`entry_date`) and Start Time (`entry_time`) prefilled with Philippine Time (PHT).
  - Added 4 classification dropdowns: Strategy (`strategy_id`), Session (`session_id`), Probability Level (`probability_level_id`), and MTF Phase (`mtf_phase_id`), with backend persistence in `routers/watchlist.py`.
- **Card Border Polish (`static/watchlist.css`)**:
  - Removed all colored accent borders (`border-left: 3px solid #3b82f6` for monitoring, amber for waiting, etc.) from watchlist cards.
  - Replaced with clean, balanced, subtle `1px solid #e2e8f0` borders across all sides with soft `#cbd5e1` hover states, eliminating artificial stripes.
- **Card Toolbar Redesign (`_card.html`)**:
  - High-contrast stage pill badges, clean typography, and full-width CTA buttons.
  - Quick stage change dropdown and minimal icon actions (Archive/Restore, Edit, Delete with prompt).
- **Table Action Icons (View, Edit, Delete)**:
  - Replaced plain text links in both Active Pipeline list table (`view_mode=list`) and Setup History table (`view=history`) with 3 clean SVG icon buttons:
    - **View**: Eye icon (`/watchlist/{id}`)
    - **Edit**: Pencil icon (`/watchlist/{id}/edit`)
    - **Delete**: Trash icon with red danger hover and confirmation dialog (`POST /watchlist/{id}/delete`)
  - Added Delete action button to Watchlist Detail page (`templates/watchlist/detail.html`).
- **Scoped Styling (`static/watchlist.css`)**:
  - All new styles scoped to `.wlx-*` and `.wl-*` classes without altering `static/style.css`.
  - Full test suite passing (57/57 tests passed).

### 1. 📏 Adverse Wick Price & MAE Overshoot Engine
- **Field & DB Migration**:
  - Added `adverse_wick_price` column (type `DOUBLE PRECISION`) to the `trades` table.
  - Added input field `Adverse Wick Price (Extreme High/Low)` under Section 3 (*Candle Size & R-Target Geometry*) in `/trades/new` and `/trades/{id}/edit`.
  - Added `ADVERSE WICK` metric display to the Trade Detail page (`/trades/{id}`).
- **Real-Time Client-Side Calculation (`recalcAdverseWick`)**:
  - **Short**: $\text{Excess} = \max(0.0, \text{Wick} - \text{SL})$.
  - **Long**: $\text{Excess} = \max(0.0, \text{SL} - \text{Wick})$.
  - **Dynamic Visual Badge**:
    - `🪤 +{excess} over SL` (Amber warning pill) when price overshoots SL.
    - `✅ Clean (0.0000)` (Green badge) when wick does not breach SL.
    - `⚠️ Enter Stop Loss in Calculator above` (Red guidance) if Stop Loss field is blank.
  - Synchronized with `calcSL`, `calcDirection`, and `calcEntry` on input/change events.
- **Backend Persistence**:
  - `routers/trades.py`: `create_trade` and `update_trade` parse and persist `adverse_wick_price`.

### 2. ⚡ Watchlist 1-Click Promote & Pre-fill Improvements
- **Price & Direction Binding**:
  - Fixed prefill mismatch when promoting from Watchlist (`planned_entry`, `planned_sl`, `planned_tp`, and uppercase `direction` like `SHORT`).
  - Pre-fills into the Risk Calculator and auto-computes position sizing, margin, candle size, and target R.
- **Notes & Thesis Consolidation**:
  - Automatically merges General Trade Plan with all multi-timeframe layer notes (`• [Layer Title]: Notes`) into `Comments / Execution Notes`.
- **Auto Dates**:
  - Auto-fills `entry_date` with current date and `entry_time` with current Philippine Time (PHT), triggering session auto-detection.

### 3. 📦 Watchlist Clutter-Free Lifecycle & Archive System
- **Smart Scope Filter Toolbar**:
  - Added `Scope:` dropdown filter to `/watchlist/`:
    - `⚡ Active Pipeline`: Shows only active, ongoing setups (`WAITING`, `MONITORING`, `EXECUTED`).
    - `🌐 All Ideas`: Full board visibility.
    - `📦 Archived / History`: Inactive/resolved ideas.
- **1-Click Archive & Restore Actions**:
  - Added `📦 Archive` button to cards: instantly marks setup as `RESOLVED` with timestamp.
  - Added `♻️ Restore` button on resolved cards to return them to active board.
- **Logged Trade Result Pill**:
  - Cards linked to executed trades display `View in Trades #{id} →` with color-coded outcome pill (e.g. `+2.20R WIN` or `-1.00R LOSS`).
- **Independent Scrollboxes & Kanban Pagination**:
  - Kanban columns feature independent scrollable containers (`max-height: calc(100vh - 280px)` with slim custom scrollbars) preventing tall page scrolling.
  - Added `➖ Minimize` / `➕ Expand` toggle button per column with `localStorage` state persistence.
  - `Resolved / Inactive` column displays the latest 5 setups with a toggleable `📦 Show All Archived Setups (X more) ↓` button.

### 4. 🏷️ Multi-Timeframe Layer Titles & Screenshot Sync
- **Captions Across Pipeline**:
  - Transferred timeframe layer titles (`Weekly Timeframe (1W)`, `4-Hour POI`, etc.) from Watchlist to `captions` inputs on Trade Form and saved into `trade_screenshots.caption`.
  - Displayed in Trade Detail view (`#1: Weekly Timeframe (1W)`) and inside the Full-Screen Lightbox header.
- **Interactive Screenshot Previews & Lightbox Zoom**:
  - Live TradingView snapshot resolving (`/x/...` -> S3 snapshot image) with instant preview thumbnail.
  - Universal mobile full-screen lightbox (100vw × 100vh dark overlay with touch-close button).

### 5. 📱 Mobile UI & Layout Polish
- **Trade Screenshots Responsive Layout**:
  - Changed `.shot-input-header` on mobile (`max-width: 640px`) to a clean 3-row stacked grid:
    - Row 1: `#1` Badge + `✕ Delete` button.
    - Row 2: Full-width Timeframe Title / Caption input.
    - Row 3: Full-width TradingView URL input.
  - Made action buttons (`📋 Bulk Paste Links`, `+ Add Another Screenshot`) touch-friendly 2-column grid.

### 6. 📈 Chart & Calculation Fixes
- **Calculation Engine Zero MAE Fix**:
  - In `services/calculation_service.py` (`compute_max_r`), changed condition so `0.0000` MAE is treated as a clean win rather than a stop loss hit. Recalculated Trade #50 to `+6.55 Max R` and `+2.20R Win`.
- **Chart.js Y-Axis Float Precision**:
  - Fixed floating-point precision display artifacts (e.g. `2.3000000000000003R`) on Dashboard & Summary Cumulative Equity Curve by formatting ticks with `Number(v.toFixed(2)) + 'R'`.
  - Added baseline `0.00R` ("Start") point so the equity curve clearly visualizes initial growth.
- **Matrix Table Hover Popovers**:
  - Implemented smart dynamic auto-flip (`popover-pos-up`) when hovered near the bottom of the table or viewport, preventing bottom clipping.

---

## Decisions Made
- **Raw Data First for MAE**: Set baseline Settings SL Buffer to `0.0` while collecting actual overshoot via `Adverse Wick Price`, enabling data-driven optimization.
- **Reversible Archiving**: Watchlist cards are never destroyed upon logging; they transition to `RESOLVED` and remain accessible or restorable.
- **Client-Side Responsive Layouts**: Used CSS Grid template areas for mobile screenshot inputs rather than DOM-altering JavaScript, ensuring smooth resizing across devices.
- **Strict Single-Source of Truth**: Database columns mirror domain entities; SQLAlchemy sync connection remains standard across all routers.

---

## Files Changed Recently
- `models.py`: Added `adverse_wick_price` column to `Trade`.
- `routers/trades.py`: Handled `adverse_wick_price` in create/update; transferred screenshot captions; updated prefill handling.
- `routers/watchlist.py`: Scope filtering, `archive` and `restore` endpoints, merged notes formatting, robust prefill params.
- `routers/dashboard.py`: Prepend `Start` baseline `0.0` to equity curve; decimal tick formatting.
- `routers/summary.py`: Prepend `Start` baseline `0.0` to equity curve; decimal tick formatting.
- `services/calculation_service.py`: Fixed `0.0000` MAE condition in `compute_max_r`.
- `templates/trades/form.html`: Adverse Wick input with live calculation, mobile stacked layout, prefill price bindings.
- `templates/trades/detail.html`: Displayed `ADVERSE WICK` metric and screenshot captions in gallery & lightbox.
- `templates/watchlist/index.html`: Scope filter dropdown, column collapse toggles, archived pagination, scrollbox containers.
- `templates/watchlist/_card.html`: Outcome pill badge (`+2.20R WIN`), 1-click `📦 Archive` / `♻️ Restore` actions.
- `templates/base.html`: Smart upward hover popover listener, stylesheet version cache busting (`?v=20260818e`).
- `static/style.css`: Column scrollboxes, collapse states, load-more buttons, mobile responsive screenshot headers, upward popovers.

---

## Next Steps / Backlog for Next Session
1. **Optimal SL Buffer Simulator & Analytics**:
   - Build a "Wick-Out Recovery Matrix" on `/analysis/` or `/summary/` using accumulated `adverse_wick_price` and `mae_sl_buffer` data to compute the statistical sweet spot for SL Buffer per coin.
2. **Review Untracked Testing Files**:
   - Evaluate newly added test files (`tests/test_calculation_unit.py`, `tests/test_trades_flow.py`, `playwright.config.py`) and integrate with CI / regression runs if desired.
3. **LAN / Multi-Device Access Review**:
   - Check if the user intends to run the Docker / LAN deployment on mobile devices over Wi-Fi.

---

## Validation Status
- ✅ Database migration executed (`adverse_wick_price` added to PostgreSQL).
- ✅ Trade creation and editing with Adverse Wick Price tested and verified.
- ✅ Watchlist promotion pre-fills all prices, directions, notes, and screenshot layers.
- ✅ Equity curve float precision fixed on Dashboard and Summary.
- ✅ Multi-Year Strategy Performance Matrix popovers flip upward when near bottom.
- ✅ Mobile UI for screenshot cards and lightboxes verified responsive and clutter-free.
- ✅ Git branch `main` clean and synchronized with origin remote (`main 33180cf`).
