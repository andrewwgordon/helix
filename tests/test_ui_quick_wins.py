"""Quick-win UI configuration tests (spec §3.3).

Covers the first batch of UI/navigation improvements:

* current-revision default filter on business lists,
* deterministic list ordering,
* grouped show fieldsets,
* lifecycle/priority status badges via ``formatters_columns``,
* inline help on the custom create/revise forms,
* single-record actions no longer exposed as bulk list actions.
"""

from markupsafe import Markup

from app import db
from app.services import Actor, ItemService, PartService, ProductService


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _view(app, name):
    for view in app.appbuilder.baseviews:
        if view.__class__.__name__ == name:
            return view
    raise AssertionError(f"view {name} is not registered")


def test_current_version_filter_helper(app):
    from app.views.filters import current_version_ids

    with app.app_context():
        actor = _actor()
        product = ProductService(db.session).create_product("T-QW-CUR", actor)
        old_id = product.item_version_id
        revised = ProductService(db.session).revise_product(
            product.item_version.item_id, "major", actor
        )
        new_id = revised.item_version_id

        current = set(current_version_ids())
        assert new_id in current
        assert old_id not in current


def test_business_lists_apply_current_revision_filter(app):
    with app.app_context():
        actor = _actor()
        product = ProductService(db.session).create_product("T-QW-FLT", actor)
        old_id = product.item_version_id
        revised = ProductService(db.session).revise_product(
            product.item_version.item_id, "major", actor
        )
        new_id = revised.item_version_id

        view = _view(app, "ProductModelView")
        assert view.base_filters, "ProductModelView must define base_filters"

        _, rows = view.datamodel.query(
            view._base_filters, "item_version_id", "asc", page=0, page_size=5000
        )
        ids = {row.item_version_id for row in rows}
        assert new_id in ids
        assert old_id not in ids


def test_fieldsets_reference_existing_show_columns(app):
    checked = 0
    for view in app.appbuilder.baseviews:
        fieldsets = getattr(view, "show_fieldsets", None)
        if not fieldsets:
            continue
        show_columns = set(view.show_columns or [])
        for _title, options in fieldsets:
            for field in options.get("fields", []):
                assert field in show_columns, (
                    f"{view.__class__.__name__} fieldset field '{field}' "
                    "is not present in show_columns"
                )
        checked += 1
    assert checked >= 10


def test_base_order_is_configured(app):
    expected = {
        "ItemModelView": "item_number",
        "ItemVersionModelView": "item.item_number",
        "ItemRelationshipModelView": "source_item_version_id",
        "PartModelView": "item_version_id",
        "BaselineModelView": "baseline_number",
        "BaselineMemberModelView": "id",
        "AuditEventModelView": "created_on",
        "LifecycleStateModelView": "sequence",
        "ItemTypeModelView": "code",
    }
    for name, column in expected.items():
        view = _view(app, name)
        assert view.base_order is not None, f"{name} has no base_order"
        assert view.base_order[0] == column, f"{name}: {view.base_order}"


def test_formatters_render_bootstrap_labels():
    from app.views.formatters import (
        active_flag,
        baseline_status,
        lifecycle_state,
        priority_code,
    )

    class _Coded:
        def __init__(self, code, name):
            self.code = code
            self.name = name

    released = lifecycle_state(_Coded("RELEASED", "Released"))
    assert isinstance(released, Markup)
    assert "label-success" in released
    assert "Released" in released

    assert "label-danger" in priority_code(_Coded("MANDATORY", "Mandatory"))
    assert "Frozen" in baseline_status("FROZEN")
    assert "Active" in active_flag(True)
    assert "Inactive" in active_flag(False)
    assert lifecycle_state(None) == ""


def test_single_record_actions_are_not_bulk(app):
    item_version = _view(app, "ItemVersionModelView")
    for name in ("audit", "structure", "where_used", "add_child"):
        assert item_version.actions[name].multiple is False, name
        assert item_version.actions[name].single is True, name

    product = _view(app, "ProductModelView")
    for name in ("structure", "add_child"):
        assert product.actions[name].multiple is False, name


def test_bulk_friendly_actions_stay_multi(app):
    item_version = _view(app, "ItemVersionModelView")
    for name in ("submit_for_review", "approve", "release", "obsolete"):
        assert item_version.actions[name].multiple is True, name

    assert _view(app, "PartModelView").actions["revise_major"].multiple is True


def test_custom_forms_expose_help_text(app):
    from app.views.baseline_views import BaselineForm
    from app.views.business_forms import PartForm, ProductForm, RequirementForm
    from app.views.structure_views import StructureChildForm

    assert PartForm().uom.description
    assert PartForm().make_buy.description
    assert ProductForm().release_target.description
    assert RequirementForm().requirement_text.description
    assert BaselineForm().product.description
    assert StructureChildForm().quantity.description


def test_show_page_fieldsets_render(admin_client, app):
    with app.app_context():
        part = PartService(db.session).create_part(
            "T-QW-SHOW", _actor(), uom_code="EA"
        )
        pk = part.item_version_id

    response = admin_client.get(f"/parts/show/{pk}")
    assert response.status_code == 200
    assert b"Identification" in response.data
    assert b"Classification" in response.data


def test_lifecycle_badge_renders_in_list(admin_client, app):
    with app.app_context():
        actor = _actor()
        item = ItemService(db.session).create_item("Part", "T-QW-BADGE", actor)
        ItemService(db.session).create_version(item.id, actor)

    response = admin_client.get("/itemversions/list/")
    assert response.status_code == 200
    assert b'T-QW-BADGE' in response.data
    assert b"label label-" in response.data
