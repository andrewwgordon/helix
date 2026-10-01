"""Audit trail tests (spec §13)."""

from app.models.audit import (
    EVENT_CREATE,
    EVENT_REL_ADD,
    EVENT_REVISE,
    EVENT_STATE_CHANGE,
    AuditEvent,
)
from app.services import AuditEventService, ItemService, RelationshipService


def test_create_and_revise_emit_audit_events(session, admin):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-AUD-001", admin)
    svc.create_version(item.id, admin)
    svc.revise_item(item.id, "major", admin)

    events = AuditEventService(session).query_by_item(item.id)
    types = [e.event_type for e in events]
    assert EVENT_CREATE in types
    assert EVENT_REVISE in types


def test_lifecycle_transition_emits_audit_event(session, admin, engineer):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-AUD-002", admin)
    version = svc.create_version(item.id, admin)
    svc.change_lifecycle(version.id, "IN_WORK", engineer)

    events = AuditEventService(session).query("ItemVersion", version.id)
    state_events = [e for e in events if e.event_type == EVENT_STATE_CHANGE]
    assert len(state_events) == 1
    assert state_events[0].from_value == "DRAFT"
    assert state_events[0].to_value == "IN_WORK"


def test_relationship_emits_audit_event(session, admin):
    svc = ItemService(session)
    parent = svc.create_version(
        svc.create_item("Part", "T-AUD-P3", admin).id, admin
    )
    child = svc.create_version(svc.create_item("Part", "T-AUD-C3", admin).id, admin)
    RelationshipService(session).add_relationship(
        parent.id, child.id, "CONTAINS", admin
    )

    events = (
        session.query(AuditEvent).filter_by(event_type=EVENT_REL_ADD).all()
    )
    assert any(e.item_id == parent.item_id for e in events)
