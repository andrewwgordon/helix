"""Summary dashboard tests (spec §15.5 / §15.6 rule 4).

The dashboard is a standard FAB ``IndexView`` subclass registered via
``FAB_INDEX_VIEW``. It must render at ``/`` and link only to existing standard
list views (no parallel navigation tree).
"""

import re

from sqlalchemy import func

from app import db
from app.models.core import Item
from app.services import Actor, ProductService


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def test_index_view_is_summary_dashboard(app):
    assert app.appbuilder.indexview.__name__ == "SummaryIndexView"


def test_dashboard_renders(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    assert b"PLM Dashboard" in response.data
    assert b"Revisions by lifecycle state" in response.data
    assert b"Baselines by status" in response.data


def test_dashboard_cards_link_to_standard_lists(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    for route in (b"/items/list/", b"/parts/list/", b"/baselines/list/"):
        assert route in response.data, route


def test_dashboard_lifecycle_rows_link_to_filtered_revisions(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    assert b"_flt_0_lifecycle_state=" in response.data


def test_dashboard_counts_reflect_database(admin_client, app):
    with app.app_context():
        ProductService(db.session).create_product("T-DASH-PRD", _actor())
        expected = db.session.query(func.count(Item.id)).scalar()

    response = admin_client.get("/")
    assert response.status_code == 200
    pattern = rb'<h3 class="h2">\s*%d\s*</h3>' % expected
    assert re.search(pattern, response.data), "item count not rendered"


def test_dashboard_is_public(client):
    # The FAB index page is reachable without a session, as before.
    response = client.get("/")
    assert response.status_code == 200
    assert b"PLM Dashboard" in response.data
