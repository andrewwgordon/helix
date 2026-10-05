"""Idempotent seed data (spec §22).

Reference data is upserted by ``code`` so seeding can run on every start.
Roles are created through the FAB security manager when one is supplied.
"""

from app.models.reference import (
    ItemType,
    LifecycleState,
    LifecycleTransition,
    MakeBuyCode,
    Market,
    PriorityCode,
    ProductFamily,
    RelationshipType,
    UnitOfMeasure,
    VerificationMethod,
)

ROLE_NAMES = ["Admin", "PLM Manager", "Engineer", "Reviewer", "Viewer"]

ITEM_TYPES = [
    ("Part", "Part"),
    ("Document", "Document"),
    ("Requirement", "Requirement"),
    ("Product", "Product"),
    ("Function", "Function"),
]

LIFECYCLE_STATES = [
    # code, name, sequence, is_terminal, is_releasable
    ("DRAFT", "Draft", 0, False, False),
    ("IN_WORK", "In Work", 1, False, False),
    ("REVIEW", "Review", 2, False, False),
    ("APPROVED", "Approved", 3, False, True),
    ("RELEASED", "Released", 4, True, True),
    ("OBSOLETE", "Obsolete", 5, True, False),
]

RELATIONSHIP_TYPES = [
    # code, name, is_structural, allows_quantity, allows_find_number
    ("CONTAINS", "Contains", True, True, True),
    ("REFERENCES", "References", False, False, False),
    ("SATISFIES", "Satisfies", False, False, False),
    ("DERIVED_FROM", "Derived From", False, False, False),
    ("RELATED_TO", "Related To", False, False, False),
    # Functional breakdown: a product performs functions, a function breaks
    # down into child functions via CONTAINS, and a part fulfils functions.
    ("PERFORMS", "Performs", False, False, False),
    ("FULFILLS", "Fulfills", False, False, False),
]

# from_code, to_code, required_role_name
LIFECYCLE_TRANSITIONS = [
    ("DRAFT", "IN_WORK", "Engineer"),
    ("IN_WORK", "REVIEW", "Engineer"),
    ("REVIEW", "IN_WORK", "Reviewer"),
    ("REVIEW", "APPROVED", "Reviewer"),
    ("APPROVED", "REVIEW", "Reviewer"),
    ("APPROVED", "RELEASED", "PLM Manager"),
    ("RELEASED", "OBSOLETE", "PLM Manager"),
    ("DRAFT", "OBSOLETE", "PLM Manager"),
]

UNIT_OF_MEASURE = [
    ("EA", "Each"),
    ("MM", "Millimetre"),
    ("M", "Metre"),
    ("KG", "Kilogram"),
    ("G", "Gram"),
    ("L", "Litre"),
    ("ML", "Millilitre"),
    ("SET", "Set"),
]

MAKE_BUY = [
    ("MAKE", "Make"),
    ("BUY", "Buy"),
    ("MAKE_OR_BUY", "Make or Buy"),
]

VERIFICATION_METHODS = [
    ("TEST", "Test"),
    ("ANALYSIS", "Analysis"),
    ("INSPECTION", "Inspection"),
    ("DEMONSTRATION", "Demonstration"),
]

PRIORITY_CODES = [
    ("MANDATORY", "Mandatory"),
    ("HIGH", "High"),
    ("MEDIUM", "Medium"),
    ("LOW", "Low"),
]

PRODUCT_FAMILIES = [("GENERAL", "General")]

MARKETS = [("GENERAL", "General")]


def _upsert(session, model, code, **fields):
    obj = session.query(model).filter_by(code=code).first()
    if obj is None:
        obj = model(code=code, **fields)
        session.add(obj)
    else:
        for key, value in fields.items():
            setattr(obj, key, value)
    return obj


def seed_roles(sm) -> None:
    """Create the application roles if they do not already exist."""
    for name in ROLE_NAMES:
        if sm.find_role(name) is None:
            sm.add_role(name)


def seed_reference(session) -> None:
    for code, name in ITEM_TYPES:
        _upsert(session, ItemType, code, name=name)

    for code, name, sequence, terminal, releasable in LIFECYCLE_STATES:
        _upsert(
            session,
            LifecycleState,
            code,
            name=name,
            sequence=sequence,
            is_terminal=terminal,
            is_releasable=releasable,
        )

    for code, name, structural, qty, find in RELATIONSHIP_TYPES:
        _upsert(
            session,
            RelationshipType,
            code,
            name=name,
            is_structural=structural,
            allows_quantity=qty,
            allows_find_number=find,
        )

    for code, name in UNIT_OF_MEASURE:
        _upsert(session, UnitOfMeasure, code, name=name)
    for code, name in MAKE_BUY:
        _upsert(session, MakeBuyCode, code, name=name)
    for code, name in VERIFICATION_METHODS:
        _upsert(session, VerificationMethod, code, name=name)
    for code, name in PRIORITY_CODES:
        _upsert(session, PriorityCode, code, name=name)
    for code, name in PRODUCT_FAMILIES:
        _upsert(session, ProductFamily, code, name=name)
    for code, name in MARKETS:
        _upsert(session, Market, code, name=name)

    session.flush()


def seed_transitions(session) -> None:
    states = {s.code: s for s in session.query(LifecycleState).all()}
    roles = _role_map(session)

    for from_code, to_code, role_name in LIFECYCLE_TRANSITIONS:
        from_state = states.get(from_code)
        to_state = states.get(to_code)
        if from_state is None or to_state is None:
            continue
        role = roles.get(role_name)
        existing = (
            session.query(LifecycleTransition)
            .filter_by(from_state_id=from_state.id, to_state_id=to_state.id)
            .first()
        )
        if existing is None:
            session.add(
                LifecycleTransition(
                    from_state_id=from_state.id,
                    to_state_id=to_state.id,
                    required_role_id=getattr(role, "id", None),
                )
            )
        else:
            existing.required_role_id = getattr(role, "id", None)
            existing.is_active = True

    session.flush()


def _role_map(session) -> dict:
    from flask_appbuilder.security.sqla.models import Role

    return {role.name: role for role in session.query(Role).all()}


def seed_all(session, sm=None) -> None:
    """Seed roles (if a security manager is given) and all reference data."""
    if sm is not None:
        seed_roles(sm)
    seed_reference(session)
    seed_transitions(session)
    session.commit()
