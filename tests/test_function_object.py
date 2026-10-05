"""Function business-object tests.

Covers the Function object end to end through the UI:

* menu entry and service-backed create form,
* a product performing functions (PERFORMS links, non-structural),
* the functional breakdown (CONTAINS edges between function versions,
  browsed with the structure tree in both directions),
* a part fulfilling functions (FULFILLS links) with tabs on both the Part
  and Function show pages,
* lifecycle actions on the function list.
"""

from app import db
from app.models.core import ItemVersion
from app.models.reference import RelationshipType
from app.services import (
    Actor,
    FunctionService,
    PartService,
    ProductService,
    RelationshipService,
)


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _product(number):
    return ProductService(db.session, _actor()).create_product(number, _actor())


def _part(number):
    return PartService(db.session, _actor()).create_part(number, _actor(), uom_code="EA")


def _function(number, text="The function shall be achieved."):
    return FunctionService(db.session, _actor()).create_function(
        number, _actor(), function_text=text
    )


def test_function_relationship_types_seeded(app):
    with app.app_context():
        for code in ("PERFORMS", "FULFILLS"):
            rel_type = (
                db.session.query(RelationshipType).filter_by(code=code).one()
            )
            assert rel_type.is_structural is False, code
            assert rel_type.allows_quantity is False, code


def test_functions_menu_entry(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    assert b"Functions" in response.data


def test_create_function_through_form(admin_client, app):
    response = admin_client.post(
        "/functions/create/form",
        data={
            "item_number": "T-FUN-CREATE",
            "function_text": "The UAV shall hover stably.",
            "description": "Stability function",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        function = FunctionService(db.session).items  # noqa: F841
        from app.models.business import Function

        function = (
            db.session.query(Function)
            .join(ItemVersion, Function.item_version_id == ItemVersion.id)
            .filter(ItemVersion.id == Function.item_version_id)
            .order_by(Function.item_version_id.desc())
            .first()
        )
        assert function is not None
        assert function.function_text == "The UAV shall hover stably."
        assert function.item_version.lifecycle_state.code == "DRAFT"


def test_product_performs_functions_via_add_child(admin_client, app):
    with app.app_context():
        product = _product("T-FUN-PRD")
        function = _function("T-FUN-PERFORMED")
        product_version_id = product.item_version_id
        function_version_id = function.item_version_id

    # Add child from the product show page picks the function child.
    response = admin_client.post(
        "/structures/add-child/form",
        data={
            "parent_version_id": str(product_version_id),
            "child": str(function_version_id),
        },
    )
    assert response.status_code == 302

    with app.app_context():
        # The product performs the function (PERFORMS, non-structural).
        downstream = RelationshipService(db.session).get_downstream(
            product_version_id, relationship_type="PERFORMS"
        )
        assert function_version_id in [v.id for v in downstream]
        # ...and the BOM tree does not mix the function in.
        tree = RelationshipService(db.session).build_tree(
            product_version_id, direction="down"
        )
        assert tree["children"] == []

    tab = admin_client.get(f"/products/show/{product_version_id}")
    assert tab.status_code == 200
    assert b"T-FUN-PERFORMED" in tab.data


def test_function_breakdown_parent_and_children(admin_client, app):
    with app.app_context():
        parent = _function("T-FUN-PARENT")
        child = _function("T-FUN-CHILD")
        RelationshipService(db.session, _actor()).add_relationship(
            parent.item_version_id,
            child.item_version_id,
            "CONTAINS",
            _actor(),
        )
        parent_id = parent.item_version_id
        child_id = child.item_version_id

    # Downstream: the parent function shows its child.
    down = admin_client.get(f"/structures/tree?version_id={parent_id}&direction=down")
    assert down.status_code == 200
    assert b"T-FUN-CHILD" in down.data

    # Upstream: the child function shows its (single) parent.
    up = admin_client.get(f"/structures/tree?version_id={child_id}&direction=up")
    assert up.status_code == 200
    assert b"T-FUN-PARENT" in up.data


def test_part_fulfills_function(admin_client, app):
    with app.app_context():
        function = _function("T-FUN-FULFILLED")
        part = _part("T-FUN-FULFILLING")
        function_id = function.item_version_id
        part_id = part.item_version_id

    response = admin_client.post(
        "/functions/add-fulfillment/form",
        data={
            "function_version_id": str(function_id),
            "part": str(part_id),
        },
    )
    assert response.status_code == 302

    with app.app_context():
        downstream = RelationshipService(db.session).get_downstream(
            part_id, relationship_type="FULFILLS"
        )
        assert function_id in [v.id for v in downstream]

    function_show = admin_client.get(f"/functions/show/{function_id}")
    assert function_show.status_code == 200
    assert b"Fulfilled by Parts" in function_show.data
    assert b"T-FUN-FULFILLING" in function_show.data

    part_show = admin_client.get(f"/parts/show/{part_id}")
    assert part_show.status_code == 200
    assert b"Fulfills Functions" in part_show.data
    assert b"T-FUN-FUNFILLED" in part_show.data or b"T-FUN-FULFILLED" in part_show.data


def test_function_lifecycle_action_from_list(admin_client, app):
    from app.services import LifecycleService

    with app.app_context():
        function = _function("T-FUN-LC")
        function_id = function.item_version_id
        # The valid path is DRAFT -> IN_WORK -> REVIEW.
        LifecycleService(db.session).change_lifecycle(function_id, "IN_WORK", _actor())

    response = admin_client.post(
        "/functions/action_post",
        data={"action": "submit_for_review", "rowid": str(function_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(ItemVersion, function_id).lifecycle_state.code == "REVIEW"


def test_revise_function(admin_client, app):
    with app.app_context():
        function = _function("T-FUN-REV")
        function_id = function.item_version_id

    response = admin_client.post(
        "/functions/action_post",
        data={"action": "revise_major", "rowid": str(function_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        version = db.session.get(ItemVersion, function_id)
        item = version.item
        labels = [v.revision_label for v in item.versions]
        assert labels == ["A", "B"]
