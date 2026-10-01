"""Small model helpers."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime.

    SQLite stores datetimes as ISO-8601 text; using naive UTC keeps values
    consistent with FAB's ``AuditMixin`` (which also uses ``utcnow``).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
