"""
The pad endpoint, and the one property that makes the pad worth drawing.

The interface renders the whole plane rather than the seven named
relationships, because the argument is the *shape*: a row where the respect is
constant and the register changes anyway. If a table edit ever flattens that
row, the pad keeps rendering, the page keeps working, and the feature quietly
stops making its point. So the shape is asserted rather than the pixels.
"""

from __future__ import annotations

import pytest

import app as app_module
from app import app


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)


@pytest.fixture()
def client():
    return app.test_client()


def _grid(client, lang):
    res = client.get(f"/api/register/pad?lang={lang}")
    assert res.status_code == 200
    return res.get_json()["grid"]


def _cell(grid, power, solidarity):
    return next(c for c in grid
                if c["power"] == power and c["solidarity"] == solidarity)


@pytest.mark.parametrize("lang", ["bn", "hi", "de", "ja", "es", "ur"])
def test_closeness_changes_the_answer_at_constant_respect(client, lang):
    """
    The grandmother row. Somebody senior to you and distant gets the polite
    form; somebody senior to you and close does not. Same respect, different
    register — which is the whole reason there are two axes.
    """
    grid = _grid(client, lang)
    distant = _cell(grid, 2, 0)["level_name"]
    close = _cell(grid, 2, 2)["level_name"]
    assert distant != close, (
        f"{lang}: a stranger and a grandmother landed on {distant} alike — "
        f"the pad has nothing left to show"
    )


def test_the_grid_covers_the_whole_plane(client):
    grid = _grid(client, "bn")
    assert len(grid) == 12
    assert {(c["power"], c["solidarity"]) for c in grid} == {
        (p, s) for p in range(4) for s in range(3)
    }


def test_every_cell_carries_what_the_ui_draws(client):
    for cell in _grid(client, "bn"):
        for key in ("level_name", "power_label", "solidarity_label", "named", "corner"):
            assert key in cell, f"the pad renders {key!r}"
        assert cell["level_name"] in ("Close", "Casual", "Polite", "Formal")


def test_the_named_relationships_land_on_the_plane(client):
    """
    Each label is drawn into the cell at its coordinates. A relationship whose
    coordinates fall outside the grid would simply never appear.
    """
    res = client.get("/api/register/pad?lang=bn").get_json()
    grid = {(c["power"], c["solidarity"]) for c in res["grid"]}
    for point in res["points"]:
        assert (point["power"], point["solidarity"]) in grid, (
            f"{point['key']} sits off the plane the pad draws"
        )
    named = {c["named"] for c in res["grid"] if c["named"]}
    assert named == {p["key"] for p in res["points"]}


def test_languages_divide_the_plane_differently(client):
    """
    Drawn per language because they disagree — a shopkeeper you know takes
    तुम in Delhi and Sie in Munich. If every language gave the same plane,
    fetching it per language would be waste.
    """
    hindi = _cell(_grid(client, "hi"), 1, 1)["level_name"]
    german = _cell(_grid(client, "de"), 1, 1)["level_name"]
    assert hindi != german


def test_a_language_with_no_table_gets_an_empty_grid_not_an_error(client):
    """The pad hides itself rather than the page breaking."""
    res = client.get("/api/register/pad?lang=zz")
    assert res.status_code == 200
    assert res.get_json()["grid"] == []


def test_the_drag_endpoint_answers_for_any_point(client):
    res = client.get("/api/register/pad/at?lang=bn&power=2&solidarity=2")
    assert res.status_code == 200
    body = res.get_json()
    assert body["relationship"] == "elder_family"
    assert body["level_name"] == "Casual"
