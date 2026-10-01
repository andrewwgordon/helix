"""Phase 7: baseline service tests (spec §12 / §14.9).

Covers the phase acceptance criteria:

* recursive structure capture with parent linkage,
* only releasable versions may be captured,
* a frozen baseline rejects every mutation,
* ``list_members`` returns the full structure ordered by depth.
"""

import pytest

from app.models.baseline import Baseline
from app.services import (
    Actor,
    BaselineService,
    ItemService,
    LifecycleService,
    PartService,
    ProductService,
    RelationshipService,
)
from app.services.exceptions import (
    BaselineFrozenError,
    BaselineValidationError,
    ConflictError,
    NotFoundError,
)


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _release(session, version):
    """Advance a version to APPROVED (releasable) via the lifecycle service.

    Admin bypasses role guards, keeping the fixtures independent of the
    permission matrix.
    """
    lifecycle = LifecycleService(session)
    actor = _actor()
    lifecycle.change_lifecycle(version.id, "IN_WORK", actor)
    lifecycle.change_lifecycle(version.id, "REVIEW", actor)
    lifecycle.change_lifecycle(version.id, "APPROVED", actor)
    return version


def _build_releasable_structure(session, suffix):
    """Product -> Part -> Part, with every version releasable."""
    actor = _actor()
    product = ProductService(session).create_product(f"T-B7-PRD-{suffix}", actor)
    mid = PartService(session).create_part(
        f"T-B7-MID-{suffix}", actor, uom_code="EA"
    )
    leaf = PartService(session).create_part(
        f"T-B7-LEAF-{suffix}", actor, uom_code="EA"
    )

    relationships = RelationshipService(session)
    relationships.add_relationship(
        product.item_version_id,
        mid.item_version_id,
        "CONTAINS",
        actor,
        quantity=2,
        find_number="10",
    )
    relationships.add_relationship(
        mid.item_version_id, leaf.item_version_id, "CONTAINS", actor
    )

    for version in (product.item_version, mid.item_version, leaf.item_version):
        _release(session, version)
    return product, mid, leaf


def test_create_baseline_captures_full_structure(app):
    from app import db

    session = db.session
    actor = _actor()
    product, mid, leaf = _build_releasable_structure(session, "01")

    service = BaselineService(session)
    baseline = service.create_baseline(
        product.item_version_id, "BL-T7-0001", "First baseline", actor
    )

    assert baseline.status == "DRAFT"
    assert baseline.frozen_at is None

    members = service.list_members(baseline.id)
    assert [m.item_version_id for m in members][0] == product.item_version_id

    by_version = {m.item_version_id: m for m in members}
    root = by_version[product.item_version_id]
    mid_member = by_version[mid.item_version_id]
    leaf_member = by_version[leaf.item_version_id]

    assert root.parent_member_id is None
    assert mid_member.parent_member_id == root.id
    assert leaf_member.parent_member_id == mid_member.id
    assert float(mid_member.quantity) == 2.0
    assert mid_member.find_number == "10"


def test_non_releasable_descendant_rejected_and_rolled_back(app):
    from app import db

    session = db.session
    actor = _actor()
    product = ProductService(session).create_product("T-B7-NR-PRD", actor)
    leaf = PartService(session).create_part("T-B7-NR-LEAF", actor, uom_code="EA")
    RelationshipService(session).add_relationship(
        product.item_version_id, leaf.item_version_id, "CONTAINS", actor
    )
    # Root is releasable, the descendant is still DRAFT.
    _release(session, product.item_version)

    with pytest.raises(BaselineValidationError):
        BaselineService(session).create_baseline(
            product.item_version_id, "BL-T7-NR", "Invalid", actor
        )

    # create_baseline must roll the entire capture back.
    assert session.query(Baseline).filter_by(baseline_number="BL-T7-NR").count() == 0


def test_non_releasable_root_rejected(app):
    from app import db

    session = db.session
    actor = _actor()
    product = ProductService(session).create_product("T-B7-NRR-PRD", actor)

    with pytest.raises(BaselineValidationError):
        BaselineService(session).create_baseline(
            product.item_version_id, "BL-T7-NRR", "Invalid", actor
        )


