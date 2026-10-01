"""Relationship and structure service tests (spec §14.7 / §9)."""

import pytest

from app.services import ItemService, RelationshipService
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    RelationshipCycleError,
    ReleasedVersionImmutableError,
    ValidationError,
)


def _new_part(session, admin, number):
    svc = ItemService(session)
    item = svc.create_item("Part", number, admin)
    return svc.create_version(item.id, admin)


def test_add_contains_defaults_quantity(session, admin):
    parent = _new_part(session, admin, "T-REL-P1")
    child = _new_part(session, admin, "T-REL-C1")
    rel = RelationshipService(session).add_relationship(
        parent.id, child.id, "CONTAINS", admin
    )
    assert rel.relationship_type.code == "CONTAINS"
    assert float(rel.quantity) == 1.0


def test_add_contains_with_quantity_and_find(session, admin):
    parent = _new_part(session, admin, "T-REL-P2")
    child = _new_part(session, admin, "T-REL-C2")
    rel = RelationshipService(session).add_relationship(
        parent.id, child.id, "CONTAINS", admin, quantity=4, find_number="30"
    )
    assert float(rel.quantity) == 4.0
    assert rel.find_number == "30"


def test_self_relationship_rejected(session, admin):
    version = _new_part(session, admin, "T-REL-SELF")
    with pytest.raises(ValidationError):
        RelationshipService(session).add_relationship(
            version.id, version.id, "CONTAINS", admin
        )


def test_quantity_not_allowed_for_references(session, admin):
    a = _new_part(session, admin, "T-REL-A3")
    b = _new_part(session, admin, "T-REL-B3")
    with pytest.raises(ValidationError):
        RelationshipService(session).add_relationship(
            a.id, b.id, "REFERENCES", admin, quantity=2
        )


def test_duplicate_relationship_rejected(session, admin):
    parent = _new_part(session, admin, "T-REL-P4")
    child = _new_part(session, admin, "T-REL-C4")
    svc = RelationshipService(session)
    svc.add_relationship(parent.id, child.id, "CONTAINS", admin)
    with pytest.raises(ConflictError):
        svc.add_relationship(parent.id, child.id, "CONTAINS", admin)


def test_unknown_relationship_type_rejected(session, admin):
    a = _new_part(session, admin, "T-REL-A5")
    b = _new_part(session, admin, "T-REL-B5")
    with pytest.raises(NotFoundError):
        RelationshipService(session).add_relationship(a.id, b.id, "NOPE", admin)


def test_cycle_detection(session, admin):
    a = _new_part(session, admin, "T-CYC-A")
    b = _new_part(session, admin, "T-CYC-B")
    svc = RelationshipService(session)
    svc.add_relationship(a.id, b.id, "CONTAINS", admin)
    with pytest.raises(RelationshipCycleError):
        svc.add_relationship(b.id, a.id, "CONTAINS", admin)


def test_upstream_and_downstream(session, admin):
    root = _new_part(session, admin, "T-TR-ROOT")
    mid = _new_part(session, admin, "T-TR-MID")
    leaf = _new_part(session, admin, "T-TR-LEAF")
    svc = RelationshipService(session)
    svc.add_relationship(root.id, mid.id, "CONTAINS", admin)
    svc.add_relationship(mid.id, leaf.id, "CONTAINS", admin)

    downstream = svc.get_downstream(root.id)
    assert {v.id for v in downstream} == {mid.id, leaf.id}
    assert {v.id for v in svc.get_upstream(leaf.id)} == {root.id, mid.id}
    assert {v.id for v in svc.get_upstream(leaf.id, max_depth=1)} == {mid.id}


def test_released_parent_rejects_new_relationship(
    session, admin, engineer, reviewer, plm_manager
):
    from app.services import ItemService as IS

    svc = IS(session)
    parent_item = svc.create_item("Part", "T-REL-RELP", admin)
    parent = svc.create_version(parent_item.id, admin)
    child = _new_part(session, admin, "T-REL-RELC")

    svc.change_lifecycle(parent.id, "IN_WORK", engineer)
    svc.change_lifecycle(parent.id, "REVIEW", engineer)
    svc.change_lifecycle(parent.id, "APPROVED", reviewer)
    svc.change_lifecycle(parent.id, "RELEASED", plm_manager)

    with pytest.raises(ReleasedVersionImmutableError):
        RelationshipService(session).add_relationship(
            parent.id, child.id, "CONTAINS", admin
        )
