"""Database constraint tests (spec §7)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.core import Item, ItemRelationship
from app.models.reference import ItemType
from app.services import ItemService, RelationshipService


def _item_type(session, code):
    return session.query(ItemType).filter_by(code=code).one()


def test_unique_item_number_per_type(session, admin):
    svc = ItemService(session)
    svc.create_item("Part", "T-CON-U1", admin)

    item_type = _item_type(session, "Part")
    session.add(Item(item_type_id=item_type.id, item_number="T-CON-U1"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_item_type_foreign_key_enforced(session):
    session.add(Item(item_type_id=999999, item_number="T-CON-FK"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_referenced_item_type_cannot_be_deleted(session, admin):
    ItemService(session).create_item("Part", "T-CON-DEL", admin)
    item_type = _item_type(session, "Part")
    session.delete(item_type)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_relationship_quantity_check(session, admin):
    svc = ItemService(session)
    a = svc.create_version(svc.create_item("Part", "T-CON-QA", admin).id, admin)
    b = svc.create_version(svc.create_item("Part", "T-CON-QB", admin).id, admin)

    rel_type = RelationshipService(session)._get_type("CONTAINS")
    session.add(
        ItemRelationship(
            relationship_type_id=rel_type.id,
            source_item_version_id=a.id,
            target_item_version_id=b.id,
            quantity=0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
