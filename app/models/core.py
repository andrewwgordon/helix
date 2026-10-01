"""Core identity and revision entities (spec §7).

``Item`` is the stable business identity; ``ItemVersion`` is a specific
revision. The two reference each other, so the ``Item.current_version_id``
foreign key uses ``use_alter=True`` to break the circular table dependency.
"""

from flask_appbuilder import Model
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.mixins import AuditMixin


class Item(AuditMixin, Model):
    """Stable business identity of a managed object."""

    __tablename__ = "item"

    id = Column(Integer, primary_key=True)
    item_type_id = Column(
        Integer,
        ForeignKey("item_type.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_number = Column(String(64), nullable=False)
    current_version_id = Column(
        Integer,
        ForeignKey(
            "item_version.id",
            use_alter=True,
            name="fk_item_current_version_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    item_type = relationship("ItemType", foreign_keys=[item_type_id])
    current_version = relationship(
        "ItemVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions = relationship(
        "ItemVersion",
        back_populates="item",
        foreign_keys="[ItemVersion.item_id]",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("item_type_id", "item_number", name="uq_item_type_number"),
        Index("ix_item_current_version", "current_version_id"),
    )

    def __repr__(self) -> str:
        return self.item_number


class ItemVersion(AuditMixin, Model):
    """A specific revision of an :class:`Item`."""

    __tablename__ = "item_version"

    id = Column(Integer, primary_key=True)
    item_id = Column(
        Integer, ForeignKey("item.id", ondelete="CASCADE"), nullable=False
    )
    version_sequence = Column(Integer, nullable=False)
    major_revision = Column(Integer, nullable=False, default=0)
    minor_revision = Column(Integer, nullable=False, default=0)
    revision_label = Column(String(16), nullable=False)
    description = Column(Text)
    lifecycle_state_id = Column(
        Integer, ForeignKey("lifecycle_state.id"), nullable=False
    )
    superseded_by_id = Column(
        Integer, ForeignKey("item_version.id"), nullable=True
    )
    effective_from = Column(Date)
    effective_to = Column(Date)

    item = relationship(
        "Item", back_populates="versions", foreign_keys=[item_id]
    )
    lifecycle_state = relationship("LifecycleState", foreign_keys=[lifecycle_state_id])
    superseded_by = relationship(
        "ItemVersion", remote_side=[id], foreign_keys=[superseded_by_id]
    )

    # Shared-primary-key business-object subtypes (spec §8). At most one of
    # these is populated for a given version, according to its item type.
    part = relationship(
        "Part",
        back_populates="item_version",
        uselist=False,
        cascade="all, delete-orphan",
    )
    document = relationship(
        "Document",
        back_populates="item_version",
        uselist=False,
        cascade="all, delete-orphan",
    )
    requirement = relationship(
        "Requirement",
        back_populates="item_version",
        uselist=False,
        cascade="all, delete-orphan",
    )
    product = relationship(
        "Product",
        back_populates="item_version",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "item_id", "version_sequence", name="uq_item_version_sequence"
        ),
        UniqueConstraint(
            "item_id",
            "major_revision",
            "minor_revision",
            name="uq_item_version_revision",
        ),
        CheckConstraint(
            "version_sequence >= 1", name="ck_item_version_sequence_positive"
        ),
        CheckConstraint(
            "major_revision >= 0", name="ck_item_version_major_non_negative"
        ),
        CheckConstraint(
            "minor_revision >= 0", name="ck_item_version_minor_non_negative"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL "
            "OR effective_to >= effective_from",
            name="ck_item_version_effective_range",
        ),
        Index("ix_item_version_lifecycle_state", "lifecycle_state_id"),
    )

    def __repr__(self) -> str:
        return f"{self.item.item_number} {self.revision_label}"


class ItemRelationship(AuditMixin, Model):
    """A directed edge between two item versions (spec §7.3).

    For structural relationships the source is the parent and the target is
    the child.
    """

    __tablename__ = "item_relationship"

    id = Column(Integer, primary_key=True)
    relationship_type_id = Column(
        Integer, ForeignKey("relationship_type.id"), nullable=False
    )
    source_item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity = Column(Numeric(18, 6))
    find_number = Column(String(32))
    sort_order = Column(Integer, default=0)

    relationship_type = relationship(
        "RelationshipType", foreign_keys=[relationship_type_id]
    )
    source_item_version = relationship(
        "ItemVersion", foreign_keys=[source_item_version_id]
    )
    target_item_version = relationship(
        "ItemVersion", foreign_keys=[target_item_version_id]
    )

    __table_args__ = (
        UniqueConstraint(
            "relationship_type_id",
            "source_item_version_id",
            "target_item_version_id",
            name="uq_item_relationship_edge",
        ),
        CheckConstraint(
            "source_item_version_id <> target_item_version_id",
            name="ck_item_relationship_no_self",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_item_relationship_quantity_positive",
        ),
        Index("ix_item_relationship_source", "source_item_version_id"),
        Index("ix_item_relationship_target", "target_item_version_id"),
    )

    def __repr__(self) -> str:
        return (
            f"{self.source_item_version_id} -[{self.relationship_type}]-> "
            f"{self.target_item_version_id}"
        )
