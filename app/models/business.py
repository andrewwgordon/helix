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
    and_,
)
from sqlalchemy.orm import remote, relationship

from app.models.core import ItemRelationship
from app.models.mixins import AuditMixin
from app.models.reference import RelationshipType

# Association rows joined to their relationship type, so the traceability
# relationships below can restrict themselves to structural (CONTAINS) or
# non-structural edges by relationship-type code.
_ITEM_RELATIONSHIP = ItemRelationship.__table__
_RELATIONSHIP_TYPE = RelationshipType.__table__
_LINKS = _ITEM_RELATIONSHIP.join(
    _RELATIONSHIP_TYPE,
    _ITEM_RELATIONSHIP.c.relationship_type_id == _RELATIONSHIP_TYPE.c.id,
)


def _contained_in_products(owner):
    """Products that structurally contain ``owner`` (CONTAINS edges).

    The business object is the structural child (target) and the product is
    the parent (source). Used by the "Child Parts" / "Child Documents"
    related-view tabs on the Product show page.
    """
    return relationship(
        "Product",
        secondary=_LINKS,
        primaryjoin=f"{owner}.item_version_id == ItemRelationship.target_item_version_id",
        secondaryjoin=(
            "and_(ItemRelationship.source_item_version_id"
            " == remote(Product.item_version_id),"
            " RelationshipType.code == 'CONTAINS')"
        ),
        viewonly=True,
    )


def _performed_by_products(owner):
    """Products that perform ``owner`` (non-structural PERFORMS edges).

    The function is the target of the edge and the product is the source.
    Used by the "Functions" related-view tab on the Product show page.
    """
    return relationship(
        "Product",
        secondary=_LINKS,
        primaryjoin=f"{owner}.item_version_id == ItemRelationship.target_item_version_id",
        secondaryjoin=(
            "and_(ItemRelationship.source_item_version_id"
            " == remote(Product.item_version_id),"
            " RelationshipType.code == 'PERFORMS')"
        ),
        viewonly=True,
    )


def _fulfilled_by_parts(owner):
    """Parts that fulfill ``owner`` (non-structural FULFILLS edges).

    The function is the target of the edge and the part is the source.
    Used by the "Fulfilled by Parts" related-view tab on the Function show
    page.
    """
    return relationship(
        "Part",
        secondary=_LINKS,
        primaryjoin=f"{owner}.item_version_id == ItemRelationship.target_item_version_id",
        secondaryjoin=(
            "and_(ItemRelationship.source_item_version_id"
            " == remote(Part.item_version_id),"
            " RelationshipType.code == 'FULFILLS')"
        ),
        viewonly=True,
    )


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

    # Products whose structure contains this part (structural child).
    contained_in_products = _contained_in_products("Part")

    # Functions this part fulfils (non-structural FULFILLS edges; the part is
    # the source). Used by the "Fulfills Functions" tab on the Part show page.
    fulfills_functions = relationship(
        "Function",
        secondary=_LINKS,
        primaryjoin="Part.item_version_id == ItemRelationship.source_item_version_id",
        secondaryjoin=(
            "and_(ItemRelationship.target_item_version_id"
            " == remote(Function.item_version_id),"
            " RelationshipType.code == 'FULFILLS')"
        ),
        viewonly=True,
    )

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

    # Products whose structure contains this document (structural child).
    contained_in_products = _contained_in_products("Document")

    __table_args__ = (
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="ck_document_file_size_non_negative",
        ),
    )

    @property
    def download_url(self):
        """URL of the standard ``DocumentModelView.download`` route.

        Exposed as a model property so the bundled FAB list/show widgets can
        render a one-click "Open" link (see ``download_link`` formatter)
        without any custom template.
        """
        from flask import url_for

        return url_for("DocumentModelView.download", pk=self.item_version_id)

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

    # Products this requirement points to through a traceability link
    # (non-structural edges such as SATISFIES / REFERENCES). The requirement
    # is the source, i.e. the parent side of the link.
    linked_products = relationship(
        "Product",
        secondary=_LINKS,
        primaryjoin="Requirement.item_version_id == ItemRelationship.source_item_version_id",
        secondaryjoin=(
            "and_(ItemRelationship.target_item_version_id"
            " == remote(Product.item_version_id),"
            " RelationshipType.is_structural.is_(False))"
        ),
        viewonly=True,
    )

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


class Function(AuditMixin, Model):
    """A product function (functional breakdown object).

    Functions form their own hierarchy: a child function has exactly one
    parent (``CONTAINS`` edge from the parent function, browsable through the
    structure tree), a product *performs* one or more top-level functions
    (``PERFORMS`` edges) and a part *fulfils* one or more functions
    (``FULFILLS`` edges).
    """

    __tablename__ = "function"

    item_version_id = Column(
        Integer,
        ForeignKey("item_version.id", ondelete="CASCADE"),
        primary_key=True,
    )
    function_text = Column(Text, nullable=False)

    item_version = relationship("ItemVersion", back_populates="function")

    # Products that perform this function (non-structural PERFORMS edges).
    performed_by_products = _performed_by_products("Function")

    # Parts that fulfil this function (non-structural FULFILLS edges).
    fulfilled_by_parts = _fulfilled_by_parts("Function")

    def __repr__(self) -> str:
        return f"Function({self.item_version_id})"
