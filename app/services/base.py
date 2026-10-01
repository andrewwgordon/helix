"""Shared service infrastructure (spec §14.1)."""

from dataclasses import dataclass, field
from typing import Optional

from app.services.exceptions import ReleasedVersionImmutableError


@dataclass(frozen=True)
class Actor:
    """The acting user context passed to every service call.

    ``roles`` holds role *names* (e.g. ``"PLM Manager"``).
    """

    id: Optional[int] = None
    username: Optional[str] = None
    roles: frozenset = field(default_factory=frozenset)
    is_admin: bool = False

    def has_role(self, role_name: str) -> bool:
        return role_name in self.roles

    @classmethod
    def from_user(cls, user) -> "Actor":
        """Build an actor from a FAB security user (or ``None`` for anonymous)."""
        if user is None:
            return cls()
        roles = frozenset(r.name for r in getattr(user, "roles", []) or [])
        return cls(
            id=getattr(user, "id", None),
            username=getattr(user, "username", None),
            roles=roles,
            is_admin="Admin" in roles,
        )


class BaseService:
    """Common state and helpers for domain services."""

    def __init__(self, session, actor: Optional[Actor] = None):
        self.session = session
        self.actor = actor or Actor()
        # Imported lazily to avoid a circular import at module load.
        from app.services.audit_service import AuditEventService

        self.audit = AuditEventService(session)

    def _actor(self, actor: Optional[Actor]) -> Actor:
        return actor or self.actor or Actor()

    def _commit(self):
        self.session.commit()

    def _rollback(self):
        self.session.rollback()

    @staticmethod
    def ensure_version_mutable(version):
        """Reject mutations of a released/baselined version (spec §10.4)."""
        state = getattr(version, "lifecycle_state", None)
        if state is not None and state.is_releasable:
            raise ReleasedVersionImmutableError(
                f"Version {version.id} is in '{state.code}' and cannot be modified"
            )
