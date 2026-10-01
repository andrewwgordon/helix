"""Shared helpers for business-object services (spec §14.3–§14.6)."""

from app.models.core import ItemVersion
from app.services.base import BaseService
from app.services.exceptions import NotFoundError, ValidationError
from app.services.item_service import ItemService


class BusinessObjectService(BaseService):
    """Base class for Part/Document/Requirement/Product services."""

    item_type_code: str = None
    version_attr: str = None  # e.g. "part" on ItemVersion

    def __init__(self, session, actor=None):
        super().__init__(session, actor)
        self.items = ItemService(session, self.actor)

    def _lookup(self, model, code, *, required=False):
        """Resolve a lookup entity by active ``code``."""
        if code is None:
            if required:
                raise ValidationError(f"{model.__name__} code is required")
            return None
        obj = (
            self.session.query(model)
            .filter_by(code=code, is_active=True)
            .first()
        )
        if obj is None:
            raise NotFoundError(f"{model.__name__} '{code}' not found")
        return obj

    def _get_version(self, version_id: int) -> ItemVersion:
        version = self.session.get(ItemVersion, version_id)
        if version is None:
            raise NotFoundError(f"ItemVersion {version_id} not found")
        return version

    def _subtype(self, version: ItemVersion):
        return getattr(version, self.version_attr, None)

    def _require_subtype(self, version: ItemVersion):
        if version is None:
            raise ValidationError("Item has no current version")
        subtype = self._subtype(version)
        if subtype is None:
            raise ValidationError(
                f"ItemVersion {version.id} has no {self.version_attr} data"
            )
        return subtype

    @staticmethod
    def _clone_columns(instance, columns) -> dict:
        return {column: getattr(instance, column) for column in columns}
