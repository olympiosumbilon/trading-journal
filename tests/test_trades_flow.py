import pytest
from uuid import uuid4

from fastapi.testclient import TestClient
from database import SessionLocal
from main import app
from models import Trade, WatchlistIdea


class TestWatchlistPromote:
    def test_promote_sets_promoted_trade_id_and_status(self):
        marker = f"pytest-promote-{uuid4().hex[:8]}"
        idea_id = None

        with TestClient(app) as client:
            resp = client.post(
                "/watchlist/new",
                data={
                    "title": marker,
                    "planned_entry": "100.00",
                    "planned_sl": "98.00",
                    "planned_tp": "106.00",
                    "status": "WAITING",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 303

            with SessionLocal() as db:
                idea = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one()
                idea_id = idea.id

            from urllib.parse import parse_qs, urlparse

            promote_resp = client.get(f"/watchlist/{idea_id}/promote", follow_redirects=False)
            assert promote_resp.status_code == 303
            assert "trades/new" in promote_resp.headers["location"]

            parsed = parse_qs(urlparse(promote_resp.headers["location"]).query)
            assert "entry_price" in parsed

        with SessionLocal() as db:
            idea = db.get(WatchlistIdea, idea_id)
            if idea:
                db.delete(idea)
            db.commit()

    def test_promote_preserves_price_levels(self):
        marker = f"pytest-price-{uuid4().hex[:8]}"
        idea_id = None

        with TestClient(app) as client:
            client.post(
                "/watchlist/new",
                data={
                    "title": marker,
                    "planned_entry": "123.45",
                    "planned_sl": "120.00",
                    "planned_tp": "130.00",
                },
                follow_redirects=False,
            )

            with SessionLocal() as db:
                idea = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one()
                idea_id = idea.id

            from urllib.parse import parse_qs, urlparse

            promote_resp = client.get(f"/watchlist/{idea_id}/promote", follow_redirects=False)
            query = parse_qs(urlparse(promote_resp.headers["location"]).query)

            assert query["entry_price"] == ["123.45"]
            assert query["stop_loss"][0] == "120.0"
            assert query["tp_target"][0] == "130.0"

        with SessionLocal() as db:
            idea = db.get(WatchlistIdea, idea_id)
            if idea:
                db.delete(idea)
            db.commit()


class TestCreateTrade:
    def test_create_trade_with_valid_data(self):
        marker = f"pytest-create-{uuid4().hex[:8]}"
        trade_id = None

        with TestClient(app) as client:
            resp = client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-15",
                    "entry_time": "10:30",
                    "entry_price": "100.00",
                    "stop_loss": "98.00",
                    "take_profit": "106.00",
                    "direction": "LONG",
                    "execution_status": "LIVE",
                    "outcome_type": "AUTO",
                    "comments": marker,
                },
                follow_redirects=False,
            )
            assert resp.status_code == 303

            with SessionLocal() as db:
                trade = db.query(Trade).filter(Trade.comments == marker).one()
                trade_id = trade.id
                assert trade.entry_price == 100.0

        with SessionLocal() as db:
            trade = db.get(Trade, trade_id)
            if trade:
                db.delete(trade)
            db.commit()

    def test_create_trade_with_negative_prices(self):
        marker = f"pytest-neg-{uuid4().hex[:8]}"

        with TestClient(app) as client:
            resp = client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-15",
                    "entry_price": "-100.00",
                    "stop_loss": "-98.00",
                    "take_profit": "-106.00",
                    "direction": "LONG",
                    "comments": marker,
                },
                follow_redirects=False,
            )
            assert resp.status_code == 303

            with SessionLocal() as db:
                trade = db.query(Trade).filter(Trade.comments == marker).one()
                assert trade.entry_price == -100.0

        with SessionLocal() as db:
            trade = db.get(Trade, trade.id)
            if trade:
                db.delete(trade)
            db.commit()

    def test_create_trade_with_invalid_numeric_returns_none(self):
        marker = f"pytest-inv-{uuid4().hex[:8]}"

        with TestClient(app) as client:
            resp = client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-15",
                    "entry_price": "not-a-number",
                    "stop_loss": "98.00",
                    "take_profit": "106.00",
                    "direction": "LONG",
                    "comments": marker,
                },
                follow_redirects=False,
            )
            assert resp.status_code == 303

            with SessionLocal() as db:
                trade = db.query(Trade).filter(Trade.comments == marker).one()
                assert trade.entry_price is None

        with SessionLocal() as db:
            trade = db.get(Trade, trade.id)
            if trade:
                db.delete(trade)
            db.commit()


