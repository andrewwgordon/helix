"""Lifecycle service (spec §11 / §14.8).

All state changes are validated against the configurable
``lifecycle_transition`` table and guarded by the role recorded on each
transition. Every change emits a ``STATE_CHANGE`` audit event.
"""

from flask_appbuilder.security.sqla.models import Role

from app.models.audit import EVENT_STATE_CHANGE
from app.models.core import ItemVersion
from app.models.reference import LifecycleState, LifecycleTransition
from app.services.base import Actor, BaseService
from app.services.exceptions import (
    AuthorizationError,
    InvalidLifecycleTransitionError,
    NotFoundError,
)

# Convenience target states.
STATE_REVIEW = "REVIEW"
STATE_APPROVED = "APPROVED"
STATE_RELEASED = "RELEASED"
STATE_OBSOLETE = "OBSOLETE"


class LifecycleService(BaseService):
    """Validates and applies lifecycle transitions."""

    def _get_version(self, version_id: int) -> ItemVersion:
        version = self.session.get(ItemVersion, version_id)
        if version is None:
            raise NotFoundError(f"ItemVersion {version_id} not found")
        return version

    def _get_state(self, code: str) -> LifecycleState:
        state = self.session.query(LifecycleState).filter_by(code=code).first()
        if state is None:
            raise NotFoundError(f"LifecycleState '{code}' not found")
        return state

    def _require_role(self, transition: LifecycleTransition, actor: Actor):
        if transition.required_role_id is None or actor.is_admin:
            return
        role = self.session.get(Role, transition.required_role_id)
        if role is None or not actor.has_role(role.name):
            name = role.name if role is not None else transition.required_role_id
            raise AuthorizationError(f"Role '{name}' is required for this transition")

    # -- commands --------------------------------------------------------

    def change_lifecycle(
        self,
        version_id: int,
        to_state_code: str,
        actor: Actor = None,
        comment: str = None,
    ) -> ItemVersion:
        actor = self._actor(actor)
        version = self._get_version(version_id)
        to_state = self._get_state(to_state_code)

        transition = (
            self.session.query(LifecycleTransition)
            .filter_by(
                from_state_id=version.lifecycle_state_id,
                to_state_id=to_state.id,
                is_active=True,
            )
            .first()
        )
        if transition is None:
            raise InvalidLifecycleTransitionError(
                f"Transition '{version.lifecycle_state.code}' -> "
                f"'{to_state_code}' is not allowed"
            )

        self._require_role(transition, actor)

        from_code = version.lifecycle_state.code
        version.lifecycle_state_id = to_state.id
        self.audit.record(
            EVENT_STATE_CHANGE,
            "ItemVersion",
            version.id,
            actor,
            item_id=version.item_id,
            from_value=from_code,
            to_value=to_state.code,
            comment=comment,
        )
        self.session.commit()
        return version

    def submit_for_review(self, version_id: int, actor: Actor = None, comment: str = None):
        return self.change_lifecycle(version_id, STATE_REVIEW, actor, comment)

    def approve(self, version_id: int, actor: Actor = None, comment: str = None):
        return self.change_lifecycle(version_id, STATE_APPROVED, actor, comment)

    def release(self, version_id: int, actor: Actor = None, comment: str = None):
        return self.change_lifecycle(version_id, STATE_RELEASED, actor, comment)

    def obsolete(self, version_id: int, actor: Actor = None, comment: str = None):
        return self.change_lifecycle(version_id, STATE_OBSOLETE, actor, comment)

    # -- queries ---------------------------------------------------------

    def available_transitions(self, version_id: int, actor: Actor = None) -> list:
        """Return the transitions the actor may currently perform."""
        actor = self._actor(actor)
        version = self._get_version(version_id)
        transitions = (
            self.session.query(LifecycleTransition)
            .filter_by(from_state_id=version.lifecycle_state_id, is_active=True)
            .all()
        )
        allowed = []
        for transition in transitions:
            if transition.required_role_id is None or actor.is_admin:
                allowed.append(transition)
                continue
            role = self.session.get(Role, transition.required_role_id)
            if role is not None and actor.has_role(role.name):
                allowed.append(transition)
        return allowed

    def can_transition(
        self, version_id: int, to_state_code: str, actor: Actor = None
    ) -> bool:
        return any(
            t.to_state.code == to_state_code
            for t in self.available_transitions(version_id, actor)
        )
