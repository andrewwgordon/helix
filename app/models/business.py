"""Managed business objects (spec §8).

Each business object is a **shared-primary-key subtype** of
:class:`~app.models.core.ItemVersion`: the subtype table's ``item_version_id``
is both its primary key and a foreign key to ``item_version.id``. This is a
1:1 composition, so a subtype row exists only alongside its version and is
removed with it (``ondelete=CASCADE``).
"""

from flask_appbuilder import Model
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.mixins import AuditMixin


class Part(AuditMixin, Model):
    """A physical or logical part (spec §8.1)."""

    __tablename__ = "part"

    item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        primary_key=True,
    )
    unit_of_measure_id = Column(
        Integer, ForeignKey("unit_of_measure.id"), nullable=False
    )
    make_buy_code_id = Column(Integer, ForeignKey("make_buy_code.id"))
    weight = Column(Numeric(18, 6))
    weight_uom_id = Column(Integer, ForeignKey("unit_of_measure.id"))
    material = Column(String(128))

    item_version = relationship("ItemVersion", back_populates="part")
    unit_of_measure = relationship(
        "UnitOfMeasure", foreign_keys=[unit_of_measure_id]
    )
    weight_uom = relationship("UnitOfMeasure", foreign_keys=[weight_uom_id])
    make_buy_code = relationship("MakeBuyCode")

    __table_args__ = (
        CheckConstraint(
            "weight IS NULL OR weight >= 0",
            name="ck_part_weight_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return f"Part({self.item_version_id})"


class Document(AuditMixin, Model):
    """A managed file (spec §8.2)."""

    __tablename__ = "document"

    item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(128))
    file_size = Column(Integer)
    file_path = Column(String(512), nullable=False)
    checksum_sha256 = Column(String(64))

    item_version = relationship("ItemVersion", back_populates="document")

    __table_args__ = (
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="ck_document_file_size_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return f"Document({self.file_name})"


class Requirement(AuditMixin, Model):
    """A requirement statement (spec §8.3)."""

    __tablename__ = "requirement"

    item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        primary_key=True,
    )
    requirement_text = Column(Text, nullable=False)
    verification_method_id = Column(
        Integer, ForeignKey("verification_method.id")
    )
    priority_code_id = Column(Integer, ForeignKey("priority_code.id"))

    item_version = relationship("ItemVersion", back_populates="requirement")
    verification_method = relationship("VerificationMethod")
    priority_code = relationship("PriorityCode")

    def __repr__(self) -> str:
        return f"Requirement({self.item_version_id})"


class Product(AuditMixin, Model):
    """A product (spec §8.4)."""

    __tablename__ = "product"

    item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_family_id = Column(Integer, ForeignKey("product_family.id"))
    market_id = Column(Integer, ForeignKey("market.id"))
    platform = Column(String(128))
    release_target = Column(Date)

    item_version = relationship("ItemVersion", back_populates="product")
    product_family = relationship("ProductFamily")
    market = relationship("Market")

    def __repr__(self) -> str:
        return f"Product({self.item_version_id})"
