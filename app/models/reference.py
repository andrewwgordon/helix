"""Reference and lookup entities (spec §6).

These tables make the platform configurable instead of hardcoding enums.
"""

from flask_appbuilder import Model
from flask_appbuilder.security.sqla.models import Role
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.mixins import AuditMixin


class ItemType(AuditMixin, Model):
    """Business object classification: Part, Document, Requirement, Product."""

    __tablename__ = "item_type"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False)
    name = Column(String(64), nullable=False)
    description = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("code", name="uq_item_type_code"),)

    def __repr__(self) -> str:
        return self.name


class LifecycleState(AuditMixin, Model):
    """A position in the item lifecycle workflow (spec §11)."""

    __tablename__ = "lifecycle_state"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False)
    name = Column(String(64), nullable=False)
    sequence = Column(Integer, nullable=False, default=0)
    is_terminal = Column(Boolean, nullable=False, default=False)
    is_releasable = Column(Boolean, nullable=False, default=False)
    description = Column(String(255))

    __table_args__ = (UniqueConstraint("code", name="uq_lifecycle_state_code"),)

    def __repr__(self) -> str:
        return self.name


class RelationshipType(AuditMixin, Model):
    """Directed relationship semantics (spec §6.3)."""

    __tablename__ = "relationship_type"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False)
    name = Column(String(64), nullable=False)
    is_structural = Column(Boolean, nullable=False, default=False)
    allows_quantity = Column(Boolean, nullable=False, default=False)
    allows_find_number = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("code", name="uq_relationship_type_code"),)

    def __repr__(self) -> str:
        return self.name


class LifecycleTransition(AuditMixin, Model):
    """Allowed lifecycle transition, optionally guarded by a role (spec §6.4)."""

    __tablename__ = "lifecycle_transition"

    id = Column(Integer, primary_key=True)
    from_state_id = Column(
        Integer, ForeignKey("lifecycle_state.id"), nullable=False
    )
    to_state_id = Column(Integer, ForeignKey("lifecycle_state.id"), nullable=False)
    required_role_id = Column(Integer, ForeignKey("ab_role.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    from_state = relationship("LifecycleState", foreign_keys=[from_state_id])
    to_state = relationship("LifecycleState", foreign_keys=[to_state_id])
    required_role = relationship(Role, foreign_keys=[required_role_id])

    __table_args__ = (
        UniqueConstraint(
            "from_state_id", "to_state_id", name="uq_lifecycle_transition_edge"
        ),
        CheckConstraint(
            "from_state_id <> to_state_id",
            name="ck_lifecycle_transition_distinct",
        ),
    )

    def __repr__(self) -> str:
        return f"{self.from_state} -> {self.to_state}"


class LookupMixin:
    """Shared shape for simple code/name lookup tables."""

    id = Column(Integer, primary_key=True)
    code = Column(String(32), nullable=False)
    name = Column(String(64), nullable=False)
    description = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return self.code


class UnitOfMeasure(LookupMixin, AuditMixin, Model):
    __tablename__ = "unit_of_measure"
    __table_args__ = (UniqueConstraint("code", name="uq_unit_of_measure_code"),)


class MakeBuyCode(LookupMixin, AuditMixin, Model):
    __tablename__ = "make_buy_code"
    __table_args__ = (UniqueConstraint("code", name="uq_make_buy_code_code"),)


class VerificationMethod(LookupMixin, AuditMixin, Model):
    __tablename__ = "verification_method"
    __table_args__ = (
        UniqueConstraint("code", name="uq_verification_method_code"),
    )


class PriorityCode(LookupMixin, AuditMixin, Model):
    __tablename__ = "priority_code"
    __table_args__ = (UniqueConstraint("code", name="uq_priority_code_code"),)


class ProductFamily(LookupMixin, AuditMixin, Model):
    __tablename__ = "product_family"
    __table_args__ = (UniqueConstraint("code", name="uq_product_family_code"),)


class Market(LookupMixin, AuditMixin, Model):
    __tablename__ = "market"
    __table_args__ = (UniqueConstraint("code", name="uq_market_code"),)
