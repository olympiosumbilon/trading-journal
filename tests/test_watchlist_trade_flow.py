from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import Trade, WatchlistIdea


def test_watchlist_pipeline_promotes_and_persists_price_levels():
    marker = f"pytest-watchlist-pipeline-{uuid4().hex}"
    trade_id = None
    idea_id = None

    with TestClient(app) as client:
        create_response = client.post(
            "/watchlist/new",
            data={
                "title": marker,
                "planned_entry": "0.02762",
                "planned_sl": "0.02685",
                "planned_tp": "0.03418",
                "status": "WAITING",
            },
            follow_redirects=False,
        )
        assert create_response.status_code == 303

        with SessionLocal() as db:
            idea = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one()
            idea_id = idea.id
            assert idea.status == "WAITING"

        for next_status in ("MONITORING", "EXECUTED"):
            response = client.post(
                f"/watchlist/{idea_id}/status",
                data={"status": next_status},
                follow_redirects=False,
            )
            assert response.status_code == 303

        promote_response = client.get(f"/watchlist/{idea_id}/promote", follow_redirects=False)
        assert promote_response.status_code == 303
        promote_query = parse_qs(urlparse(promote_response.headers["location"]).query)
        assert promote_query["entry_price"] == ["0.02762"]
        assert promote_query["stop_loss"] == ["0.02685"]
        assert promote_query["tp_target"] == ["0.03418"]

        trade_response = client.post(
            "/trades/",
            data={
                "from_watchlist_id": str(idea_id),
                "entry_date": "2026-09-09",
                "entry_time": "10:30",
                "entry_price": promote_query["entry_price"][0],
                "stop_loss": promote_query["stop_loss"][0],
                "take_profit": promote_query["tp_target"][0],
                "comments": marker,
                "execution_status": "LIVE",
                "outcome_type": "AUTO",
            },
            follow_redirects=False,
        )
        assert trade_response.status_code == 303
        with SessionLocal() as db:
            trade = db.query(Trade).filter(Trade.comments == marker).one()
            trade_id = trade.id
            assert (trade.entry_price, trade.stop_loss, trade.take_profit) == (
                0.02762,
                0.02685,
                0.03418,
            )

            idea = db.get(WatchlistIdea, idea_id)
            assert idea.status == "EXECUTED"
            assert idea.promoted_trade_id == trade.id

        edit_response = client.get(f"/trades/{trade_id}/edit")
        assert edit_response.status_code == 200
        assert 'value="0.02762"' in edit_response.text
        assert 'value="0.02685"' in edit_response.text
        assert 'value="0.03418"' in edit_response.text

    with SessionLocal() as db:
        trade = db.get(Trade, trade_id)
        if trade:
            db.delete(trade)
        idea = db.get(WatchlistIdea, idea_id)
        if idea:
            db.delete(idea)
        db.commit()
