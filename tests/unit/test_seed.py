"""Seed data tests (spec §22)."""

from app import db
from app.models.reference import (
    ItemType,
    LifecycleState,
    LifecycleTransition,
    RelationshipType,
    UnitOfMeasure,
)
from app.seed import seed_all


def test_expected_counts(app):
    session = db.session
    assert session.query(ItemType).count() >= 4
    assert session.query(LifecycleState).count() >= 6
    assert session.query(RelationshipType).count() >= 5
    assert session.query(LifecycleTransition).count() == 8
    assert session.query(UnitOfMeasure).count() >= 8


def test_seed_is_idempotent(app):
    session = db.session
    before = (
        session.query(ItemType).count(),
        session.query(LifecycleState).count(),
        session.query(RelationshipType).count(),
        session.query(LifecycleTransition).count(),
    )
    seed_all(session)
    after = (
        session.query(ItemType).count(),
        session.query(LifecycleState).count(),
        session.query(RelationshipType).count(),
        session.query(LifecycleTransition).count(),
    )
    assert before == after


def test_contains_is_structural_with_quantity(app):
    rel_type = (
        db.session.query(RelationshipType).filter_by(code="CONTAINS").one()
    )
    assert rel_type.is_structural is True
    assert rel_type.allows_quantity is True
    assert rel_type.allows_find_number is True
