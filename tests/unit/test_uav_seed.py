"""HoverX-4 UAV demonstration seed tests.

Verifies that the seed ports the requirements dataset faithfully and adds the
product, revisions, three-level part structure, documents and baseline.
"""

import pytest

from app import db
from app.models.baseline import Baseline
from app.models.business import Document, Part, Product, Requirement
from app.models.core import Item, ItemVersion
from app.services import RelationshipService
from app.uav_seed import (
    ALL_ITEM_NUMBERS,
    BASELINE_NUMBER,
    PRODUCT_NUMBER,
    seed_uav,
    teardown_uav,
)


@pytest.fixture(scope="module")
def uav(app):
    with app.app_context():
        summary = seed_uav(db.session, app.appbuilder.sm)
        yield summary
        teardown_uav(db.session, app.config.get("UPLOAD_FOLDER"))


def _node_by_number(tree, number):
    """Find a node in a build_tree result by item number."""
    if tree["version"].item.item_number == number:
        return tree
    for child in tree["children"]:
        found = _node_by_number(child, number)
        if found is not None:
            return found
    return None


def _tree_depth(node):
    if not node["children"]:
        return 0
    return 1 + max(_tree_depth(child) for child in node["children"])


def test_dataset_counts(uav):
    assert uav["created"] is True
    assert uav["requirements"] == 27
    assert uav["parts"] == 32
    assert uav["documents"] == 6
    assert uav["product_versions"] == 2

    assert db.session.query(Product).count() >= 1
    assert db.session.query(Requirement).count() >= 27
    assert db.session.query(Part).count() >= 32
    assert db.session.query(Document).count() >= 6


def test_product_has_two_revisions(uav):
    item = db.session.query(Item).filter_by(item_number=PRODUCT_NUMBER).one()
    versions = sorted(item.versions, key=lambda v: v.version_sequence)
    assert [v.revision_label for v in versions] == ["A", "B"]
    assert item.current_version_id == versions[1].id
    assert versions[0].lifecycle_state.code == "APPROVED"
    assert versions[1].lifecycle_state.code == "RELEASED"


def test_three_level_product_breakdown(uav):
    item = db.session.query(Item).filter_by(item_number=PRODUCT_NUMBER).one()
    tree = RelationshipService(db.session).build_tree(
        item.current_version_id, direction="down"
    )

    assert _tree_depth(tree) == 3
    assert len(tree["children"]) == 6  # six top-level assemblies

    # Product -> Propulsion System -> Motor -> Stator Assembly (3 part levels).
    level_1 = _node_by_number(tree, "ASM-PROP")
    assert level_1 is not None
    level_2 = _node_by_number(level_1, "PRT-MOTOR")
    assert level_2 is not None
    level_3 = _node_by_number(level_2, "PRT-MOTOR-STAT")
    assert level_3 is not None
    assert float(level_2["relationship"].quantity) == 4.0
    assert level_2["relationship"].find_number == "10"

    # A second three-level path through the airframe.
    assert _node_by_number(tree, "PRT-ARM-TUBE") is not None


def test_requirements_preserved_with_trace_links(uav):
    numbers = {row[0] for row in db.session.query(Item.item_number)}
    for expected in ("SR-001", "SYS-004", "SW-003", "TC-004", "RSK-002", "D-001"):
        assert expected in numbers

    sys_001 = db.session.query(Item).filter_by(item_number="SYS-001").one()
    downstream = RelationshipService(db.session).get_downstream(
        sys_001.current_version_id, relationship_type="SATISFIES"
    )
    assert "SR-001" in {v.item.item_number for v in downstream}

    # Priority + lifecycle mapping survived the port.
    sr_004 = (
        db.session.query(Requirement)
        .join(ItemVersion, Requirement.item_version_id == ItemVersion.id)
        .join(Item, ItemVersion.item_id == Item.id)
        .filter(Item.item_number == "SR-004")
        .one()
    )
    assert sr_004.priority_code.code == "MANDATORY"
    assert sr_004.item_version.lifecycle_state.code == "RELEASED"

    sys_003 = (
        db.session.query(Requirement)
        .join(ItemVersion, Requirement.item_version_id == ItemVersion.id)
        .join(Item, ItemVersion.item_id == Item.id)
        .filter(Item.item_number == "SYS-003")
        .one()
    )
    assert sys_003.item_version.lifecycle_state.code == "DRAFT"


def test_documents_are_managed_files(uav):
    for number in ("DOC-SRS", "DOC-BOM"):
        document = (
            db.session.query(Document)
            .join(ItemVersion, Document.item_version_id == ItemVersion.id)
            .join(Item, ItemVersion.item_id == Item.id)
            .filter(Item.item_number == number)
            .one()
        )
        assert document.file_path
        assert document.checksum_sha256
        assert document.file_size > 0


def test_frozen_baseline_captures_structure(uav):
    baseline = (
        db.session.query(Baseline)
        .filter_by(baseline_number=BASELINE_NUMBER)
        .one()
    )
    assert baseline.status == "FROZEN"
    assert baseline.frozen_at is not None
    # Product + 32 parts.
    assert len(baseline.members) == 33


def test_seed_is_idempotent(uav):
    before = db.session.query(Item).filter(Item.item_number.in_(ALL_ITEM_NUMBERS)).count()
    second = seed_uav(db.session, None)
    assert second["created"] is False
    after = db.session.query(Item).filter(Item.item_number.in_(ALL_ITEM_NUMBERS)).count()
    assert before == after


def test_teardown_removes_only_seeded_data(uav):
    # Tear down and re-seed so the module-scoped fixture teardown stays valid.
    removed = teardown_uav(db.session, None)
    assert removed["removed"] is True
    assert (
        db.session.query(Item)
        .filter(Item.item_number.in_(ALL_ITEM_NUMBERS))
        .count()
        == 0
    )
    assert (
        db.session.query(Baseline)
        .filter_by(baseline_number=BASELINE_NUMBER)
        .count()
        == 0
    )
    seed_uav(db.session, None)
