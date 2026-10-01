"""HoverX-4 quadcopter UAV demonstration seed for Helix PLM.

This ports the requirements dataset from the HoverX-4 requirements-management
seed (``tmp/seed.py``) into the PLM domain model and extends it with a full
product breakdown:

* one **Product** (``PRD-HX4``) with two revisions (Rev A prototype, Rev B
  released configuration);
* a three-level **Part** structure rooted at the product version
  (assemblies -> sub-assemblies/parts -> sub-parts);
* managed **Documents** (SRS, ICD, test plan, user manual, safety analysis,
  BOM report);
* every original **Requirement** (stakeholder/system/software/use case/
  feature/user story/risk/test case/defect) with its trace links preserved;
* a frozen **Baseline** captured over the released product configuration.

All writes go through the domain services, so lifecycle transitions,
immutability, audit events and structure cycle checks are exercised exactly as
they are from the UI/API.

Usage::

    flask seed-uav       # idempotent — no-op if PRD-HX4 already exists
    flask teardown-uav   # removes only the data this seed created
"""

from datetime import date
from io import BytesIO

from werkzeug.datastructures import FileStorage

from app.models.audit import AuditEvent
from app.models.baseline import Baseline, BaselineMember
from app.models.business import Document
from app.models.core import Item, ItemRelationship, ItemVersion
from app.models.reference import RelationshipType
from app.seed import seed_all
from app.services import (
    Actor,
    BaselineService,
    DocumentService,
    LifecycleService,
    PartService,
    ProductService,
    RelationshipService,
    RequirementService,
)

PRODUCT_NUMBER = "PRD-HX4"
PRODUCT_NAME = "HoverX-4 Quadcopter UAV"
BASELINE_NUMBER = "BL-HX4-001"

# Extra traceability relationship types on top of the PLM default set
# (CONTAINS, REFERENCES, SATISFIES, DERIVED_FROM, RELATED_TO).
EXTRA_RELATIONSHIP_TYPES = [
    ("REFINES", "Refines"),
    ("ELABORATES", "Elaborates"),
    ("IMPLEMENTS", "Implements"),
    ("VERIFIES", "Verifies"),
    ("MITIGATES", "Mitigates"),
    ("DEPENDS_ON", "Depends On"),
]

# Lifecycle path used to drive versions to their seeded state.
_LIFECYCLE_PATH = ["DRAFT", "IN_WORK", "REVIEW", "APPROVED", "RELEASED"]

