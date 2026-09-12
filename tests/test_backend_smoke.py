import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/trades/",
        "/trades/new",
        "/watchlist/",
        "/watchlist/new",
        "/dashboard/",
        "/analysis/",
        "/summary/",
    ],
)
def test_core_pages_render(path):
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200


def test_missing_trade_returns_404():
    with TestClient(app) as client:
        response = client.get("/trades/2147483647")
    assert response.status_code == 404