def test_freeze_is_one_way_and_blocks_mutations(app):
    from app import db

    session = db.session
    actor = _actor()
    product, mid, _leaf = _build_releasable_structure(session, "02")
    service = BaselineService(session)
    baseline = service.create_baseline(
        product.item_version_id, "BL-T7-0002", "Frozen", actor
    )

    service.freeze_baseline(baseline.id, actor)
    assert baseline.status == "FROZEN"
    assert baseline.frozen_at is not None

    # Re-freezing is forbidden.
    with pytest.raises(BaselineFrozenError):
        service.freeze_baseline(baseline.id, actor)

    # Adding a member to a frozen baseline is forbidden.
    with pytest.raises(BaselineFrozenError):
        service.add_member(baseline.id, mid.item_version_id, actor)


def test_create_baseline_freeze_immediately(app):
    from app import db

    session = db.session
    actor = _actor()
    product, _mid, _leaf = _build_releasable_structure(session, "03")

    baseline = BaselineService(session).create_baseline(
        product.item_version_id,
        "BL-T7-0003",
        "Frozen at creation",
        actor,
        freeze_immediately=True,
    )
    assert baseline.status == "FROZEN"
    assert baseline.frozen_at is not None


def test_add_member_draft_and_duplicate_conflict(app):
    from app import db

    session = db.session
    actor = _actor()
    product, _mid, _leaf = _build_releasable_structure(session, "04")
    extra = PartService(session).create_part("T-B7-EXTRA", actor, uom_code="EA")
    _release(session, extra.item_version)

    service = BaselineService(session)
    baseline = service.create_baseline(
        product.item_version_id, "BL-T7-0004", "Draft", actor
    )

    member = service.add_member(baseline.id, extra.item_version_id, actor)
    assert member.parent_member_id is None

    with pytest.raises(ConflictError):
        service.add_member(baseline.id, extra.item_version_id, actor)

    assert extra.item_version_id in {
        m.item_version_id for m in service.list_members(baseline.id)
    }


def test_add_member_rejects_unknown_baseline(app):
    from app import db

    session = db.session
    with pytest.raises(NotFoundError):
        BaselineService(session).add_member(
            999999, 1, _actor()
        )


def test_compare_baselines_classifies_changes(app):
    from app import db

    session = db.session
    actor = _actor()

    product = ProductService(session).create_product("T-B7-CMP-PRD", actor)
    _release(session, product.item_version)

    items = ItemService(session)
    part_item = items.create_item("Part", "T-B7-CMP-PART", actor)
    rev_a = items.create_version(part_item.id, actor)
    rev_b = items.revise_item(part_item.id, "major", actor)
    _release(session, rev_a)
    _release(session, rev_b)

    service = BaselineService(session)
    baseline_a = service.create_baseline(
        product.item_version_id, "BL-T7-CMP-A", "A", actor
    )
    baseline_b = service.create_baseline(
        product.item_version_id, "BL-T7-CMP-B", "B", actor
    )
    service.add_member(baseline_a.id, rev_a.id, actor)
    service.add_member(baseline_b.id, rev_b.id, actor)

    diff = service.compare_baselines(baseline_a.id, baseline_b.id)

    assert diff.added == []
    assert diff.removed == []
    assert len(diff.changed) == 1
    assert diff.changed[0][0].item_version_id == rev_a.id
    assert diff.changed[0][1].item_version_id == rev_b.id
    assert len(diff.unchanged) == 1  # the product root


def test_duplicate_baseline_number_rejected(app):
    from app import db

    session = db.session
    actor = _actor()
    product, _mid, _leaf = _build_releasable_structure(session, "05")
    service = BaselineService(session)
    service.create_baseline(product.item_version_id, "BL-T7-DUP", "One", actor)

    with pytest.raises(ConflictError):
        service.create_baseline(
            product.item_version_id, "BL-T7-DUP", "Two", actor
        )
