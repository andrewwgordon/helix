"""Relationship and structure service (spec §14.7)."""

from app.models.audit import EVENT_REL_ADD, EVENT_REL_REMOVE
from app.models.core import ItemRelationship, ItemVersion
from app.models.reference import RelationshipType
from app.services.base import Actor, BaseService
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    RelationshipCycleError,
    ValidationError,
)


class RelationshipService(BaseService):
    """Manages directed edges between item versions."""

    # -- helpers ---------------------------------------------------------

    def _get_version(self, version_id: int) -> ItemVersion:
        version = self.session.get(ItemVersion, version_id)
        if version is None:
            raise NotFoundError(f"ItemVersion {version_id} not found")
        return version

    def _get_type(self, code: str) -> RelationshipType:
        rtype = (
            self.session.query(RelationshipType)
            .filter_by(code=code, is_active=True)
            .first()
        )
        if rtype is None:
            raise NotFoundError(f"RelationshipType '{code}' not found")
        return rtype

    # -- commands --------------------------------------------------------

    def add_relationship(
        self,
        source_version_id: int,
        target_version_id: int,
        relationship_type_code: str,
        actor: Actor = None,
        *,
        quantity=None,
        find_number: str = None,
    ) -> ItemRelationship:
        actor = self._actor(actor)
        rtype = self._get_type(relationship_type_code)
        source = self._get_version(source_version_id)
        target = self._get_version(target_version_id)

        if source.id == target.id:
            raise ValidationError("An item version cannot relate to itself")

        self.ensure_version_mutable(source)

        if quantity is not None and not rtype.allows_quantity:
            raise ValidationError(
                f"Relationship '{rtype.code}' does not allow a quantity"
            )
        if find_number is not None and not rtype.allows_find_number:
            raise ValidationError(
                f"Relationship '{rtype.code}' does not allow a find number"
            )
        if quantity is not None and quantity <= 0:
            raise ValidationError("quantity must be greater than 0")
        if rtype.allows_quantity and quantity is None:
            quantity = 1

        if rtype.is_structural and self.would_create_cycle(source.id, target.id):
            raise RelationshipCycleError(
                f"Adding {source.id} -> {target.id} would create a cycle"
            )

        existing = (
            self.session.query(ItemRelationship)
            .filter_by(
                relationship_type_id=rtype.id,
                source_item_version_id=source.id,
                target_item_version_id=target.id,
            )
            .first()
        )
        if existing is not None:
            raise ConflictError(
                f"Relationship {rtype.code} {source.id} -> {target.id} "
                "already exists"
            )

        relationship = ItemRelationship(
            relationship_type_id=rtype.id,
            source_item_version_id=source.id,
            target_item_version_id=target.id,
            quantity=quantity,
            find_number=find_number,
            created_by_fk=actor.id,
        )
        self.session.add(relationship)
        self.session.flush()

        self.audit.record(
            EVENT_REL_ADD,
            "ItemRelationship",
            relationship.id,
            actor,
            item_id=source.item_id,
            from_value=str(source.item_id),
            to_value=f"{rtype.code}:{target.item_id}",
        )
        self.session.commit()
        return relationship

    def remove_relationship(self, relationship_id: int, actor: Actor = None) -> None:
        actor = self._actor(actor)
        relationship = self.session.get(ItemRelationship, relationship_id)
        if relationship is None:
            raise NotFoundError(f"ItemRelationship {relationship_id} not found")

        source = self._get_version(relationship.source_item_version_id)
        self.ensure_version_mutable(source)

        self.session.delete(relationship)
        self.audit.record(
            EVENT_REL_REMOVE,
            "ItemRelationship",
            relationship_id,
            actor,
            item_id=source.item_id,
        )
        self.session.commit()

    # -- traversal -------------------------------------------------------

    def would_create_cycle(self, source_version_id: int, target_version_id: int) -> bool:
        """Return True if adding source->target closes a structural cycle."""
        stack = [target_version_id]
        visited = set()
        while stack:
            version_id = stack.pop()
            if version_id == source_version_id:
                return True
            if version_id in visited:
                continue
            visited.add(version_id)
            children = (
                self.session.query(ItemRelationship)
                .join(RelationshipType)
                .filter(
                    ItemRelationship.source_item_version_id == version_id,
                    RelationshipType.is_structural.is_(True),
                )
                .all()
            )
            stack.extend(rel.target_item_version_id for rel in children)
        return False

    def get_downstream(
        self,
        version_id: int,
        *,
        relationship_type: str = None,
        max_depth: int = None,
    ) -> list:
        return self._traverse(
            version_id,
            direction="down",
            relationship_type=relationship_type,
            max_depth=max_depth,
        )

    def get_upstream(
        self,
        version_id: int,
        *,
        relationship_type: str = None,
        max_depth: int = None,
    ) -> list:
        return self._traverse(
            version_id,
            direction="up",
            relationship_type=relationship_type,
            max_depth=max_depth,
        )

    def _traverse(
        self,
        root_id: int,
        direction: str,
        relationship_type: str = None,
        max_depth: int = None,
    ) -> list:
        self._get_version(root_id)
        result = []
        seen = set()
        frontier = [root_id]
        depth = 0

        while frontier and (max_depth is None or depth < max_depth):
            next_frontier = []
            for version_id in frontier:
                query = self.session.query(ItemRelationship)
                if direction == "down":
                    query = query.filter(
                        ItemRelationship.source_item_version_id == version_id
                    )
                else:
                    query = query.filter(
                        ItemRelationship.target_item_version_id == version_id
                    )
                if relationship_type is not None:
                    query = query.join(RelationshipType).filter(
                        RelationshipType.code == relationship_type
                    )

                for rel in query.all():
                    neighbour = (
                        rel.target_item_version_id
                        if direction == "down"
                        else rel.source_item_version_id
                    )
                    if neighbour in seen or neighbour == root_id:
                        continue
                    seen.add(neighbour)
                    next_frontier.append(neighbour)
                    result.append(self.session.get(ItemVersion, neighbour))

            frontier = next_frontier
            depth += 1

        return result

    def build_tree(
        self,
        version_id: int,
        *,
        direction: str = "down",
        max_depth: int = None,
    ) -> dict:
        """Return a nested tree of structural relationships.

        ``direction="down"`` builds the BOM (children); ``"up"`` builds the
        where-used tree (parents). The root is always included.
        """
        root = self._get_version(version_id)
        return self._expand(root, direction, max_depth, 0, {root.id})

    def _expand(self, version, direction, max_depth, depth, seen) -> dict:
        node = {"version": version, "relationship": None, "children": []}
        if max_depth is not None and depth >= max_depth:
            return node

        query = (
            self.session.query(ItemRelationship)
            .join(RelationshipType)
            .filter(RelationshipType.is_structural.is_(True))
        )
        if direction == "down":
            query = query.filter(
                ItemRelationship.source_item_version_id == version.id
            )
        else:
            query = query.filter(
                ItemRelationship.target_item_version_id == version.id
            )
        query = query.order_by(ItemRelationship.sort_order, ItemRelationship.id)

        for relationship in query.all():
            neighbour_id = (
                relationship.target_item_version_id
                if direction == "down"
                else relationship.source_item_version_id
            )
            if neighbour_id in seen:
                continue
            neighbour = self.session.get(ItemVersion, neighbour_id)
            child = self._expand(
                neighbour, direction, max_depth, depth + 1, seen | {neighbour_id}
            )
            child["relationship"] = relationship
            node["children"].append(child)
        return node