# ---------------------------------------------------------------------------
# Requirements (item_number, kind, title, text, lifecycle, priority, verify)
# ---------------------------------------------------------------------------
REQUIREMENTS = [
    (
        "SR-001", "Stakeholder Requirement", "Safe operation BVLOS",
        "The UAV shall support safe flight beyond visual line of sight, "
        "including fail-safe behaviour on loss of the control link.",
        "APPROVED", "HIGH", None,
    ),
    (
        "SR-002", "Stakeholder Requirement", "Payload of at least 1 kg",
        "The UAV shall carry a 1 kg inspection camera payload.",
        "APPROVED", "MEDIUM", None,
    ),
    (
        "SR-003", "Stakeholder Requirement", "Endurance of at least 30 minutes",
        "The UAV shall remain airborne for at least 30 minutes of hover.",
        "APPROVED", "HIGH", None,
    ),
    (
        "SR-004", "Stakeholder Requirement", "Autonomous return-to-home",
        "The UAV shall automatically return to home on low battery.",
        "RELEASED", "MANDATORY", None,
    ),
    (
        "SR-005", "Stakeholder Requirement", "Handheld controller, 5 km range",
        "The operator shall control the UAV from a handheld console at up to 5 km.",
        "IN_WORK", "MEDIUM", None,
    ),
    (
        "SYS-001", "System Requirement", "Wind stability to 12 m/s",
        "The vehicle shall maintain attitude stability in winds up to 12 m/s.",
        "IN_WORK", "HIGH", "TEST",
    ),
    (
        "SYS-002", "System Requirement", "Power for 30 minutes hover",
        "The power system shall sustain 30 minutes of hover at 1 kg payload.",
        "IN_WORK", "HIGH", "TEST",
    ),
    (
        "SYS-003", "System Requirement", "Redundant flight controller",
        "The vehicle shall continue controlled flight after a primary "
        "flight-controller failure.",
        "DRAFT", "MANDATORY", "ANALYSIS",
    ),
    (
        "SYS-004", "System Requirement", "Autonomous return-to-home",
        "The vehicle shall return to the home point within 2 m accuracy.",
        "IN_WORK", "MANDATORY", "TEST",
    ),
    (
        "SYS-005", "System Requirement", "Weight budget 2 kg",
        "Total take-off weight shall not exceed 2 kg including payload.",
        "APPROVED", "MEDIUM", "ANALYSIS",
    ),
    (
        "SW-001", "Software Requirement", "400 Hz attitude loop",
        "The flight stack shall run the attitude loop at 400 Hz.",
        "IN_WORK", "HIGH", "TEST",
    ),
    (
        "SW-002", "Software Requirement", "Low-battery alert at 20 % SOC",
        "The battery monitor shall alert at 20 % state of charge.",
        "IN_WORK", "HIGH", "TEST",
    ),
    (
        "SW-003", "Software Requirement", "Telemetry within 500 ms",
        "The ground-control app shall show telemetry within 500 ms.",
        "IN_WORK", "MEDIUM", "TEST",
    ),
    (
        "SW-004", "Software Requirement", "RTH guidance to 2 m",
        "The RTH routine shall guide the vehicle to home within 2 m.",
        "IN_WORK", "MANDATORY", "TEST",
    ),
    (
        "UC-002", "Use Case", "Autonomous return on low battery",
        "Actor: UAV manager. The vehicle detects low battery, enters auto-return "
        "and lands at the home point.",
        "IN_WORK", "MANDATORY", None,
    ),
    (
        "F-001", "Feature", "Autonomous flight-modes package",
        "Attitude hold, orbit, waypoint and RTH flight modes.",
        "DRAFT", "MEDIUM", None,
    ),
    (
        "US-001", "User Story", "Fail-safe return-to-home",
        "As a ground operator, I want a fail-safe RTH so that I avoid flyaways.",
        "APPROVED", "MANDATORY", None,
    ),
    (
        "US-002", "User Story", "Live battery telemetry",
        "As a pilot, I want live battery telemetry so that I can land safely.",
        "IN_WORK", "MEDIUM", None,
    ),
    (
        "RSK-002", "Risk", "Battery thermal runaway",
        "A cell failure may propagate to thermal runaway in flight.",
        "APPROVED", "MANDATORY", None,
    ),
    (
        "RSK-003", "Risk", "Loss of RC link / flyaway",
        "Loss of the RC link may leave the vehicle uncontrolled.",
        "APPROVED", "MANDATORY", None,
    ),
    (
        "TC-001", "Test Case", "Hover stability in 12 m/s wind",
        "Execute 10-minute hover in a 12 m/s wind and verify attitude < 5 deg.",
        "APPROVED", "HIGH", "TEST",
    ),
    (
        "TC-002", "Test Case", "30-minute hover endurance",
        "Hover with a 1 kg payload until battery low; verify 30 minutes.",
        "APPROVED", "HIGH", "TEST",
    ),
    (
        "TC-003", "Test Case", "Low-battery RTH completion",
        "Drain battery to 20 % SOC; verify automatic return and 2 m landing.",
        "IN_WORK", "MANDATORY", "TEST",
    ),
    (
        "TC-004", "Test Case", "Telemetry latency under 500 ms",
        "Measure end-to-end telemetry latency over the 5 km link under maximum "
        "ground-station load; expect < 500 ms.",
        "IN_WORK", "MEDIUM", "TEST",
    ),
    (
        "D-001", "Defect", "GCS telemetry stutters under load",
        "Telemetry frames drop when the ground station is under heavy load.",
        "IN_WORK", "MEDIUM", None,
    ),
    (
        "F-002", "Feature", "Quick-release payload platform",
        "Tool-free payload swap platform (not yet traced).",
        "DRAFT", "MEDIUM", None,
    ),
    (
        "D-002", "Defect", "Intermittent compass calibration drift",
        "Occasional calibration drift reported in field trials (not yet traced).",
        "DRAFT", "MEDIUM", None,
    ),
]