class TestEditTrade:
    def test_edit_trade_updates_values(self):
        marker = f"pytest-edit-{uuid4().hex[:8]}"

        with TestClient(app) as client:
            create_resp = client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-10",
                    "entry_price": "100.00",
                    "stop_loss": "98.00",
                    "take_profit": "106.00",
                    "direction": "LONG",
                    "execution_status": "LIVE",
                    "outcome_type": "AUTO",
                    "comments": marker,
                },
                follow_redirects=False,
            )

            with SessionLocal() as db:
                trade = db.query(Trade).filter(Trade.comments == marker).one()
                trade_id = trade.id

            edit_resp = client.get(f"/trades/{trade_id}/edit")
            assert edit_resp.status_code == 200
            assert 'name="entry_price"' in edit_resp.text
            assert 'name="stop_loss"' in edit_resp.text
            assert 'name="take_profit"' in edit_resp.text

            update_resp = client.post(
                f"/trades/{trade_id}/edit",
                data={
                    "entry_price": "101.00",
                    "stop_loss": "99.00",
                    "take_profit": "108.00",
                    "direction": "SHORT",
                    "execution_status": "LIVE",
                    "outcome_type": "AUTO",
                    "comments": marker,
                },
                follow_redirects=False,
            )
            assert update_resp.status_code == 303

            with SessionLocal() as db:
                trade = db.get(Trade, trade_id)
                assert trade.entry_price == 101.0
                assert trade.stop_loss == 99.0
                assert trade.take_profit == 108.0

        with SessionLocal() as db:
            trade = db.get(Trade, trade_id)
            if trade:
                db.delete(trade)
            db.commit()

    def test_edit_nonexistent_trade_returns_404(self):
        with TestClient(app) as client:
            resp = client.post(
                "/trades/9999999/edit",
                data={
                    "entry_price": "100",
                    "stop_loss": "98",
                    "take_profit": "106",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 404


class TestDeleteTrade:
    def test_delete_trade_removes_from_db(self):
        marker = f"pytest-del-{uuid4().hex[:8]}"

        with TestClient(app) as client:
            client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-15",
                    "entry_price": "100.00",
                    "comments": marker,
                },
                follow_redirects=False,
            )

            with SessionLocal() as db:
                trade = db.query(Trade).filter(Trade.comments == marker).one()
                trade_id = trade.id

            delete_resp = client.post(
                f"/trades/{trade_id}/delete",
                follow_redirects=False,
            )
            assert delete_resp.status_code == 303

            with SessionLocal() as db:
                assert db.get(Trade, trade_id) is None

    def test_delete_nonexistent_trade_returns_404(self):
        with TestClient(app) as client:
            resp = client.post(
                "/trades/9999999/delete",
                follow_redirects=False,
            )
            assert resp.status_code == 404


class TestDoubleSubmission:
    def test_double_submit_creates_duplicate_trades(self):
        marker = f"pytest-double-{uuid4().hex[:8]}"

        with TestClient(app) as client:
            resp1 = client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-15",
                    "entry_price": "100.00",
                    "comments": marker,
                },
                follow_redirects=False,
            )
            assert resp1.status_code == 303

            resp2 = client.post(
                "/trades/",
                data={
                    "entry_date": "2026-09-15",
                    "entry_price": "100.00",
                    "comments": marker + "_2",
                },
                follow_redirects=False,
            )
            assert resp2.status_code == 303

            with SessionLocal() as db:
                trades = db.query(Trade).filter(Trade.comments.in_([marker, marker + "_2"])).all()
                assert len(trades) == 2

        with SessionLocal() as db:
            for t in trades:
                db.delete(t)
            db.commit()


class TestTradeFormFields:
    def test_trade_form_renders_all_expected_fields(self):
        with TestClient(app) as client:
            resp = client.get("/trades/new")
            assert resp.status_code == 200
            html = resp.text

            assert 'name="entry_date"' in html
            assert 'name="entry_time"' in html
            assert 'name="entry_price"' in html
            assert 'name="stop_loss"' in html
            assert 'name="take_profit"' in html
            assert 'name="direction"' in html
            assert 'name="session_id"' in html
            assert 'name="instrument_id"' in html
            assert 'name="strategy_id"' in html
            assert 'name="probability_level_id"' in html
            assert 'name="mtf_phase_id"' in html
            assert 'name="execution_status"' in html
            assert 'id="riskCalculatorCard" style="display:none !important;"' in html

    def test_trade_form_prefills_from_watchlist(self):
        marker = f"pytest-prefill-{uuid4().hex[:8]}"

        with TestClient(app) as client:
            client.post(
                "/watchlist/new",
                data={
                    "title": marker,
                    "planned_entry": "150.00",
                    "planned_sl": "148.00",
                    "planned_tp": "158.00",
                    "direction": "SHORT",
                },
                follow_redirects=False,
            )

            with SessionLocal() as db:
                idea = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one()
                idea_id = idea.id

            resp = client.get(f"/watchlist/{idea_id}/promote", follow_redirects=False)
            assert "trades/new" in resp.headers["location"]

            trade_new = client.get(resp.headers["location"].replace("http://localhost:8000", ""))
            assert trade_new.status_code == 200

        with SessionLocal() as db:
            idea = db.get(WatchlistIdea, idea_id)
            if idea:
                db.delete(idea)
            db.commit()