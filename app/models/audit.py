"""Application-level audit trail (spec §7.4 / §13).

Audit records are append-only. Timestamp and actor come from FAB's
``AuditMixin`` (``created_on`` and ``created_by_fk``); this table is the one
deliberate exception to the "one created timestamp" convention because it
records *domain* events rather than mutable rows.
"""

from flask_appbuilder import Model
from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text

from app.models.mixins import AuditMixin

# Event type constants (spec §7.4).
EVENT_CREATE = "CREATE"
EVENT_REVISE = "REVISE"
EVENT_STATE_CHANGE = "STATE_CHANGE"
EVENT_REL_ADD = "REL_ADD"
EVENT_REL_REMOVE = "REL_REMOVE"
EVENT_BASELINE_CREATE = "BASELINE_CREATE"
EVENT_BASELINE_FREEZE = "BASELINE_FREEZE"
EVENT_UPDATE = "UPDATE"
EVENT_DELETE = "DELETE"


class AuditEvent(AuditMixin, Model):
    """A single domain mutation event."""

    __tablename__ = "audit_event"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(32), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=False)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=True)
    from_value = Column(String(255))
    to_value = Column(String(255))
    comment = Column(Text)

    __table_args__ = (
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
        Index("ix_audit_event_item", "item_id", "created_on"),
    )

    def __repr__(self) -> str:
        return f"{self.event_type} {self.entity_type}#{self.entity_id}"
