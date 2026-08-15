from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import Base, engine
from routers import trades, dashboard, ai, automations, settings, summary, analysis
from apscheduler.schedulers.background import BackgroundScheduler
from services.automation_service import check_alerts

app = FastAPI(title="Trading Journal System")

templates = Jinja2Templates(directory="templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


scheduler = BackgroundScheduler()


def _alert_check_job():
    alerts = check_alerts()
    if alerts:
        print(f"[AUTOMATION] {len(alerts)} alert(s) detected:")
        for a in alerts:
            print(f"  - {a}")
    else:
        print("[AUTOMATION] No alerts.")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(_alert_check_job, "interval", minutes=30, id="alert_check")
    scheduler.start()
    print("[AUTOMATION] Background scheduler started. Alert checks every 30 minutes.")


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()
    print("[AUTOMATION] Background scheduler stopped.")


from services.news_service import get_crypto_news, get_economic_calendar
from database import SessionLocal
from models import Trade

@app.get("/")
def root(request: Request, year: str = ""):
    cookie_year = request.cookies.get("active_year", "")
    active_year = year.strip() if year else (cookie_year.strip() if cookie_year else "2026")
    news = get_crypto_news()
    calendar_events = get_economic_calendar()

    db = SessionLocal()
    query = db.query(Trade)
    if active_year != "all":
        try:
            query = query.filter(Trade.year == int(active_year))
        except ValueError:
            pass

    trades_list = query.all()
    total_trades = len(trades_list)
    wins = sum(1 for t in trades_list if t.is_win)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    total_r = sum(t.fixed_r_target or 0.0 for t in trades_list)
    db.close()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "news": news,
            "calendar_events": calendar_events,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "total_r": round(total_r, 2),
            "active_year": active_year
        }
    )


@app.get("/api/crypto-news")
def api_crypto_news(refresh: bool = False):
    return {"status": "ok", "news": get_crypto_news(force_refresh=refresh)}


app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(automations.router, prefix="/automations", tags=["automations"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(summary.router, prefix="/summary", tags=["summary"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
