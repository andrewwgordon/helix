"""Baseline configuration snapshots (spec §12).

A baseline captures one product version and its full descendant structure as
immutable :class:`BaselineMember` rows. Baselines start ``DRAFT`` and become
read-only once ``FROZEN``.
"""

from flask_appbuilder import Model
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.mixins import AuditMixin

STATUS_DRAFT = "DRAFT"
STATUS_FROZEN = "FROZEN"


class Baseline(AuditMixin, Model):
    """Named, immutable-once-frozen product configuration."""

    __tablename__ = "baseline"

    id = Column(Integer, primary_key=True)
    baseline_number = Column(String(32), nullable=False)
    baseline_name = Column(String(128), nullable=False)
    product_version_id = Column(
        Integer, ForeignKey("item_version.id"), nullable=False
    )
    status = Column(String(16), nullable=False, default=STATUS_DRAFT)
    frozen_at = Column(DateTime)
    description = Column(Text)

    product_version = relationship(
        "ItemVersion", foreign_keys=[product_version_id]
    )
    members = relationship(
        "BaselineMember",
        back_populates="baseline",
        cascade="all, delete-orphan",
        order_by="BaselineMember.id",
    )

    __table_args__ = (
        UniqueConstraint("baseline_number", name="uq_baseline_number"),
        CheckConstraint(
            "status IN ('DRAFT', 'FROZEN')", name="ck_baseline_status"
        ),
        CheckConstraint(
            "(status = 'FROZEN' AND frozen_at IS NOT NULL) "
            "OR (status = 'DRAFT' AND frozen_at IS NULL)",
            name="ck_baseline_frozen_consistency",
        ),
    )

    def __repr__(self) -> str:
        return f"{self.baseline_number} ({self.status})"


class BaselineMember(AuditMixin, Model):
    """A captured item version within a baseline structure."""

    __tablename__ = "baseline_member"

    id = Column(Integer, primary_key=True)
    baseline_id = Column(
        Integer,
        ForeignKey("baseline.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_version_id = Column(
        Integer, ForeignKey("item_version.id"), nullable=False
    )
    parent_member_id = Column(
        Integer, ForeignKey("baseline_member.id"), nullable=True
    )
    quantity = Column(Numeric(18, 6))
    find_number = Column(String(32))

    baseline = relationship("Baseline", back_populates="members")
    item_version = relationship("ItemVersion", foreign_keys=[item_version_id])
    parent = relationship(
        "BaselineMember", remote_side=[id], foreign_keys=[parent_member_id]
    )

    __table_args__ = (
        UniqueConstraint(
            "baseline_id",
            "item_version_id",
            "parent_member_id",
            name="uq_baseline_member",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_baseline_member_quantity_positive",
        ),
    )

    def __repr__(self) -> str:
        return f"BaselineMember({self.item_version_id})"
