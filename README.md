# 📈 Professional Trading Journal & Analytics System

A high-performance, full-stack trading journal and backtesting analytics web application built with **FastAPI**, **PostgreSQL**, **Jinja2**, and **Chart.js**. Designed from the ground up to replace spreadsheets with real-time R-multiple analytics, multi-dimensional execution matrices, psychological discipline metrics, and TradingView screenshot resolution.

---

## 🌟 Key Features

### 📊 Comprehensive Performance Analytics
- **Yearly & All-Time Performance Dashboard**: Real-time Strike Rate (Win Rate), Net Return (R), Profit Factor, Expectancy, and Average Win/Loss.
- **Dynamic Equity Curve**: Cumulative R performance line charts with gradient fills and monthly bar comparisons.
- **Multi-Year Strategy Matrix**: Cross-tabulated performance tracking across strategies (`LC-1`, `LC-2A`, `LC-IC1`, `OB`, etc.) and time horizons.
- **Quarterly & Monthly Performance Matrices**: Breakdown of returns and strike rates by month, quarter, and trade setup.

### 🎯 Interactive Trade Preview & Drill-Down Filtering
- **Hover Preview Popovers**: Hover over any trade count across breakdown cards (Months, Setups, Sessions, Probabilities, MTF Phases, Days of Week, and Outcomes) to immediately preview trade details (`#ID`, `Pair`, `Setup`, `Return R`).
- **1-Click Drill-Down**: Click "View All &rarr;" on any category to filter the Trade List directly to matching trades.
- **Active Filter Badges**: Visual indicator with 1-click reset button (`[Show All Trades]`).

### 🚦 Execution Tagging & Opportunity Cost Tracking
- **Multi-State Execution Tagging**:
  - 🟢 **Live Trades**: Real trades executed according to plan.
  - 🟡 **Front-Run**: Orders filled before reaching the exact limit entry price.
  - ⚪ **Missed**: Valid setups that triggered without trader entry (+Missed R tracking).
  - 🪤 **SL Swept**: Trades stopped out before running to target (-Lost R leakage tracking).
- **Execution Discipline Meter**: Quantifies overall execution consistency and theoretical maximum return.

### 🧘 Trader Psychology & Mindset Edge
- **Pre-Trade State**: Analyze win rates and returns when entering under `Calm & Disciplined`, `FOMO`, `Fearful/Hesitant`, `Revenge Trading`, `Boredom`, or `High Confidence`.
- **Post-Trade Reflection**: Review exit execution feelings (`Followed Plan`, `Greed / Held Too Long`, `Panicked / Cut Early`, `Frustrated`, `Neutral`).

### 📸 Multi-Screenshot & TradingView Integration
- **TradingView Snapshot Resolver**: Automatically parses and resolves `tradingview.com/x/...` share links into high-resolution chart images.
- **Multi-Image Attachments**: Dynamic screenshot gallery manager with bulk link import.

