from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import Trade


def test_trade_list_shows_direction_in_table_and_compact_list():
    marker = f"pytest-direction-list-{uuid4().hex}"
    trade_id = None

    with TestClient(app) as client:
        response = client.post(
            "/trades/",
            data={
                "entry_date": "2026-09-10",
                "entry_time": "10:30",
                "direction": "SHORT",
                "entry_price": "100",
                "stop_loss": "102",
                "take_profit": "96",
                "comments": marker,
                "execution_status": "LIVE",
                "outcome_type": "AUTO",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            trade = db.query(Trade).filter(Trade.comments == marker).one()
            trade_id = trade.id

        table = client.get("/trades/?per_page=100")
        assert table.status_code == 200
        assert "<th>Direction</th>" in table.text
        assert "direction-short" in table.text
        assert ">SHORT<" in table.text

    with SessionLocal() as db:
        trade = db.get(Trade, trade_id)
        if trade:
            db.delete(trade)
        db.commit()
