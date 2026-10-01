"""Item and revision service tests (spec §14.2)."""

import pytest

from app.services import ItemService
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InvalidLifecycleTransitionError,
    NotFoundError,
    ReleasedVersionImmutableError,
    ValidationError,
)


def _advance_to_released(session, version, engineer, reviewer, plm_manager):
    svc = ItemService(session)
    svc.change_lifecycle(version.id, "IN_WORK", engineer)
    svc.change_lifecycle(version.id, "REVIEW", engineer)
    svc.change_lifecycle(version.id, "APPROVED", reviewer)
    svc.change_lifecycle(version.id, "RELEASED", plm_manager)
    return version


def test_create_item_and_version(session, admin):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-ITEM-001", admin)
    version = svc.create_version(item.id, admin)

    assert item.item_number == "T-ITEM-001"
    assert version.version_sequence == 1
    assert version.revision_label == "A"
    assert version.lifecycle_state.code == "DRAFT"
    assert item.current_version_id == version.id


def test_duplicate_item_rejected(session, admin):
    svc = ItemService(session)
    svc.create_item("Part", "T-DUP-001", admin)
    with pytest.raises(ConflictError):
        svc.create_item("Part", "T-DUP-001", admin)


def test_unknown_item_type_rejected(session, admin):
    with pytest.raises(NotFoundError):
        ItemService(session).create_item("Nope", "T-X-001", admin)


def test_blank_item_number_rejected(session, admin):
    with pytest.raises(ValidationError):
        ItemService(session).create_item("Part", "  ", admin)


def test_revise_major_then_minor(session, admin):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-REV-001", admin)
    svc.create_version(item.id, admin)

    major = svc.revise_item(item.id, "major", admin)
    assert major.revision_label == "B"
    assert major.version_sequence == 2

    minor = svc.revise_item(item.id, "minor", admin)
    assert minor.revision_label == "B.1"
    assert minor.version_sequence == 3
    assert svc.get_current_version(item.id).id == minor.id


def test_revise_invalid_change_type(session, admin):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-REV-002", admin)
    svc.create_version(item.id, admin)
    with pytest.raises(ValidationError):
        svc.revise_item(item.id, "patch", admin)


def test_lifecycle_happy_path(session, admin, engineer, reviewer, plm_manager):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-LC-001", admin)
    version = svc.create_version(item.id, admin)

    _advance_to_released(session, version, engineer, reviewer, plm_manager)
    assert version.lifecycle_state.code == "RELEASED"


def test_invalid_transition_rejected(session, admin):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-LC-002", admin)
    version = svc.create_version(item.id, admin)
    with pytest.raises(InvalidLifecycleTransitionError):
        svc.change_lifecycle(version.id, "RELEASED", admin)


def test_role_guard_blocks_engineer_approval(session, admin, engineer, reviewer):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-LC-003", admin)
    version = svc.create_version(item.id, admin)
    svc.change_lifecycle(version.id, "IN_WORK", engineer)
    svc.change_lifecycle(version.id, "REVIEW", engineer)

    with pytest.raises(AuthorizationError):
        svc.change_lifecycle(version.id, "APPROVED", engineer)

    svc.change_lifecycle(version.id, "APPROVED", reviewer)
    assert version.lifecycle_state.code == "APPROVED"


def test_released_version_is_immutable(
    session, admin, engineer, reviewer, plm_manager
):
    svc = ItemService(session)
    item = svc.create_item("Part", "T-LC-004", admin)
    version = svc.create_version(item.id, admin)
    _advance_to_released(session, version, engineer, reviewer, plm_manager)

    with pytest.raises(ReleasedVersionImmutableError):
        svc.revise_item(item.id, "major", admin)
