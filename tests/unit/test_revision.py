"""Revision label formatting (spec §10.2)."""

from app.services.item_service import format_revision


def test_initial_revision_is_a():
    assert format_revision(0, 0) == "A"


def test_major_revision_letters():
    assert format_revision(1, 0) == "B"
    assert format_revision(2, 0) == "C"
    assert format_revision(25, 0) == "Z"


def test_minor_revision_suffix():
    assert format_revision(0, 1) == "A.1"
    assert format_revision(1, 2) == "B.2"
    assert format_revision(0, 10) == "A.10"
