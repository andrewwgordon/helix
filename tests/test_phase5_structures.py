"""Phase 5: product structure tests (spec §9 / §15.5)."""

from app import db
from app.services import (
    Actor,
    ItemService,
    ProductService,
    RelationshipService,
)


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _part(session, number):
    svc = ItemService(session)
    item = svc.create_item("Part", number, _actor())
    return svc.create_version(item.id, _actor())


def _product(session, number):
    return ProductService(session).create_product(number, _actor())


def _build_chain(session, product_number, mid_number, leaf_number):
    root = _product(session, product_number)
    mid = _part(session, mid_number)
    leaf = _part(session, leaf_number)
    rel = RelationshipService(session)
    rel.add_relationship(
        root.item_version_id, mid.id, "CONTAINS", _actor(), quantity=2
    )
    rel.add_relationship(mid.id, leaf.id, "CONTAINS", _actor())
    return root, mid, leaf, rel


def test_build_tree_downstream(app):
    with app.app_context():
        root, mid, leaf, rel = _build_chain(
            db.session, "T-P5-PRD", "T-P5-MID", "T-P5-LEAF"
        )
        tree = rel.build_tree(root.item_version_id, direction="down")
        assert tree["version"].id == root.item_version_id
        assert len(tree["children"]) == 1
        assert tree["children"][0]["version"].id == mid.id
        assert tree["children"][0]["children"][0]["version"].id == leaf.id
        assert float(tree["children"][0]["relationship"].quantity) == 2.0


def test_build_tree_upstream(app):
    with app.app_context():
        root, mid, leaf, rel = _build_chain(
            db.session, "T-P5-PRD2", "T-P5-MID2", "T-P5-LEAF2"
        )
        tree = rel.build_tree(leaf.id, direction="up")
        assert tree["version"].id == leaf.id
        assert tree["children"][0]["version"].id == mid.id
        assert tree["children"][0]["children"][0]["version"].id == root.item_version_id


def test_build_tree_respects_max_depth(app):
    with app.app_context():
        root, mid, leaf, rel = _build_chain(
            db.session, "T-P5-PRD3", "T-P5-MID3", "T-P5-LEAF3"
        )
        tree = rel.build_tree(root.item_version_id, direction="down", max_depth=1)
        assert len(tree["children"]) == 1
        assert tree["children"][0]["children"] == []


def test_structure_tree_page_downstream(admin_client, app):
    with app.app_context():
        root, mid, leaf, _ = _build_chain(
            db.session, "T-P5-PAGEP", "T-P5-PAGEM", "T-P5-PAGEL"
        )
        version_id = root.item_version_id

    response = admin_client.get(
        f"/structures/tree?version_id={version_id}&direction=down"
    )
    assert response.status_code == 200
    assert b"T-P5-PAGEP" in response.data
    assert b"T-P5-PAGEM" in response.data
    assert b"T-P5-PAGEL" in response.data


def test_structure_tree_page_where_used(admin_client, app):
    with app.app_context():
        root, mid, leaf, _ = _build_chain(
            db.session, "T-P5-WU-P", "T-P5-WU-M", "T-P5-WU-L"
        )
        leaf_id = leaf.id

    response = admin_client.get(
        f"/structures/tree?version_id={leaf_id}&direction=up"
    )
    assert response.status_code == 200
    assert b"T-P5-WU-P" in response.data  # top-level product is a parent


def test_add_child_through_form(admin_client, app):
    with app.app_context():
        root = _product(db.session, "T-P5-FORM-PRD")
        child = _part(db.session, "T-P5-FORM-CHILD")
        parent_version_id = root.item_version_id
        child_item_number = child.item.item_number

    get_response = admin_client.get(
        f"/structures/add-child/form?parent_version_id={parent_version_id}"
    )
    assert get_response.status_code == 200

    post_response = admin_client.post(
        "/structures/add-child/form",
        data={
            "parent_version_id": str(parent_version_id),
            "item_number": child_item_number,
            "quantity": "3",
            "find_number": "40",
        },
    )
    assert post_response.status_code == 302

    with app.app_context():
        tree = RelationshipService(db.session).build_tree(
            parent_version_id, direction="down"
        )
        assert len(tree["children"]) == 1
        child_node = tree["children"][0]
        assert child_node["version"].item.item_number == "T-P5-FORM-CHILD"
        assert float(child_node["relationship"].quantity) == 3.0
        assert child_node["relationship"].find_number == "40"


def test_unknown_item_number_flashes_error(admin_client, app):
    with app.app_context():
        root = _product(db.session, "T-P5-ERR-PRD")
        parent_version_id = root.item_version_id

    response = admin_client.post(
        "/structures/add-child/form",
        data={
            "parent_version_id": str(parent_version_id),
            "item_number": "DOES-NOT-EXIST",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        # No relationship was created.
        tree = RelationshipService(db.session).build_tree(
            parent_version_id, direction="down"
        )
        assert tree["children"] == []
