"""Related-view tabs on the Product show page.

The Product detail view embeds three standard FAB ``related_views`` tabs
joined through viewonly many-to-many relationships on the business models:

* ``ProductChildPartModelView`` - parts structurally contained (CONTAINS),
* ``ProductChildDocumentModelView`` - documents structurally contained,
* ``ProductParentRequirementModelView`` - requirements linked to the product
  through non-structural (traceability) edges.

The tabs show the *linked* revisions, not necessarily the current one,
because structure and traceability links always point at exact revisions.
"""

from app import db
from app.services import (
    Actor,
    DocumentService,
    ItemService,
    PartService,
    ProductService,
    RelationshipService,
    RequirementService,
)


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _product(number):
    return ProductService(db.session, _actor()).create_product(number, _actor())


def _part(number):
    return PartService(db.session, _actor()).create_part(number, _actor(), uom_code="EA")


def _requirement(number):
    return RequirementService(db.session, _actor()).create_requirement(
        number, _actor(), requirement_text="The system shall work."
    )


def _related_view(app, name):
    for view in app.appbuilder.baseviews:
        if view.__class__.__name__ == name:
            return view
    raise AssertionError(f"view {name} is not registered")


def test_product_related_views_registered(app):
    related = {
        view.__name__
        for view in _related_view(app, "ProductModelView").related_views
    }
    assert related == {
        "ProductChildPartModelView",
        "ProductChildDocumentModelView",
        "ProductParentRequirementModelView",
        "ProductChildFunctionModelView",
    }


def test_product_show_renders_tabs(admin_client, app):
    with app.app_context():
        product = _product("T-TAB-SHOW-PRD")
        product_id = product.item_version_id

    response = admin_client.get(f"/products/show/{product_id}")
    assert response.status_code == 200
    for caption in ("Child Parts", "Child Documents", "Parent Requirements"):
        assert caption.encode() in response.data


def test_child_parts_tab_lists_contained_parts(admin_client, app):
    with app.app_context():
        product = _product("T-TAB-PRD")
        child = _part("T-TAB-CHILD")
        RelationshipService(db.session, _actor()).add_relationship(
            product.item_version_id,
            child.item_version_id,
            "CONTAINS",
            _actor(),
            quantity=4,
        )
        product_id = product.item_version_id
        child_number = "T-TAB-CHILD"

    response = admin_client.get(f"/products/show/{product_id}")
    assert response.status_code == 200
    assert child_number.encode() in response.data


def test_child_documents_tab_lists_contained_documents(admin_client, app):
    import io

    from app.models.business import Document
    from app.models.core import Item, ItemVersion

    with app.app_context():
        product = _product("T-TAB-DOC-PRD")
        admin_client.post(
            "/documents/create/form",
            data={
                "item_number": "T-TAB-DOC",
                "file": (io.BytesIO(b"tab-doc"), "spec.txt"),
            },
            content_type="multipart/form-data",
        )
        document = (
            db.session.query(Document)
            .join(ItemVersion, Document.item_version_id == ItemVersion.id)
            .join(Item, ItemVersion.item_id == Item.id)
            .filter(Item.item_number == "T-TAB-DOC")
            .one()
        )
        RelationshipService(db.session, _actor()).add_relationship(
            product.item_version_id,
            document.item_version_id,
            "CONTAINS",
            _actor(),
        )
        product_id = product.item_version_id

    response = admin_client.get(f"/products/show/{product_id}")
    assert response.status_code == 200
    assert b"spec.txt" in response.data


def test_parent_requirements_tab_lists_linked_requirements(admin_client, app):
    with app.app_context():
        product = _product("T-TAB-REQ-PRD")
        requirement = _requirement("T-TAB-REQ")
        RelationshipService(db.session, _actor()).add_relationship(
            requirement.item_version_id,
            product.item_version_id,
            "SATISFIES",
            _actor(),
        )
        product_id = product.item_version_id
        req_number = "T-TAB-REQ"

    response = admin_client.get(f"/products/show/{product_id}")
    assert response.status_code == 200
    assert req_number.encode() in response.data


def test_child_parts_tab_shows_only_structural_links(admin_client, app):
    with app.app_context():
        product = _product("T-TAB-STRUCT-PRD")
        child = _part("T-TAB-STRUCT-CHILD")
        # A non-structural reference from the product to the part: the part
        # must NOT appear in the "Child Parts" (CONTAINS) tab.
        RelationshipService(db.session, _actor()).add_relationship(
            product.item_version_id,
            child.item_version_id,
            "REFERENCES",
            _actor(),
        )
        product_id = product.item_version_id

    response = admin_client.get(f"/products/show/{product_id}")
    assert response.status_code == 200
    assert b"T-TAB-STRUCT-CHILD" not in response.data


def test_tabs_show_linked_revision_not_current(admin_client, app):
    with app.app_context():
        product = _product("T-TAB-REV-PRD")
        child = _part("T-TAB-REV-CHILD")
        RelationshipService(db.session, _actor()).add_relationship(
            product.item_version_id,
            child.item_version_id,
            "CONTAINS",
            _actor(),
        )
        # Revise the child so its current revision is no longer the linked one.
        PartService(db.session, _actor()).revise_part(
            child.item_version.item_id, "major", _actor()
        )
        product_id = product.item_version_id

    response = admin_client.get(f"/products/show/{product_id}")
    assert response.status_code == 200
    # The linked revision A (superseded) is still listed.
    assert b"T-TAB-REV-CHILD" in response.data