# Second-generation edits from the source dataset: number -> new requirement text.
REQUIREMENT_REVISIONS = {
    "SR-001": (
        "major",
        "The UAV shall support safe flight beyond visual line of sight, including "
        "fail-safe behaviour on loss of the control link.",
    ),
    "SYS-002": (
        "minor",
        "The power system shall sustain 30 minutes of hover at 1 kg payload.",
    ),
    "TC-004": (
        "minor",
        "Measure end-to-end telemetry latency over the 5 km link under maximum "
        "ground-station load; expect < 500 ms.",
    ),
    "SW-002": (
        "minor",
        "The battery monitor shall alert at 20 % state of charge.",
    ),
}

# ---------------------------------------------------------------------------
# Parts: (item_number, name, uom, make_buy, weight_kg, material)
# ---------------------------------------------------------------------------
PARTS = [
    ("ASM-AIRFRAME", "Airframe Assembly", "EA", "MAKE", 0.55, "Carbon Fibre"),
    ("ASM-PROP", "Propulsion System", "EA", "MAKE", 0.60, None),
    ("ASM-POWER", "Power System", "EA", "MAKE", 0.75, None),
    ("ASM-FCS", "Flight Control System", "EA", "MAKE", 0.12, None),
    ("ASM-GCS", "Ground Control Station", "EA", "MAKE", 0.50, None),
    ("ASM-PAYLOAD", "Payload System", "EA", "MAKE", 0.35, None),
    ("PRT-FRAME", "Carbon Frame", "EA", "MAKE", 0.35, "CFRP"),
    ("PRT-ARMS", "Folding Arm Set", "SET", "MAKE", 0.15, "Carbon Fibre"),
    ("PRT-LANDING", "Landing Gear", "SET", "MAKE", 0.05, "Nylon"),
    ("PRT-ARM-TUBE", "Arm Tube", "EA", "BUY", 0.05, "Carbon Fibre"),
    ("PRT-ARM-HINGE", "Arm Hinge", "EA", "BUY", 0.02, "Aluminium"),
    ("PRT-MOTOR", "Brushless Motor", "EA", "BUY", 0.08, "Aluminium"),
    ("PRT-ESC", "Electronic Speed Controller", "EA", "BUY", 0.03, None),
    ("PRT-PROP", "Propeller", "EA", "BUY", 0.02, "Composite"),
    ("PRT-MOTOR-STAT", "Motor Stator Assembly", "EA", "BUY", 0.04, "Steel"),
    ("PRT-MOTOR-ROT", "Motor Rotor Bell", "EA", "BUY", 0.02, "Aluminium"),
    ("PRT-MOTOR-BRG", "Motor Bearing", "EA", "BUY", 0.005, "Steel"),
    ("PRT-PROP-BLADE", "Propeller Blade", "EA", "BUY", 0.008, "Composite"),
    ("PRT-PROP-HUB", "Propeller Hub", "EA", "BUY", 0.01, "Aluminium"),
    ("PRT-BATT", "Li-ion Battery Pack", "EA", "BUY", 0.55, None),
    ("PRT-PDB", "Power Distribution Board", "EA", "MAKE", 0.06, "Copper/FR4"),
    ("PRT-BATT-CELL", "Li-ion Cell", "EA", "BUY", 0.045, "Li-ion"),
    ("PRT-BATT-BMS", "Battery Management Board", "EA", "BUY", 0.05, None),
    ("PRT-FC", "Flight Controller", "EA", "BUY", 0.045, None),
    ("PRT-IMU", "IMU Module", "EA", "BUY", 0.01, None),
    ("PRT-BARO", "Barometer Module", "EA", "BUY", 0.005, None),
    ("PRT-RC", "RC Receiver", "EA", "BUY", 0.015, None),
    ("PRT-HHC", "Handheld Controller", "EA", "BUY", 0.40, None),
    ("PRT-ANT", "Telemetry Antenna", "EA", "BUY", 0.02, None),
    ("PRT-TEL", "Telemetry Radio", "EA", "BUY", 0.03, None),
    ("PRT-GIMBAL", "Camera Gimbal", "EA", "BUY", 0.18, "Aluminium"),
    ("PRT-CAM", "Inspection Camera", "EA", "BUY", 0.12, None),
]

