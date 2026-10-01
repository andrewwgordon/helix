"""Phase 6: lifecycle service tests (spec §11 / §14.8)."""

import pytest

from app.models.audit import EVENT_STATE_CHANGE
from app.services import AuditEventService, ItemService, LifecycleService
from app.services.exceptions import (
    AuthorizationError,
    InvalidLifecycleTransitionError,
    NotFoundError,
)


def _version(session, admin, number):
    svc = ItemService(session)
    item = svc.create_item("Part", number, admin)
    return svc.create_version(item.id, admin)


def test_full_lifecycle_path(session, admin, engineer, reviewer, plm_manager):
    version = _version(session, admin, "T-L6-001")
    lifecycle = LifecycleService(session)

    lifecycle.change_lifecycle(version.id, "IN_WORK", engineer)
    lifecycle.submit_for_review(version.id, engineer)
    assert version.lifecycle_state.code == "REVIEW"

    lifecycle.approve(version.id, reviewer)
    assert version.lifecycle_state.code == "APPROVED"

    lifecycle.release(version.id, plm_manager)
    assert version.lifecycle_state.code == "RELEASED"

    lifecycle.obsolete(version.id, plm_manager)
    assert version.lifecycle_state.code == "OBSOLETE"


def test_submit_for_review_requires_in_work(session, admin, engineer):
    version = _version(session, admin, "T-L6-002")
    # From DRAFT there is no direct transition to REVIEW.
    with pytest.raises(InvalidLifecycleTransitionError):
        LifecycleService(session).submit_for_review(version.id, engineer)


def test_engineer_cannot_approve(session, admin, engineer):
    version = _version(session, admin, "T-L6-003")
    lifecycle = LifecycleService(session)
    lifecycle.change_lifecycle(version.id, "IN_WORK", engineer)
    lifecycle.change_lifecycle(version.id, "REVIEW", engineer)
    with pytest.raises(AuthorizationError):
        lifecycle.approve(version.id, engineer)


def test_engineer_cannot_release(session, admin, engineer, reviewer, plm_manager):
    version = _version(session, admin, "T-L6-004")
    lifecycle = LifecycleService(session)
    lifecycle.change_lifecycle(version.id, "IN_WORK", engineer)
    lifecycle.change_lifecycle(version.id, "REVIEW", engineer)
    lifecycle.approve(version.id, reviewer)
    with pytest.raises(AuthorizationError):
        lifecycle.release(version.id, engineer)


def test_invalid_transition_rejected(session, admin):
    version = _version(session, admin, "T-L6-005")
    with pytest.raises(InvalidLifecycleTransitionError):
        LifecycleService(session).change_lifecycle(version.id, "RELEASED", admin)


def test_unknown_state_rejected(session, admin):
    version = _version(session, admin, "T-L6-006")
    with pytest.raises(NotFoundError):
        LifecycleService(session).change_lifecycle(version.id, "NOPE", admin)


def test_available_transitions_respect_roles(session, admin, engineer):
    version = _version(session, admin, "T-L6-007")
    lifecycle = LifecycleService(session)

    engineer_targets = {
        t.to_state.code for t in lifecycle.available_transitions(version.id, engineer)
    }
    assert engineer_targets == {"IN_WORK"}  # OBSOLETE requires PLM Manager

    admin_targets = {
        t.to_state.code for t in lifecycle.available_transitions(version.id, admin)
    }
    assert admin_targets == {"IN_WORK", "OBSOLETE"}

    assert lifecycle.can_transition(version.id, "IN_WORK", engineer) is True
    assert lifecycle.can_transition(version.id, "OBSOLETE", engineer) is False


def test_transition_emits_audit_event(session, admin, engineer):
    version = _version(session, admin, "T-L6-008")
    LifecycleService(session).change_lifecycle(version.id, "IN_WORK", engineer, "start")

    events = AuditEventService(session).query("ItemVersion", version.id)
    state_events = [e for e in events if e.event_type == EVENT_STATE_CHANGE]
    assert len(state_events) == 1
    assert state_events[0].from_value == "DRAFT"
    assert state_events[0].to_value == "IN_WORK"
    assert state_events[0].comment == "start"


def test_item_service_delegates_to_lifecycle(session, admin, engineer):
    version = _version(session, admin, "T-L6-009")
    ItemService(session).change_lifecycle(version.id, "IN_WORK", engineer)
    assert version.lifecycle_state.code == "IN_WORK"
    assert ItemService(session).can_transition(version.id, "REVIEW", engineer) is True
