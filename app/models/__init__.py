"""PLM domain models.

Importing this package registers every model on FAB's shared declarative
metadata (``flask_appbuilder.models.sqla.Base``). Alembic and the app factory
rely on that side effect.
"""

from app.models.audit import AuditEvent
from app.models.baseline import Baseline, BaselineMember
from app.models.business import Document, Part, Product, Requirement
from app.models.core import Item, ItemRelationship, ItemVersion
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

__all__ = [
    "AuditEvent",
    "Baseline",
    "BaselineMember",
    "Document",
    "Item",
    "ItemRelationship",
    "ItemVersion",
    "ItemType",
    "LifecycleState",
    "LifecycleTransition",
    "MakeBuyCode",
    "Market",
    "Part",
    "PriorityCode",
    "Product",
    "ProductFamily",
    "RelationshipType",
    "Requirement",
    "UnitOfMeasure",
    "VerificationMethod",
]