# Product structure edges: (parent, child, quantity, find_number)
BOM = [
    (PRODUCT_NUMBER, "ASM-AIRFRAME", 1, "10"),
    (PRODUCT_NUMBER, "ASM-PROP", 1, "20"),
    (PRODUCT_NUMBER, "ASM-POWER", 1, "30"),
    (PRODUCT_NUMBER, "ASM-FCS", 1, "40"),
    (PRODUCT_NUMBER, "ASM-GCS", 1, "50"),
    (PRODUCT_NUMBER, "ASM-PAYLOAD", 1, "60"),
    # Level 2 under the airframe.
    ("ASM-AIRFRAME", "PRT-FRAME", 1, "10"),
    ("ASM-AIRFRAME", "PRT-ARMS", 4, "20"),
    ("ASM-AIRFRAME", "PRT-LANDING", 1, "30"),
    # Level 3 under the arm set.
    ("PRT-ARMS", "PRT-ARM-TUBE", 4, "10"),
    ("PRT-ARMS", "PRT-ARM-HINGE", 4, "20"),
    # Propulsion.
    ("ASM-PROP", "PRT-MOTOR", 4, "10"),
    ("ASM-PROP", "PRT-ESC", 4, "20"),
    ("ASM-PROP", "PRT-PROP", 4, "30"),
    ("PRT-MOTOR", "PRT-MOTOR-STAT", 1, "10"),
    ("PRT-MOTOR", "PRT-MOTOR-ROT", 1, "20"),
    ("PRT-MOTOR", "PRT-MOTOR-BRG", 2, "30"),
    ("PRT-PROP", "PRT-PROP-BLADE", 2, "10"),
    ("PRT-PROP", "PRT-PROP-HUB", 1, "20"),
    # Power.
    ("ASM-POWER", "PRT-BATT", 1, "10"),
    ("ASM-POWER", "PRT-PDB", 1, "20"),
    ("PRT-BATT", "PRT-BATT-CELL", 6, "10"),
    ("PRT-BATT", "PRT-BATT-BMS", 1, "20"),
    # Flight control.
    ("ASM-FCS", "PRT-FC", 1, "10"),
    ("ASM-FCS", "PRT-IMU", 1, "20"),
    ("ASM-FCS", "PRT-BARO", 1, "30"),
    ("ASM-FCS", "PRT-RC", 1, "40"),
    # Ground control station.
    ("ASM-GCS", "PRT-HHC", 1, "10"),
    ("ASM-GCS", "PRT-ANT", 2, "20"),
    ("ASM-GCS", "PRT-TEL", 1, "30"),
    # Payload.
    ("ASM-PAYLOAD", "PRT-GIMBAL", 1, "10"),
    ("ASM-PAYLOAD", "PRT-CAM", 1, "20"),
]

# Original requirement-to-requirement trace links: (source, target, type)
REQUIREMENT_LINKS = [
    ("SYS-001", "SR-001", "SATISFIES"),
    ("SYS-002", "SR-003", "SATISFIES"),
    ("SYS-004", "SR-004", "SATISFIES"),
    ("SYS-005", "SR-002", "SATISFIES"),
    ("SYS-003", "SR-001", "REFINES"),
    ("SW-001", "SYS-001", "IMPLEMENTS"),
    ("SW-002", "SYS-002", "IMPLEMENTS"),
    ("SW-004", "SYS-004", "IMPLEMENTS"),
    ("SW-003", "SR-005", "ELABORATES"),
    ("UC-002", "SYS-004", "ELABORATES"),
    ("F-001", "SYS-004", "ELABORATES"),
    ("US-001", "SYS-004", "REFINES"),
    ("US-002", "SW-003", "REFINES"),
    ("SW-002", "SW-001", "DEPENDS_ON"),
    ("SW-004", "SW-001", "DEPENDS_ON"),
    ("TC-001", "SYS-001", "VERIFIES"),
    ("TC-002", "SYS-002", "VERIFIES"),
    ("TC-003", "SYS-004", "VERIFIES"),
    ("TC-004", "SW-003", "VERIFIES"),
    ("SYS-002", "RSK-002", "MITIGATES"),
    ("SYS-004", "RSK-003", "MITIGATES"),
    ("D-001", "SW-003", "REFERENCES"),
]

