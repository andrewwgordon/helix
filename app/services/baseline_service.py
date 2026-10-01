"""Baseline service (spec §12 / §14.9)."""

from dataclasses import dataclass, field

from app.models.audit import EVENT_BASELINE_CREATE, EVENT_BASELINE_FREEZE
from app.models.baseline import STATUS_DRAFT, STATUS_FROZEN, Baseline, BaselineMember
from app.models.core import ItemVersion
from app.models.utils import utcnow
from app.services.base import Actor, BaseService
from app.services.exceptions import (
    BaselineFrozenError,
    BaselineValidationError,
    ConflictError,
    NotFoundError,
)
from app.services.relationship_service import RelationshipService


@dataclass
class BaselineDiff:
    """Result of comparing two baselines (by item identity)."""

    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)


class BaselineService(BaseService):
    """Creates, freezes and inspects baseline configurations."""

    # -- helpers ---------------------------------------------------------

    def _get_baseline(self, baseline_id: int) -> Baseline:
        baseline = self.session.get(Baseline, baseline_id)
        if baseline is None:
            raise NotFoundError(f"Baseline {baseline_id} not found")
        return baseline

    def _get_version(self, version_id: int) -> ItemVersion:
        version = self.session.get(ItemVersion, version_id)
        if version is None:
            raise NotFoundError(f"ItemVersion {version_id} not found")
        return version

    @staticmethod
    def _ensure_releasable(version: ItemVersion):
        state = version.lifecycle_state
        code = state.code if state is not None else "?"
        if state is None or not state.is_releasable:
            raise BaselineValidationError(
                f"Version {version.id} is in state '{code}' and cannot enter a "
                "baseline"
            )

    @staticmethod
    def _ensure_not_frozen(baseline: Baseline):
        if baseline.status == STATUS_FROZEN:
            raise BaselineFrozenError(
                f"Baseline '{baseline.baseline_number}' is frozen and immutable"
            )

    # -- commands --------------------------------------------------------

    def create_baseline(
        self,
        product_version_id: int,
        baseline_number: str,
        baseline_name: str,
        actor: Actor = None,
        *,
        description: str = None,
        freeze_immediately: bool = False,
    ) -> Baseline:
        actor = self._actor(actor)
        root_version = self._get_version(product_version_id)
        self._ensure_releasable(root_version)

        if (
            self.session.query(Baseline)
            .filter_by(baseline_number=baseline_number)
            .first()
            is not None
        ):
            raise ConflictError(
                f"Baseline '{baseline_number}' already exists"
            )

        baseline = Baseline(
            baseline_number=baseline_number,
            baseline_name=baseline_name,
            product_version_id=root_version.id,
            status=STATUS_DRAFT,
            description=description,
            created_by_fk=actor.id,
            changed_by_fk=actor.id,
        )
        self.session.add(baseline)
        try:
            self.session.flush()

            tree = RelationshipService(self.session).build_tree(
                root_version.id, direction="down"
            )
            self._capture(baseline, tree, None)

            self.audit.record(
                EVENT_BASELINE_CREATE,
                "Baseline",
                baseline.id,
                actor,
                item_id=root_version.item_id,
                to_value=baseline.baseline_number,
            )

            if freeze_immediately:
                baseline.status = STATUS_FROZEN
                baseline.frozen_at = utcnow()
                self.audit.record(
                    EVENT_BASELINE_FREEZE,
                    "Baseline",
                    baseline.id,
                    actor,
                    item_id=root_version.item_id,
                    to_value=baseline.baseline_number,
                )

            self.session.commit()
        except Exception:
            # A descendant may be non-releasable; roll the whole capture back
            # so no partial baseline is left behind (spec §14.1, §12.3).
            self.session.rollback()
            raise
        return baseline

    def _capture(self, baseline, node, parent_member) -> BaselineMember:
        version = node["version"]
        self._ensure_releasable(version)
        relationship = node["relationship"]

        member = BaselineMember(
            baseline_id=baseline.id,
            item_version_id=version.id,
            parent_member_id=getattr(parent_member, "id", None),
            quantity=getattr(relationship, "quantity", None),
            find_number=getattr(relationship, "find_number", None),
            created_by_fk=baseline.created_by_fk,
            changed_by_fk=baseline.created_by_fk,
        )
        self.session.add(member)
        self.session.flush()

        for child in node["children"]:
            self._capture(baseline, child, member)
        return member

    def add_member(
        self,
        baseline_id: int,
        item_version_id: int,
        actor: Actor = None,
        *,
        parent_member_id: int = None,
        quantity=None,
        find_number: str = None,
    ) -> BaselineMember:
        actor = self._actor(actor)
        baseline = self._get_baseline(baseline_id)
        self._ensure_not_frozen(baseline)

        version = self._get_version(item_version_id)
        self._ensure_releasable(version)

        if parent_member_id is not None:
            parent = self.session.get(BaselineMember, parent_member_id)
            if parent is None or parent.baseline_id != baseline.id:
                raise BaselineValidationError(
                    f"Parent member {parent_member_id} is not in this baseline"
                )

        existing = (
            self.session.query(BaselineMember)
            .filter_by(
                baseline_id=baseline.id,
                item_version_id=version.id,
                parent_member_id=parent_member_id,
            )
            .first()
        )
        if existing is not None:
            raise ConflictError("This version is already a member of the baseline")

        member = BaselineMember(
            baseline_id=baseline.id,
            item_version_id=version.id,
            parent_member_id=parent_member_id,
            quantity=quantity,
            find_number=find_number,
            created_by_fk=actor.id,
            changed_by_fk=actor.id,
        )
        self.session.add(member)
        self.session.flush()
        self.session.commit()
        return member

    def freeze_baseline(self, baseline_id: int, actor: Actor = None) -> Baseline:
        actor = self._actor(actor)
        baseline = self._get_baseline(baseline_id)
        self._ensure_not_frozen(baseline)

        baseline.status = STATUS_FROZEN
        baseline.frozen_at = utcnow()
        self.audit.record(
            EVENT_BASELINE_FREEZE,
            "Baseline",
            baseline.id,
            actor,
            item_id=baseline.product_version.item_id,
            to_value=baseline.baseline_number,
        )
        self.session.commit()
        return baseline

    # -- queries ---------------------------------------------------------

    def list_members(self, baseline_id: int) -> list:
        baseline = self._get_baseline(baseline_id)
        members = list(baseline.members)
        by_id = {member.id: member for member in members}

        def depth(member):
            level = 0
            current = member
            while current.parent_member_id is not None:
                current = by_id[current.parent_member_id]
                level += 1
            return level

        return sorted(members, key=lambda m: (depth(m), m.id))

    def compare_baselines(self, baseline_a_id: int, baseline_b_id: int) -> BaselineDiff:
        map_a = self._member_map(baseline_a_id)
        map_b = self._member_map(baseline_b_id)

        added = [map_b[key] for key in map_b.keys() - map_a.keys()]
        removed = [map_a[key] for key in map_a.keys() - map_b.keys()]
        changed = [
            (map_a[key], map_b[key])
            for key in map_a.keys() & map_b.keys()
            if map_a[key].item_version_id != map_b[key].item_version_id
        ]
        unchanged = [
            (map_a[key], map_b[key])
            for key in map_a.keys() & map_b.keys()
            if map_a[key].item_version_id == map_b[key].item_version_id
        ]
        return BaselineDiff(
            added=added, removed=removed, changed=changed, unchanged=unchanged
        )

    def _member_map(self, baseline_id: int) -> dict:
        baseline = self._get_baseline(baseline_id)
        # Keyed by item identity so a revision change is detected as "changed".
        return {member.item_version.item_id: member for member in baseline.members}
