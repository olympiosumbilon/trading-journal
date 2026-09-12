from datetime import date

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import Trade


def test_trade_prices_survive_create_and_edit():
    marker = "pytest-trade-price-persistence"

    with TestClient(app) as client:
        create_response = client.post(
            "/trades/",
            data={
                "entry_date": "2026-09-09",
                "entry_time": "10:30",
                "entry_price": "100.5",
                "stop_loss": "98.25",
                "take_profit": "106.75",
                "direction": "SHORT",
                "comments": marker,
                "execution_status": "LIVE",
                "outcome_type": "AUTO",
            },
            follow_redirects=False,
        )
        assert create_response.status_code == 303

        with SessionLocal() as db:
            trade = db.query(Trade).filter(Trade.comments == marker).one()
            trade_id = trade.id
            assert (trade.direction, trade.entry_price, trade.stop_loss, trade.take_profit) == (
                "SHORT",
                100.5,
                98.25,
                106.75,
            )

        edit_response = client.get(f"/trades/{trade_id}/edit")
        assert edit_response.status_code == 200
        assert 'name="entry_price"' in edit_response.text
        assert 'value="100.5"' in edit_response.text
        assert 'value="98.25"' in edit_response.text
        assert 'value="106.75"' in edit_response.text

        update_response = client.post(
            f"/trades/{trade_id}/edit",
            data={
                "entry_date": "2026-09-09",
                "entry_time": "10:30",
                "entry_price": "101.0",
                "stop_loss": "97.5",
                "take_profit": "109.0",
                "direction": "LONG",
                "comments": marker,
                "execution_status": "LIVE",
                "outcome_type": "AUTO",
            },
            follow_redirects=False,
        )
        assert update_response.status_code == 303

        with SessionLocal() as db:
            trade = db.get(Trade, trade_id)
            assert (trade.direction, trade.entry_price, trade.stop_loss, trade.take_profit) == (
                "LONG",
                101.0,
                97.5,
                109.0,
            )
            db.delete(trade)
            db.commit()


def test_calculator_price_inputs_are_inside_submittable_trade_form():
    with TestClient(app) as client:
        response = client.get("/trades/new")

    assert response.status_code == 200
    html = response.text
    form_start = html.index('<form method="post" action="/trades/"')
    form_end = html.index("</form>", form_start)
    assert 'id="setupEntry"' in html
    assert 'id="setupStopLoss"' in html
    assert 'id="setupTakeProfit"' in html
    assert 'name="direction"' in html
    assert 'id="riskCalculatorCard" style="display:none !important;"' in html
    assert html.count('name="entry_price"') == 1
    assert html.count('name="stop_loss"') == 1
    assert html.count('name="take_profit"') == 1
