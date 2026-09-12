from uuid import uuid4
from datetime import date

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import Trade, WatchlistIdea


def test_auto_loss_without_explicit_outcome_stays_running():
    marker = f"pytest-auto-loss-{uuid4().hex}"
    idea_id = None
    trade_id = None

    with SessionLocal() as db:
        idea = WatchlistIdea(title=marker, status="EXECUTED")
        db.add(idea)
        db.flush()
        trade = Trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            outcome_type="AUTO",
            fixed_r_target=-1.0,
            is_loss=True,
            is_win=False,
            exit_date=date(2026, 9, 9),
            comments=marker,
        )
        db.add(trade)
        db.flush()
        idea.promoted_trade_id = trade.id
        db.commit()
        idea_id = idea.id
        trade_id = trade.id

    try:
        with TestClient(app) as client:
            running = client.get("/watchlist/?view=running")
            assert running.status_code == 200
            assert marker in running.text

            history = client.get("/watchlist/?view=history")
            assert history.status_code == 200
            assert marker not in history.text
    finally:
        with SessionLocal() as db:
            trade = db.get(Trade, trade_id)
            if trade:
                db.delete(trade)
            idea = db.get(WatchlistIdea, idea_id)
            if idea:
                db.delete(idea)
            db.commit()
