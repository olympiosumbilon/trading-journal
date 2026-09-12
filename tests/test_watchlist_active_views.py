from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models import WatchlistIdea


def test_active_pipeline_supports_status_filters_and_list_kanban():
    marker = f"pytest-active-views-{uuid4().hex}"
    idea_ids = []
    with TestClient(app) as client:
        for suffix, status in (("waiting", "WAITING"), ("monitoring", "MONITORING"), ("running", "EXECUTED")):
            response = client.post(
                "/watchlist/new",
                data={"title": f"{marker}-{suffix}", "status": status},
                follow_redirects=False,
            )
            assert response.status_code == 303

        with SessionLocal() as db:
            idea_ids = [i.id for i in db.query(WatchlistIdea).filter(WatchlistIdea.title.like(f"{marker}%")).all()]

        for status_value, expected_title, excluded_title in (
            ("WAITING", f"{marker}-waiting", f"{marker}-monitoring"),
            ("MONITORING", f"{marker}-monitoring", f"{marker}-waiting"),
            ("RUNNING", f"{marker}-running", f"{marker}-waiting"),
        ):
            response = client.get(f"/watchlist/?view=active&view_mode=list&active_status={status_value}")
            assert response.status_code == 200
            assert expected_title in response.text
            assert excluded_title not in response.text

        kanban = client.get("/watchlist/?view=active&view_mode=kanban&active_status=ALL")
        assert kanban.status_code == 200
        assert "Waiting for POI" in kanban.text
        assert "Monitoring Trigger" in kanban.text
        assert "Running Trades" in kanban.text
        assert f"{marker}-waiting" in kanban.text
        assert f"{marker}-monitoring" in kanban.text
        assert f"{marker}-running" in kanban.text

    with SessionLocal() as db:
        for idea_id in idea_ids:
            idea = db.get(WatchlistIdea, idea_id)
            if idea:
                db.delete(idea)
        db.commit()
