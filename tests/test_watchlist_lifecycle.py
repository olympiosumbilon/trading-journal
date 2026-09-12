from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import Trade, WatchlistIdea


def test_running_trade_stays_running_then_moves_to_history():
    marker = f"pytest-lifecycle-{uuid4().hex}"
    idea_id = None
    trade_id = None

    with TestClient(app) as client:
        response = client.post(
            "/watchlist/new",
            data={"title": marker, "planned_entry": "100", "planned_sl": "98", "planned_tp": "106", "status": "WAITING"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            idea = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one()
            idea_id = idea.id

        client.post(f"/watchlist/{idea_id}/status", data={"status": "MONITORING"}, follow_redirects=False)
        client.post(f"/watchlist/{idea_id}/status", data={"status": "EXECUTED"}, follow_redirects=False)

        client.post(
            "/trades/",
            data={
                "from_watchlist_id": str(idea_id),
                "entry_date": "2026-09-09",
                "entry_time": "10:30",
                "entry_price": "100",
                "stop_loss": "98",
                "take_profit": "106",
                "comments": marker,
                "execution_status": "LIVE",
                "outcome_type": "AUTO",
            },
            follow_redirects=False,
        )

        with SessionLocal() as db:
            trade = db.query(Trade).filter(Trade.comments == marker).one()
            trade_id = trade.id
            # Simulate an open trade with no final result yet.
            trade.fixed_r_target = None
            trade.is_win = False
            trade.is_loss = False
            db.commit()

        running = client.get("/watchlist/?view=running")
        assert running.status_code == 200
        assert marker in running.text
        assert "Running Trades" in running.text

        returned = client.post(f"/watchlist/{idea_id}/return-to-monitoring", follow_redirects=False)
        assert returned.status_code == 303
        with SessionLocal() as db:
            idea = db.get(WatchlistIdea, idea_id)
            assert idea.status == "MONITORING"
            assert idea.promoted_trade_id is None

            idea.promoted_trade_id = trade_id
            idea.status = "EXECUTED"
            trade = db.get(Trade, trade_id)
            trade.outcome_type = "FULL_TP"
            trade.fixed_r_target = 2.5
            db.commit()

        history = client.get("/watchlist/?view=history")
        assert history.status_code == 200
        assert marker in history.text
        assert "Setup History" in history.text

    with SessionLocal() as db:
        trade = db.get(Trade, trade_id)
        if trade:
            db.delete(trade)
        idea = db.get(WatchlistIdea, idea_id)
        if idea:
            db.delete(idea)
        db.commit()
