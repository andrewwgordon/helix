"""FAB view tests (spec §15).

Renders the standard list views as an authenticated admin and checks that the
registered view/menu structure matches the specification.
"""

import pytest

from app import db
from app.services import Actor, PartService

LIST_ROUTES = [
    "/items/list/",
    "/parts/list/",
    "/documents/list/",
    "/requirements/list/",
    "/functions/list/",
    "/products/list/",
    "/itemversions/list/",
    "/itemversions/pending-review/list/",
    "/relationships/list/",
    "/baselines/list/",
    "/audit/list/",
    "/itemtypes/list/",
    "/lifecyclestates/list/",
    "/lifecycle-transitions/list/",
    "/relationshiptypes/list/",
    "/uoms/list/",
    "/makebuycodes/list/",
    "/verificationmethods/list/",
    "/prioritycodes/list/",
    "/productfamilies/list/",
    "/markets/list/",
]

EXPECTED_VIEWS = [
    "ItemModelView",
    "ItemVersionModelView",
    "PendingReviewModelView",
    "ItemRelationshipModelView",
    "BaselineModelView",
    "BaselineMemberModelView",
    "PartModelView",
    "DocumentModelView",
    "ProductChildPartModelView",
    "ProductChildDocumentModelView",
    "ProductParentRequirementModelView",
    "RequirementModelView",
    "FunctionModelView",
    "ProductChildFunctionModelView",
    "FunctionFulfilledByPartModelView",
    "PartFulfillsFunctionModelView",
    "ProductModelView",
    "AuditEventModelView",
    "ItemTypeModelView",
    "LifecycleStateModelView",
    "LifecycleTransitionModelView",
    "RelationshipTypeModelView",
]


def test_expected_views_registered(app):
    registered = {view.__class__.__name__ for view in app.appbuilder.baseviews}
    missing = set(EXPECTED_VIEWS) - registered
    assert not missing, f"views not registered: {missing}"


@pytest.mark.parametrize("route", LIST_ROUTES)
def test_list_routes_render(admin_client, route):
    response = admin_client.get(route)
    assert response.status_code == 200, f"{route} -> {response.status_code}"


def test_parts_list_is_filterable(admin_client, app):
    with app.app_context():
        PartService(db.session).create_part(
            "T-VIEW-PART",
            Actor(username="viewadmin", roles=frozenset({"Admin"}), is_admin=True),
            uom_code="EA",
            material="UNIQUEMATERIAL",
        )
    response = admin_client.get("/parts/list/?_flt_0_material=UNIQUEMATERIAL")
    assert response.status_code == 200
    assert b"T-VIEW-PART" in response.data


def test_read_only_views_hide_add_button(admin_client):
    response = admin_client.get("/items/list/")
    assert response.status_code == 200
    # ItemModelView is read-only: no add action is exposed.
    assert b"/items/add/" not in response.data


def test_reference_view_allows_add(admin_client):
    response = admin_client.get("/itemtypes/list/")
    assert response.status_code == 200
    assert b"itemtypes/add" in response.data