### 📐 Live Position Size & R-Calculator
- Built-in position calculator with instant risk sizing, Fixed Target R, Max Potential R, MAE (Maximum Adverse Excursion), and MFE (Maximum Favorable Excursion) metrics.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+) |
| **Server Engine** | [Uvicorn](https://www.uvicorn.org/) (ASGI Server) |
| **Database & ORM** | [PostgreSQL](https://www.postgresql.org/) + [SQLAlchemy](https://www.sqlalchemy.org/) |
| **Frontend UI** | Server-Rendered [Jinja2](https://jinja.palletsprojects.com/) Templates |
| **Styling** | Custom Vanilla CSS (Dark/Light Photon Theme) |
| **Charting Engine** | [Chart.js](https://www.chartjs.org/) |
| **Spreadsheet Engine** | [OpenPyXL](https://openpyxl.readthedocs.io/) |

---

## 🚀 Installation & Setup

### 1. Prerequisites
- **Python 3.10** or higher installed on your system.
- **PostgreSQL** database server running locally or accessible via network.
- **Git** installed.

### 2. Clone the Repository
```bash
git clone https://github.com/olympiosumbilon/trading-journal.git
cd trading-journal
```

### 3. Create a Virtual Environment
```bash
# Windows (PowerShell / CMD)
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and configure your PostgreSQL database connection:
```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env`:
```ini
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/trading_journal
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

*(Make sure the database `trading_journal` exists in your PostgreSQL instance, e.g. `CREATE DATABASE trading_journal;`)*

### 6. Run the Application

#### Option A: Run on your PC only (Localhost)
```bash
uvicorn main:app --reload --port 8000
```
Open your browser and navigate to: **[http://localhost:8000](http://localhost:8000)**

#### Option B: Access from Tablet / iPad / Mobile on the same Wi-Fi
To access the journal and watch course videos from your **Tablet, iPad, or Smartphone** connected to the same Wi-Fi network:

1. Start the server bound to `0.0.0.0`:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Find your computer's local IPv4 address (run `ipconfig` on Windows, e.g. `192.168.1.11`).
3. Open the browser (Safari, Chrome, etc.) on your tablet/phone and navigate to:
   ```
   http://YOUR_LOCAL_IP:8000
   ```
   *(Example: `http://192.168.1.11:8000`)*

> [!TIP]
> If your tablet cannot connect, ensure that your Wi-Fi network in Windows is set to **Private**, or allow Python through the Windows Defender Firewall prompt.

---

## 📖 How to Use

### 1. Logging a Trade (`/trades/new`)
1. Click **+ New Trade** on the navigation bar.
2. Select the **Instrument**, **Date/Time**, **Session** (Asia, LDN, NY), and **Setup**.
3. Input your Entry, Stop Loss, and Exit targets. The live calculator computes your Risk (R) and potential return.
4. Select your **Pre-Trade Mindset** (e.g. *Calm & Disciplined*) and **Execution Tag** (e.g. *Live Trades*).
5. Paste your TradingView screenshot link (e.g. `https://www.tradingview.com/x/GAxHDxmH/`) or upload images.
6. Click **Save Trade**.

### 2. Yearly Analysis (`/analysis/`)
- Switch the active year via the top-right dropdown selector.
- Inspect KPI statistics, Equity Curves, and Session/Strategy performance.
- Hover over any trade count cell to view interactive popovers containing individual trade details.

### 3. All-Time Summary (`/summary/`)
- View multi-year historical progression, composite equity curves, and breakdown metrics across all logged years.

### 4. Trade List & Filtering (`/trades/`)
- Filter trades by Year, Month, Session, Instrument, Setup, Probability, MTF Phase, Tag, or Outcome.
- Sort by Date, Max R, Fixed R, or Total R.

### 5. 🎓 Photon Academy & Course Player (`/course/`)
- **13 Complete Modules (158 Video Lessons)**: Instant range-streamed video playback covering Market Structure, Liquidity, Orderflow, LC-1, LC-2A, and Trading Psychology.
- **Dedicated Document Reader**: View lesson `.docx`, `.pdf`, and study guides directly in your browser without downloading files to your disk.
- **Speed & Progress Tracking**: Playback speed controls (0.75x–2x), autoplay next lesson, completion checkmarks, and integrated local study notepad.

---

## 📂 Project Structure

```
Trading Journal/
├── config.py                 # Application settings and env loader
├── database.py               # SQLAlchemy engine & session factory
├── main.py                   # FastAPI app entry point & router mounting
├── models.py                 # SQLAlchemy database models (Trade, Lookups, Screenshots)
├── requirements.txt          # Python dependencies
├── routers/
│   ├── analysis.py           # Yearly analytics and photon breakdown router
│   ├── automations.py        # Automated sync & maintenance jobs
│   ├── course.py             # Photon Course Academy & video streaming router
│   ├── dashboard.py          # Dashboard homepage router
│   ├── review.py             # AI trade review router
│   ├── settings.py           # Lookup configuration router (Pairs, Setups, etc.)
│   ├── summary.py            # All-time multi-year summary router
│   └── trades.py             # CRUD trade logging, pagination & filtering
├── services/
│   ├── calculation_service.py # Core R-multiple math, KPIs, and preview serializers
│   ├── course_service.py     # Recursive course tree scanner & doc parser
│   └── import_service.py     # Excel backtesting spreadsheet migration engine
├── static/
│   ├── style.css             # Complete design system tokens & component styles
│   └── js/                   # Frontend helpers & calculator scripts
├── templates/
│   ├── analysis/             # Yearly analysis views
│   ├── course/               # Academy hub, video watch player & doc reader views
│   ├── dashboard/            # Overview dashboard views
│   ├── layout.html           # Master navigation & responsive shell
│   ├── summary/              # Multi-year summary views
│   └── trades/               # Trade logging, list, detail & edit views
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
