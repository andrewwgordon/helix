"""Task-oriented UI/navigation tests.

Covers the workflow improvements that let users drive PLM tasks from the
objects they work with instead of internal tables:

* the reviewer's "Pending Review" queue (filtered standard ``ModelView``),
* lifecycle actions (submit/approve/release/obsolete) directly on the
  business-object lists,
* one-click audit trail from any business-object row,
* one-click document download from the document list/show pages,
* clickable item numbers on business lists,
* task-oriented menu categories.
"""

import io

from app import db
from app.models.business import Document
from app.models.core import Item, ItemVersion
from app.services import Actor, LifecycleService, PartService


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _part(number):
    return PartService(db.session, _actor()).create_part(number, _actor(), uom_code="EA")


def _advance_to_review(version):
    actor = _actor()
    LifecycleService(db.session).change_lifecycle(version.id, "IN_WORK", actor)
    return LifecycleService(db.session).submit_for_review(version.id, actor)


def test_pending_review_menu_entry(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    assert b"Pending Review" in response.data
    assert b"Change & Release" in response.data
    assert b"Product Data" in response.data
    assert b"Traceability" in response.data


def test_pending_review_shows_only_review_versions(admin_client, app):
    with app.app_context():
        in_review = _part("T-TASK-PR-A")
        _advance_to_review(in_review.item_version)
        in_work = _part("T-TASK-PR-B")  # stays IN_WORK (created) -> DRAFT
        in_work_id = in_work.item_version.id
        in_review_number = "T-TASK-PR-A"

    response = admin_client.get("/itemversions/pending-review/list/")
    assert response.status_code == 200
    assert in_review_number.encode() in response.data
    assert f"/itemversions/show/{in_work_id}".encode() not in response.data


def test_lifecycle_action_from_business_list(admin_client, app):
    with app.app_context():
        part = _part("T-TASK-LC")
        LifecycleService(db.session).change_lifecycle(
            part.item_version.id, "IN_WORK", _actor()
        )
        part_id = part.item_version_id

    response = admin_client.post(
        "/parts/action_post",
        data={"action": "submit_for_review", "rowid": str(part_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        version = db.session.get(ItemVersion, part_id)
        assert version.lifecycle_state.code == "REVIEW"


def test_audit_action_from_business_list(admin_client, app):
    with app.app_context():
        part = _part("T-TASK-AU")
        item_id = part.item_version.item_id

    response = admin_client.post(
        "/parts/action_post",
        data={"action": "audit", "rowid": str(part.item_version_id)},
    )
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "/audit/list/" in location
    assert f"_flt_0_item_id={item_id}" in location


def test_business_list_rows_link_to_item_page(admin_client, app):
    with app.app_context():
        part = _part("T-TASK-LINK")
        item_id = part.item_version.item_id

    response = admin_client.get("/parts/list/")
    assert response.status_code == 200
    assert f'/items/show/{item_id}"'.encode() in response.data


def test_document_download(admin_client, app):
    with app.app_context():
        admin_client.post(
            "/documents/create/form",
            data={
                "item_number": "T-TASK-DOC",
                "file": (io.BytesIO(b"task-flow-contents"), "task.txt"),
            },
            content_type="multipart/form-data",
        )
        document = (
            db.session.query(Document)
            .join(ItemVersion, Document.item_version_id == ItemVersion.id)
            .join(Item, ItemVersion.item_id == Item.id)
            .filter(Item.item_number == "T-TASK-DOC")
            .one()
        )
        document_id = document.item_version_id

    response = admin_client.get(f"/documents/download/{document_id}")
    assert response.status_code == 200
    assert response.data == b"task-flow-contents"


def test_document_list_links_to_download(admin_client, app):
    response = admin_client.get("/documents/list/")
    assert response.status_code == 200
    assert b"documents/download" in response.data


def test_business_show_page_includes_description(admin_client, app):
    with app.app_context():
        part = _part("T-TASK-DESC")
        part_id = part.item_version_id

    response = admin_client.get(f"/parts/show/{part_id}")
    assert response.status_code == 200
    assert b"Notes" in response.data
