"""UI navigation tests (spec §3.3.2 / §15.6).

Covers the cross-navigation improvements that keep the UI to the standard
``list -> show -> edit`` pattern:

* the Item show page embeds the revision history via ``related_views``,
* every identity/business view exposes a standard "Revisions" action that
  links to the filtered ``ItemVersionModelView`` list,
* revision lists link back to the stable item identity.
"""

from app import db
from app.services import Actor, ItemService, PartService, ProductService


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _view(app, name):
    for view in app.appbuilder.baseviews:
        if view.__class__.__name__ == name:
            return view
    raise AssertionError(f"view {name} is not registered")


def test_item_view_embeds_revision_history(app):
    item_view = _view(app, "ItemModelView")
    related = {view.__name__ for view in item_view.related_views}
    assert "ItemVersionModelView" in related


def test_item_show_lists_revisions(admin_client, app):
    with app.app_context():
        actor = _actor()
        svc = ItemService(db.session)
        item = svc.create_item("Part", "T-NAV-ITEM", actor)
        svc.create_version(item.id, actor)  # Rev A
        svc.create_version(item.id, actor)  # Rev B
        item_id = item.id

    response = admin_client.get(f"/items/show/{item_id}")
    assert response.status_code == 200
    assert b"T-NAV-ITEM" in response.data
    # The revision history is embedded as a standard related view tab.
    assert b"nav-tabs" in response.data
    assert b"/itemversions/show/" in response.data


def test_item_revisions_action_targets_filtered_history(admin_client, app):
    with app.app_context():
        actor = _actor()
        item = ItemService(db.session).create_item("Part", "T-NAV-ACT", actor)
        ItemService(db.session).create_version(item.id, actor)
        item_id = item.id

    response = admin_client.get(f"/items/action/revisions/{item_id}")
    assert response.status_code == 302
    assert f"_flt_0_item={item_id}" in response.headers["Location"]


def test_revision_list_links_back_to_item(admin_client, app):
    with app.app_context():
        actor = _actor()
        item = ItemService(db.session).create_item("Part", "T-NAV-LINK", actor)
        ItemService(db.session).create_version(item.id, actor)
        item_id = item.id

    response = admin_client.get("/itemversions/list/")
    assert response.status_code == 200
    assert b"T-NAV-LINK" in response.data
    assert f"/items/show/{item_id}".encode() in response.data


def test_business_views_expose_revisions_action(app):
    for name in (
        "PartModelView",
        "DocumentModelView",
        "RequirementModelView",
        "ProductModelView",
    ):
        view = _view(app, name)
        assert "revisions" in view.actions, f"{name} has no revisions action"
        assert view.actions["revisions"].multiple is False, name
        assert view.actions["revisions"].single is True, name
        assert "revisions" in view.base_permissions, name


def test_business_revisions_action_targets_item_history(admin_client, app):
    with app.app_context():
        part = PartService(db.session).create_part(
            "T-NAV-PART", _actor(), uom_code="EA"
        )
        part_id = part.item_version_id
        item_id = part.item_version.item_id

    response = admin_client.get(f"/parts/action/revisions/{part_id}")
    assert response.status_code == 302
    assert f"_flt_0_item={item_id}" in response.headers["Location"]


def test_product_revisions_action_targets_item_history(admin_client, app):
    with app.app_context():
        product = ProductService(db.session).create_product("T-NAV-PRD", _actor())
        product_id = product.item_version_id
        item_id = product.item_version.item_id

    response = admin_client.get(f"/products/action/revisions/{product_id}")
    assert response.status_code == 302
    assert f"_flt_0_item={item_id}" in response.headers["Location"]
