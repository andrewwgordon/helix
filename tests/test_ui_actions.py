"""FAB list-view action dispatch tests (spec §3.3.2).

FAB posts list-view actions to ``action_post`` and passes the selected rows as
a **list**, while show-view actions receive a single instance. These tests
exercise both paths for the service-backed actions introduced through Phase 7.
"""

from app import db
from app.models.core import Item, ItemRelationship, ItemVersion
from app.services import (
    Actor,
    ItemService,
    LifecycleService,
    PartService,
    RelationshipService,
)


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def test_lifecycle_action_from_list(admin_client, app):
    with app.app_context():
        actor = _actor()
        svc = ItemService(db.session)
        item = svc.create_item("Part", "T-ACT-LC", actor)
        version = svc.create_version(item.id, actor)
        LifecycleService(db.session).change_lifecycle(version.id, "IN_WORK", actor)
        version_id = version.id

    response = admin_client.post(
        "/itemversions/action_post",
        data={"action": "submit_for_review", "rowid": str(version_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(ItemVersion, version_id).lifecycle_state.code == "REVIEW"


def test_revise_major_action_from_list_single(admin_client, app):
    with app.app_context():
        actor = _actor()
        part = PartService(db.session).create_part("T-ACT-REV1", actor, uom_code="EA")
        part_id = part.item_version_id

    response = admin_client.post(
        "/parts/action_post",
        data={"action": "revise_major", "rowid": str(part_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        item = db.session.query(Item).filter_by(item_number="T-ACT-REV1").one()
        versions = ItemService(db.session).list_versions(item.id)
        assert [v.revision_label for v in versions] == ["A", "B"]


def test_revise_major_action_from_list_multiple(admin_client, app):
    with app.app_context():
        actor = _actor()
        part_ids = []
        for number in ("T-ACT-REV2", "T-ACT-REV3"):
            part = PartService(db.session).create_part(
                number, actor, uom_code="EA"
            )
            part_ids.append(part.item_version_id)

    response = admin_client.post(
        "/parts/action_post",
        data={"action": "revise_major", "rowid": [str(pk) for pk in part_ids]},
    )
    assert response.status_code == 302

    with app.app_context():
        for number in ("T-ACT-REV2", "T-ACT-REV3"):
            item = db.session.query(Item).filter_by(item_number=number).one()
            versions = ItemService(db.session).list_versions(item.id)
            assert [v.revision_label for v in versions] == ["A", "B"]


def test_relationship_remove_action_from_list(admin_client, app):
    with app.app_context():
        actor = _actor()
        svc = ItemService(db.session)
        parent = svc.create_version(
            svc.create_item("Part", "T-ACT-REL-P", actor).id, actor
        )
        child = svc.create_version(
            svc.create_item("Part", "T-ACT-REL-C", actor).id, actor
        )
        relationship = RelationshipService(db.session).add_relationship(
            parent.id, child.id, "CONTAINS", actor
        )
        relationship_id = relationship.id

    response = admin_client.post(
        "/relationships/action_post",
        data={"action": "remove", "rowid": str(relationship_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(ItemRelationship, relationship_id) is None


def test_part_revise_action_via_show_route(admin_client, app):
    # The show-view route passes a single instance; the same action must work.
    with app.app_context():
        actor = _actor()
        part = PartService(db.session).create_part("T-ACT-SHOW", actor, uom_code="EA")
        part_id = part.item_version_id

    response = admin_client.get(f"/parts/action/revise_minor/{part_id}")
    assert response.status_code == 302

    with app.app_context():
        item = db.session.query(Item).filter_by(item_number="T-ACT-SHOW").one()
        labels = [
            v.revision_label for v in ItemService(db.session).list_versions(item.id)
        ]
        assert labels == ["A", "A.1"]
