"""Phase 4: service-backed create / revise form tests (spec §15.3)."""

import io

from app import db
from app.models.business import Document, Part
from app.models.core import Item, ItemVersion
from app.models.reference import UnitOfMeasure


def _uom_id(code):
    return str(db.session.query(UnitOfMeasure).filter_by(code=code).one().id)


def _find_item(number):
    return db.session.query(Item).filter_by(item_number=number).one()


def test_part_add_redirects_to_form(admin_client):
    response = admin_client.get("/parts/add/")
    assert response.status_code == 302
    assert "/parts/create/form" in response.headers["Location"]


def test_create_part_through_form(admin_client, app):
    response = admin_client.post(
        "/parts/create/form",
        data={
            "item_number": "T-FORM-PART",
            "uom": _uom_id("EA"),
            "material": "Titanium",
            "weight": "1.25",
            "description": "from form",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        part = (
            db.session.query(Part)
            .join(ItemVersion, Part.item_version_id == ItemVersion.id)
            .join(Item, ItemVersion.item_id == Item.id)
            .filter(Item.item_number == "T-FORM-PART")
            .one()
        )
        assert part.material == "Titanium"
        assert part.item_version.revision_label == "A"


def test_create_requirement_through_form(admin_client, app):
    response = admin_client.post(
        "/requirements/create/form",
        data={
            "item_number": "T-FORM-REQ",
            "requirement_text": "The system shall comply.",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assert _find_item("T-FORM-REQ") is not None


def test_create_product_through_form(admin_client, app):
    response = admin_client.post(
        "/products/create/form",
        data={"item_number": "T-FORM-PRD", "platform": "P1"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert _find_item("T-FORM-PRD") is not None


def test_create_document_upload_through_form(admin_client, app):
    response = admin_client.post(
        "/documents/create/form",
        data={
            "item_number": "T-FORM-DOC",
            "file": (io.BytesIO(b"file-contents"), "design.txt"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        document = (
            db.session.query(Document)
            .join(ItemVersion, Document.item_version_id == ItemVersion.id)
            .join(Item, ItemVersion.item_id == Item.id)
            .filter(Item.item_number == "T-FORM-DOC")
            .one()
        )
        assert document.file_name == "design.txt"
        assert document.file_size == len(b"file-contents")


def test_business_edit_and_delete_routes_disabled(admin_client):
    # Writes go through services: no direct edit/delete endpoints exist.
    assert admin_client.get("/parts/edit/1").status_code == 404
    assert admin_client.get("/parts/delete/1").status_code == 404
    assert admin_client.get("/items/edit/1").status_code == 404


def test_create_forms_render(admin_client):
    for route in (
        "/parts/create/form",
        "/documents/create/form",
        "/requirements/create/form",
        "/products/create/form",
    ):
        assert admin_client.get(route).status_code == 200, route


def test_revise_document_through_form(admin_client, app):
    admin_client.post(
        "/documents/create/form",
        data={
            "item_number": "T-FORM-DOCREV",
            "file": (io.BytesIO(b"v1"), "v1.txt"),
        },
        content_type="multipart/form-data",
    )
    with app.app_context():
        item = _find_item("T-FORM-DOCREV")

    get_response = admin_client.get(
        f"/documents/revise/form?item_id={item.id}&change_type=minor"
    )
    assert get_response.status_code == 200

    post_response = admin_client.post(
        "/documents/revise/form",
        data={
            "item_id": str(item.id),
            "change_type": "minor",
            "description": "updated",
            "file": (io.BytesIO(b"v2-longer"), "v2.txt"),
        },
        content_type="multipart/form-data",
    )
    assert post_response.status_code == 302

    with app.app_context():
        versions = (
            db.session.query(ItemVersion)
            .filter_by(item_id=item.id)
            .order_by(ItemVersion.version_sequence)
            .all()
        )
        assert [v.revision_label for v in versions] == ["A", "A.1"]
        assert versions[-1].description == "updated"