# Part-to-requirement implementation links.
PART_LINKS = [
    ("ASM-PROP", "SYS-001", "IMPLEMENTS"),
    ("ASM-POWER", "SYS-002", "IMPLEMENTS"),
    ("ASM-FCS", "SYS-003", "IMPLEMENTS"),
    ("ASM-PAYLOAD", "SR-002", "IMPLEMENTS"),
    ("ASM-GCS", "SR-005", "IMPLEMENTS"),
    ("PRT-MOTOR", "SYS-002", "IMPLEMENTS"),
    ("PRT-PROP", "SYS-001", "IMPLEMENTS"),
    ("PRT-BATT", "SYS-002", "IMPLEMENTS"),
    ("PRT-PDB", "SYS-002", "IMPLEMENTS"),
    ("PRT-FC", "SYS-003", "IMPLEMENTS"),
    ("PRT-IMU", "SYS-003", "IMPLEMENTS"),
    ("PRT-RC", "SR-005", "IMPLEMENTS"),
    ("PRT-TEL", "SW-003", "IMPLEMENTS"),
    ("PRT-ANT", "SR-005", "IMPLEMENTS"),
    ("PRT-GIMBAL", "SR-002", "IMPLEMENTS"),
    ("PRT-CAM", "SR-002", "IMPLEMENTS"),
]

# Documents: (item_number, file_name, description, content)
DOCUMENTS = [
    (
        "DOC-SRS", "HX4-System-Requirements-Specification.txt",
        "System Requirements Specification",
        "HoverX-4 System Requirements Specification.\n"
        "Allocated stakeholder, system and software requirements.",
    ),
    (
        "DOC-ICD", "HX4-Interface-Control-Document.txt",
        "Interface Control Document",
        "HoverX-4 Interface Control Document. Power, data and RF interfaces.",
    ),
    (
        "DOC-TP", "HX4-Test-Plan.txt",
        "Verification Test Plan",
        "HoverX-4 verification test plan: wind stability, endurance, RTH, telemetry.",
    ),
    (
        "DOC-UM", "HX4-User-Manual.txt",
        "Operator User Manual",
        "HoverX-4 operator manual: pre-flight, mission, emergency procedures.",
    ),
    (
        "DOC-SA", "HX4-Safety-Analysis.txt",
        "Safety Analysis",
        "HoverX-4 safety analysis: battery thermal runaway and flyaway mitigation.",
    ),
    (
        "DOC-BOM", "HX4-Product-BOM.txt",
        "Product Bill of Materials",
        "HoverX-4 released bill of materials down to three assembly levels.",
    ),
]

# Document trace links: (document_number, target_number, type)
DOCUMENT_LINKS = [
    ("DOC-SRS", "SR-001", "REFERENCES"),
    ("DOC-SRS", "SYS-004", "REFERENCES"),
    ("DOC-ICD", "SYS-003", "REFERENCES"),
    ("DOC-TP", "TC-001", "REFERENCES"),
    ("DOC-TP", "TC-003", "REFERENCES"),
    ("DOC-UM", "SR-005", "REFERENCES"),
    ("DOC-SA", "RSK-002", "REFERENCES"),
    ("DOC-SA", "RSK-003", "REFERENCES"),
    ("DOC-BOM", "ASM-PROP", "REFERENCES"),
]

ALL_ITEM_NUMBERS = (
    [PRODUCT_NUMBER]
    + [p[0] for p in PARTS]
    + [d[0] for d in DOCUMENTS]
    + [r[0] for r in REQUIREMENTS]
)


def _upsert_relationship_types(session) -> None:
    for code, name in EXTRA_RELATIONSHIP_TYPES:
        existing = (
            session.query(RelationshipType).filter_by(code=code).first()
        )
        if existing is None:
            session.add(
                RelationshipType(
                    code=code,
                    name=name,
                    is_structural=False,
                    allows_quantity=False,
                    allows_find_number=False,
                    is_active=True,
                )
            )
        else:
            existing.name = name
            existing.is_active = True
    session.flush()


