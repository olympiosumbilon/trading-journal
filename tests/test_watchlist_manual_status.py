from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import WatchlistIdea


def test_watchlist_manual_status_moves_card_between_kanban_stages():
    marker = f"pytest-manual-status-{uuid4().hex}"
    idea_id = None

    with TestClient(app) as client:
        response = client.post(
            "/watchlist/new",
            data={"title": marker, "status": "WAITING"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            idea_id = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one().id

        for status, expected_tab in (("MONITORING", "Monitoring Trigger"), ("EXECUTED", "Running Trades")):
            response = client.post(
                f"/watchlist/{idea_id}/status",
                data={"status": status},
                follow_redirects=False,
            )
            assert response.status_code == 303
            page = client.get("/watchlist/?view=active")
            assert page.status_code == 200
            assert marker in page.text
            assert expected_tab in page.text
            assert 'value="EXECUTED"' in page.text

        response = client.post(
            f"/watchlist/{idea_id}/status",
            data={"status": "RESOLVED"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        history = client.get("/watchlist/?view=history")
        assert marker in history.text

    with SessionLocal() as db:
        idea = db.get(WatchlistIdea, idea_id)
        if idea:
            db.delete(idea)
        db.commit()
