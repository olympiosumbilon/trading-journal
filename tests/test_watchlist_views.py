from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import WatchlistIdea


def test_active_and_running_views_respect_kanban_or_grid_mode():
    marker = f"pytest-view-parity-{uuid4().hex}"
    idea_id = None

    with TestClient(app) as client:
        response = client.post(
            "/watchlist/new",
            data={"title": marker, "status": "EXECUTED"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            idea_id = db.query(WatchlistIdea).filter(WatchlistIdea.title == marker).one().id

        active_list = client.get("/watchlist/?view=active&view_mode=list")
        assert active_list.status_code == 200
        assert 'class="wl-list-table"' in active_list.text
        assert 'id="colRunning"' not in active_list.text
        assert marker in active_list.text

        active_grid = client.get("/watchlist/?view=active&view_mode=grid")
        assert active_grid.status_code == 200
        assert 'class="wl-cards-grid"' in active_grid.text
        assert 'id="colRunning"' not in active_grid.text
        assert marker in active_grid.text

        running_list = client.get("/watchlist/?view=running&view_mode=list")
        assert running_list.status_code == 200
        assert 'class="wl-list-table"' in running_list.text
        assert marker in running_list.text

        running_grid = client.get("/watchlist/?view=running&view_mode=grid")
        assert running_grid.status_code == 200
        assert 'class="wl-cards-grid"' in running_grid.text
        assert 'id="colRunning"' not in running_grid.text
        assert marker in running_grid.text

    with SessionLocal() as db:
        idea = db.get(WatchlistIdea, idea_id)
        if idea:
            db.delete(idea)
        db.commit()