def _advance(session, actor, version, target_code: str) -> None:
    """Drive a version along the linear lifecycle path to ``target_code``."""
    lifecycle = LifecycleService(session, actor)
    current = session.get(ItemVersion, version.id).lifecycle_state.code
    if current == target_code:
        return
    if current not in _LIFECYCLE_PATH or target_code not in _LIFECYCLE_PATH:
        raise ValueError(f"Cannot advance lifecycle {current} -> {target_code}")
    start = _LIFECYCLE_PATH.index(current)
    end = _LIFECYCLE_PATH.index(target_code)
    for code in _LIFECYCLE_PATH[start + 1 : end + 1]:
        lifecycle.change_lifecycle(version.id, code, actor)


def _doc_file(file_name: str, content: str) -> FileStorage:
    return FileStorage(
        stream=BytesIO(content.encode("utf-8")),
        filename=file_name,
        content_type="text/plain",
    )


def seed_uav(session, sm=None, actor: Actor = None) -> dict:
    """Seed the HoverX-4 dataset. Idempotent by product item number.

    Returns a summary dict with ``created`` and the seeded record counts.
    """
    seed_all(session, sm)

    existing = (
        session.query(Item).filter_by(item_number=PRODUCT_NUMBER).first()
    )
    if existing is not None:
        return {"created": False, "product": PRODUCT_NUMBER}

    actor = actor or Actor(
        username="admin", roles=frozenset({"Admin"}), is_admin=True
    )

    _upsert_relationship_types(session)

    parts_svc = PartService(session, actor)
    products_svc = ProductService(session, actor)
    requirements_svc = RequirementService(session, actor)
    documents_svc = DocumentService(session, actor)
    relationships = RelationshipService(session, actor)

    # --- Product identity + first revision -------------------------------
    product = products_svc.create_product(
        PRODUCT_NUMBER,
        actor,
        description=PRODUCT_NAME,
        product_family="GENERAL",
        market="GENERAL",
        platform="HX4",
        release_target=date(2026, 6, 30),
    )

    # --- Parts -----------------------------------------------------------
    parts = {}
    for number, name, uom, make_buy, weight, material in PARTS:
        parts[number] = parts_svc.create_part(
            number,
            actor,
            uom_code=uom,
            make_buy=make_buy,
            weight=weight,
            material=material,
            description=name,
        )

    # --- Documents -------------------------------------------------------
    documents = {}
    for number, file_name, description, content in DOCUMENTS:
        documents[number] = documents_svc.create_document(
            number,
            actor,
            uploaded_file=_doc_file(file_name, content),
            description=description,
        )

    # --- Requirements ----------------------------------------------------
    requirements = {}
    for number, kind, title, text, _status, priority, verify in REQUIREMENTS:
        requirements[number] = requirements_svc.create_requirement(
            number,
            actor,
            requirement_text=text,
            verification_method=verify,
            priority=priority,
            description=f"{kind}: {title}",
        )

    # Second-generation edits (while still drafts, before trace links).
    for number, (change_type, text) in REQUIREMENT_REVISIONS.items():
        requirements[number] = requirements_svc.revise_requirement(
            requirements[number].item_version.item_id,
            change_type,
            actor,
            requirement_text=text,
        )

    # --- Product structure (three levels of parts) -----------------------
    def _version_id(number: str) -> int:
        if number in parts:
            return parts[number].item_version_id
        if number in requirements:
            return requirements[number].item_version_id
        if number in documents:
            return documents[number].item_version_id
        return product.item_version_id

    for parent, child, quantity, find_number in BOM:
        relationships.add_relationship(
            _version_id(parent),
            _version_id(child),
            "CONTAINS",
            actor,
            quantity=quantity,
            find_number=find_number,
        )

    # --- Trace links -----------------------------------------------------
    for source, target, rel_type in REQUIREMENT_LINKS:
        relationships.add_relationship(
            _version_id(source), _version_id(target), rel_type, actor
        )
    for source, target, rel_type in PART_LINKS:
        relationships.add_relationship(
            _version_id(source), _version_id(target), rel_type, actor
        )
    for source, target, rel_type in DOCUMENT_LINKS:
        relationships.add_relationship(
            _version_id(source), _version_id(target), rel_type, actor
        )

    # --- Product revision B (copies the structure + links) ---------------
    product_b = products_svc.revise_product(
        product.item_version.item_id, "major", actor, platform="HX4-B"
    )

    # --- Lifecycle: parts and documents releasable for the baseline ------
    for part in parts.values():
        _advance(session, actor, part.item_version, "APPROVED")
    for document in documents.values():
        _advance(session, actor, document.item_version, "APPROVED")

    # --- Lifecycle: requirements to their seeded states ------------------
    for number, _kind, _title, _text, status, _priority, _verify in REQUIREMENTS:
        _advance(session, actor, requirements[number].item_version, status)

    # --- Lifecycle: product versions -------------------------------------
    _advance(session, actor, product.item_version, "APPROVED")   # Rev A
    _advance(session, actor, product_b.item_version, "RELEASED")  # Rev B

    # --- Frozen baseline over the released product configuration ---------
    baseline = BaselineService(session, actor).create_baseline(
        product_b.item_version_id,
        BASELINE_NUMBER,
        "HX4 Initial Released Baseline",
        actor,
        description=(
            "Frozen release baseline for the HoverX-4 Rev B configuration, "
            "capturing the three-level product structure."
        ),
        freeze_immediately=True,
    )

    seeded_version_ids = _seeded_version_ids(session)
    summary = {
        "created": True,
        "product": PRODUCT_NUMBER,
        "product_versions": 2,
        "parts": len(parts),
        "documents": len(documents),
        "requirements": len(requirements),
        "relationships": session.query(ItemRelationship)
        .filter(
            ItemRelationship.source_item_version_id.in_(seeded_version_ids)
        )
        .count(),
        "baseline": baseline.baseline_number,
        "baseline_members": len(baseline.members),
    }
    return summary


