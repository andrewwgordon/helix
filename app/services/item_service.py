"""Item identity and revision service (spec §14.2)."""

from app.models.audit import EVENT_CREATE, EVENT_REVISE
from app.models.core import Item, ItemRelationship, ItemVersion
from app.models.reference import ItemType, LifecycleState
from app.services.base import Actor, BaseService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.lifecycle_service import LifecycleService

CHANGE_MAJOR = "major"
CHANGE_MINOR = "minor"
_VALID_CHANGE_TYPES = {CHANGE_MAJOR, CHANGE_MINOR}


def format_revision(major: int, minor: int) -> str:
    """Format a revision label, e.g. (0, 0) -> "A", (1, 2) -> "B.2"."""
    letter = chr(ord("A") + major)
    return f"{letter}.{minor}" if minor else letter


class ItemService(BaseService):
    """Creates items and versions and manages lifecycle transitions."""

    # -- lookups ---------------------------------------------------------

    def _get_item(self, item_id: int) -> Item:
        item = self.session.get(Item, item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")
        return item

    def _get_version(self, version_id: int) -> ItemVersion:
        version = self.session.get(ItemVersion, version_id)
        if version is None:
            raise NotFoundError(f"ItemVersion {version_id} not found")
        return version

    def _get_state(self, code: str) -> LifecycleState:
        state = (
            self.session.query(LifecycleState).filter_by(code=code).first()
        )
        if state is None:
            raise NotFoundError(f"LifecycleState '{code}' not found")
        return state

    def _last_version(self, item_id: int):
        return (
            self.session.query(ItemVersion)
            .filter_by(item_id=item_id)
            .order_by(ItemVersion.version_sequence.desc())
            .first()
        )

    # -- commands --------------------------------------------------------

    def create_item(
        self,
        item_type_code: str,
        item_number: str,
        actor: Actor = None,
        *,
        commit: bool = True,
    ) -> Item:
        actor = self._actor(actor)
        if not item_number or not item_number.strip():
            raise ValidationError("item_number is required", field="item_number")

        item_type = (
            self.session.query(ItemType)
            .filter_by(code=item_type_code, is_active=True)
            .first()
        )
        if item_type is None:
            raise NotFoundError(f"ItemType '{item_type_code}' not found")

        existing = (
            self.session.query(Item)
            .filter_by(item_type_id=item_type.id, item_number=item_number)
            .first()
        )
        if existing is not None:
            raise ConflictError(
                f"Item '{item_number}' already exists for type '{item_type_code}'",
                field="item_number",
            )

        item = Item(
            item_type_id=item_type.id,
            item_number=item_number,
            created_by_fk=actor.id,
        )
        self.session.add(item)
        self.session.flush()

        self.audit.record(EVENT_CREATE, "Item", item.id, actor, item_id=item.id)
        if commit:
            self.session.commit()
        return item

    def create_version(
        self,
        item_id: int,
        actor: Actor = None,
        *,
        major_revision: int = None,
        minor_revision: int = None,
        description: str = None,
        lifecycle_code: str = "DRAFT",
        commit: bool = True,
    ) -> ItemVersion:
        actor = self._actor(actor)
        item = self._get_item(item_id)
        last = self._last_version(item_id)

        if last is None:
            sequence = 1
            major = 0 if major_revision is None else major_revision
            minor = 0 if minor_revision is None else minor_revision
        else:
            sequence = last.version_sequence + 1
            major = last.major_revision if major_revision is None else major_revision
            minor = (
                last.minor_revision + 1 if minor_revision is None else minor_revision
            )

        if major < 0 or minor < 0:
            raise ValidationError("Revisions cannot be negative")

        state = self._get_state(lifecycle_code)
        version = ItemVersion(
            item_id=item_id,
            version_sequence=sequence,
            major_revision=major,
            minor_revision=minor,
            revision_label=format_revision(major, minor),
            description=description,
            lifecycle_state_id=state.id,
            created_by_fk=actor.id,
        )
        self.session.add(version)
        self.session.flush()

        if last is not None:
            last.superseded_by_id = version.id
            self.audit.record(
                EVENT_REVISE,
                "ItemVersion",
                version.id,
                actor,
                item_id=item_id,
                from_value=last.revision_label,
                to_value=version.revision_label,
            )
        else:
            self.audit.record(
                EVENT_CREATE,
                "ItemVersion",
                version.id,
                actor,
                item_id=item_id,
                to_value=version.revision_label,
            )

        item.current_version_id = version.id
        if commit:
            self.session.commit()
        return version

    def revise_item(
        self,
        item_id: int,
        change_type: str,
        actor: Actor = None,
        *,
        copy_relationships: bool = True,
        description: str = None,
        commit: bool = True,
    ) -> ItemVersion:
        actor = self._actor(actor)
        if change_type not in _VALID_CHANGE_TYPES:
            raise ValidationError(
                f"change_type must be one of {sorted(_VALID_CHANGE_TYPES)}"
            )

        current = self.get_current_version(item_id)
        if current is None:
            raise ValidationError(
                f"Item {item_id} has no current version to revise"
            )
        self.ensure_version_mutable(current)

        if change_type == CHANGE_MAJOR:
            major, minor = current.major_revision + 1, 0
        else:
            major, minor = current.major_revision, current.minor_revision + 1

        new_version = self.create_version(
            item_id,
            actor,
            major_revision=major,
            minor_revision=minor,
            description=description,
            commit=False,
        )

        if copy_relationships:
            self._copy_relationships(current.id, new_version.id, actor, commit=False)

        if commit:
            self.session.commit()
        return new_version

    def _copy_relationships(
        self, source_version_id, new_version_id, actor, *, commit: bool = True
    ):
        source = self._get_version(source_version_id)
        copied = (
            self.session.query(ItemRelationship)
            .filter_by(source_item_version_id=source.id)
            .all()
        )
        for rel in copied:
            clone = ItemRelationship(
                relationship_type_id=rel.relationship_type_id,
                source_item_version_id=new_version_id,
                target_item_version_id=rel.target_item_version_id,
                quantity=rel.quantity,
                find_number=rel.find_number,
                sort_order=rel.sort_order,
                created_by_fk=actor.id,
            )
            self.session.add(clone)
        if copied and commit:
            self.session.commit()

    def change_lifecycle(
        self,
        version_id: int,
        to_state_code: str,
        actor: Actor = None,
        comment: str = None,
    ) -> ItemVersion:
        """Backwards-compatible shim; lifecycle logic lives in LifecycleService."""
        return LifecycleService(self.session, self.actor).change_lifecycle(
            version_id, to_state_code, actor, comment
        )

    def available_transitions(self, version_id: int, actor: Actor = None) -> list:
        """Backwards-compatible shim; see :class:`LifecycleService`."""
        return LifecycleService(self.session, self.actor).available_transitions(
            version_id, actor
        )

    def can_transition(
        self, version_id: int, to_state_code: str, actor: Actor = None
    ) -> bool:
        """Backwards-compatible shim; see :class:`LifecycleService`."""
        return LifecycleService(self.session, self.actor).can_transition(
            version_id, to_state_code, actor
        )

    # -- queries ---------------------------------------------------------

    def get_current_version(self, item_id: int):
        item = self._get_item(item_id)
        if item.current_version_id is None:
            return None
        return self.session.get(ItemVersion, item.current_version_id)

    def list_versions(self, item_id: int) -> list:
        self._get_item(item_id)
        return (
            self.session.query(ItemVersion)
            .filter_by(item_id=item_id)
            .order_by(ItemVersion.version_sequence.asc())
            .all()
        )
