from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import WatchlistIdea


def test_history_kanban_and_grid_render_different_layouts():
    marker = f"pytest-history-view-{uuid4().hex}"
    idea_id = None

    with TestClient(app) as client:
        response = client.post(
            "/watchlist/new",
            data={"title": marker, "status": "RESOLVED"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            idea_id = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one().id

        list_view = client.get("/watchlist/?view=history&view_mode=list")
        assert list_view.status_code == 200
        assert 'class="wl-history-table"' in list_view.text
        assert marker in list_view.text

        grid = client.get("/watchlist/?view=history&view_mode=grid")
        assert grid.status_code == 200
        assert "Setup History" in grid.text
        assert 'class="wl-cards-grid"' in grid.text
        assert 'class="wl-history-table"' not in grid.text
        assert marker in grid.text

    with SessionLocal() as db:
        idea = db.get(WatchlistIdea, idea_id)
        if idea:
            db.delete(idea)
        db.commit()