def _seeded_version_ids(session) -> list:
    """Return every version id belonging to the seeded items."""
    seeded_items = (
        session.query(Item).filter(Item.item_number.in_(ALL_ITEM_NUMBERS)).all()
    )
    return [version.id for item in seeded_items for version in item.versions]


def teardown_uav(session, upload_folder: str = None) -> dict:
    """Remove the HoverX-4 dataset created by :func:`seed_uav`."""
    from app.services.storage import delete_stored

    items = (
        session.query(Item).filter(Item.item_number.in_(ALL_ITEM_NUMBERS)).all()
    )
    if not items:
        return {"removed": False}

    item_ids = [item.id for item in items]
    version_ids = [version.id for item in items for version in item.versions]

    baseline_ids = [
        row[0]
        for row in session.query(Baseline.id).filter(
            Baseline.product_version_id.in_(version_ids)
        )
    ]
    if baseline_ids:
        session.query(BaselineMember).filter(
            BaselineMember.baseline_id.in_(baseline_ids)
        ).delete(synchronize_session=False)
        session.query(Baseline).filter(
            Baseline.id.in_(baseline_ids)
        ).delete(synchronize_session=False)

    session.query(AuditEvent).filter(
        AuditEvent.item_id.in_(item_ids)
    ).delete(synchronize_session=False)
    session.query(ItemRelationship).filter(
        ItemRelationship.source_item_version_id.in_(version_ids)
        | ItemRelationship.target_item_version_id.in_(version_ids)
    ).delete(synchronize_session=False)

    if upload_folder:
        stored = [
            doc.file_path
            for doc in session.query(Document)
            .filter(Document.item_version_id.in_(version_ids))
            .all()
        ]
        for file_path in stored:
            delete_stored(file_path, upload_folder)

    session.query(ItemVersion).filter(
        ItemVersion.item_id.in_(item_ids)
    ).delete(synchronize_session=False)
    session.query(Item).filter(Item.id.in_(item_ids)).delete(
        synchronize_session=False
    )

    # Remove the extra trace types only when nothing else uses them.
    for code, _name in EXTRA_RELATIONSHIP_TYPES:
        rel_type = (
            session.query(RelationshipType).filter_by(code=code).first()
        )
        if rel_type is None:
            continue
        in_use = (
            session.query(ItemRelationship)
            .filter_by(relationship_type_id=rel_type.id)
            .count()
        )
        if not in_use:
            session.delete(rel_type)

    session.commit()
    return {"removed": True, "items": len(item_ids)}
