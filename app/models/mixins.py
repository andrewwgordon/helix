"""Audit columns for PLM models.

This mirrors FAB's ``AuditMixin`` but makes ``created_by_fk`` / ``changed_by_fk``
**nullable**. FAB's implementation marks them ``NOT NULL`` with a ``g.user``
default, which raises ``IntegrityError`` during seeding, CLI commands, and any
service call made outside a request context. The spec (§5.2) specifies these
columns as nullable, so this variant is used throughout the PLM schema.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from app.models.utils import utcnow


class AuditMixin:
    """Adds created/changed timestamps and user references to a model."""

    created_on = Column(DateTime, default=utcnow, nullable=False)
    changed_on = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    @declared_attr
    def created_by_fk(cls):
        return Column(Integer, ForeignKey("ab_user.id"), nullable=True)

    @declared_attr
    def created_by(cls):
        from flask_appbuilder.security.sqla.models import User

        return relationship(
            User,
            primaryjoin=f"{cls.__name__}.created_by_fk == User.id",
            enable_typechecks=False,
        )

    @declared_attr
    def changed_by_fk(cls):
        return Column(Integer, ForeignKey("ab_user.id"), nullable=True)

    @declared_attr
    def changed_by(cls):
        from flask_appbuilder.security.sqla.models import User

        return relationship(
            User,
            primaryjoin=f"{cls.__name__}.changed_by_fk == User.id",
            enable_typechecks=False,
        )
