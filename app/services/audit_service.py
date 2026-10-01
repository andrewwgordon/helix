"""Audit trail service (spec §13 / §14.10)."""

from app.models.audit import AuditEvent
from app.services.base import Actor


class AuditEventService:
    """Records and queries :class:`~app.models.audit.AuditEvent` rows.

    Recording is deliberately not transactional on its own: it adds to the
    caller's session so the event commits atomically with the mutation.
    """

    def __init__(self, session):
        self.session = session

    def record(
        self,
        event_type: str,
        entity_type: str,
        entity_id: int,
        actor: Actor = None,
        *,
        item_id: int = None,
        from_value: str = None,
        to_value: str = None,
        comment: str = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            item_id=item_id,
            from_value=from_value,
            to_value=to_value,
            comment=comment,
            created_by_fk=getattr(actor, "id", None),
        )
        self.session.add(event)
        return event

    def query(self, entity_type: str, entity_id: int) -> list:
        return (
            self.session.query(AuditEvent)
            .filter_by(entity_type=entity_type, entity_id=entity_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

    def query_by_item(self, item_id: int) -> list:
        return (
            self.session.query(AuditEvent)
            .filter_by(item_id=item_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )
