from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import WatchlistIdea


def test_executed_unlinked_watchlist_idea_remains_visible_as_running():
    marker = f"pytest-unlinked-watchlist-{uuid4().hex}"
    idea_id = None

    with TestClient(app) as client:
        response = client.post(
            "/watchlist/new",
            data={"title": marker, "status": "EXECUTED"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            idea = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one()
            idea_id = idea.id

        running = client.get("/watchlist/?view=running")
        assert running.status_code == 200
        assert marker in running.text
        assert "Running Trades" in running.text

    with SessionLocal() as db:
        idea = db.get(WatchlistIdea, idea_id)
        if idea:
            db.delete(idea)
        db.commit()
