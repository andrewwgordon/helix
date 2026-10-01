"""Business-object service tests (spec §8 / §14.3–§14.6)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.business import Part
from app.models.core import Item
from app.services import PartService, ProductService, RequirementService
from app.services.exceptions import NotFoundError


def test_create_part(session, admin):
    part = PartService(session).create_part(
        "T-P2-001", admin, uom_code="EA", make_buy="MAKE", weight=2.5, material="Steel"
    )
    assert part.item_version.item.item_number == "T-P2-001"
    assert part.item_version.revision_label == "A"
    assert part.unit_of_measure.code == "EA"
    assert part.make_buy_code.code == "MAKE"
    assert float(part.weight) == 2.5
    assert part.material == "Steel"


def test_revise_part_clones_and_overrides(session, admin):
    svc = PartService(session)
    part = svc.create_part("T-P2-002", admin, uom_code="EA", material="Steel")
    revised = svc.revise_part(part.item_version.item_id, "major", admin, material="Brass")

    assert revised.item_version.revision_label == "B"
    assert revised.material == "Brass"
    # Non-overridden columns are cloned.
    assert revised.unit_of_measure_id == part.unit_of_measure_id


def test_create_part_unknown_uom_leaves_no_item(session, admin):
    with pytest.raises(NotFoundError):
        PartService(session).create_part("T-P2-003", admin, uom_code="NOPE")
    assert session.query(Item).filter_by(item_number="T-P2-003").first() is None


def test_create_part_negative_weight_rolls_back(session, admin):
    with pytest.raises(IntegrityError):
        PartService(session).create_part(
            "T-P2-004", admin, uom_code="EA", weight=-1
        )
    session.rollback()
    assert session.query(Item).filter_by(item_number="T-P2-004").first() is None


def test_create_product(session, admin):
    product = ProductService(session).create_product(
        "T-P2-PRD", admin, platform="X1", product_family="GENERAL"
    )
    assert product.item_version.item.item_number == "T-P2-PRD"
    assert product.platform == "X1"
    assert product.product_family.code == "GENERAL"


def test_revise_product(session, admin):
    svc = ProductService(session)
    product = svc.create_product("T-P2-PRD2", admin, platform="X1")
    revised = svc.revise_product(
        product.item_version.item_id, "minor", admin, platform="X2"
    )
    assert revised.item_version.revision_label == "A.1"
    assert revised.platform == "X2"


def test_create_requirement(session, admin):
    requirement = RequirementService(session).create_requirement(
        "T-P2-REQ",
        admin,
        requirement_text="The widget shall be red.",
        verification_method="TEST",
        priority="HIGH",
    )
    assert requirement.item_version.item.item_number == "T-P2-REQ"
    assert requirement.requirement_text == "The widget shall be red."
    assert requirement.verification_method.code == "TEST"
    assert requirement.priority_code.code == "HIGH"


def test_revise_requirement_clones_and_overrides(session, admin):
    svc = RequirementService(session)
    requirement = svc.create_requirement(
        "T-P2-REQ2",
        admin,
        requirement_text="The widget shall be red.",
        priority="LOW",
    )

    revised = svc.revise_requirement(
        requirement.item_version.item_id,
        "minor",
        admin,
        requirement_text="The widget shall be blue.",
    )

    assert revised.item_version.revision_label == "A.1"
    assert revised.requirement_text == "The widget shall be blue."
    # Non-overridden columns are cloned.
    assert revised.priority_code_id == requirement.priority_code_id


def test_deleting_version_cascades_to_subtype(session, admin):
    part = PartService(session).create_part("T-P2-CAS", admin, uom_code="EA")
    version_id = part.item_version_id

    session.delete(part.item_version)
    session.commit()

    assert session.get(Part, version_id) is None
