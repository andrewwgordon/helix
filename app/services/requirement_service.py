"""Requirement service (spec §14.6)."""

from app.models.audit import EVENT_CREATE, EVENT_REVISE
from app.models.business import Requirement
from app.models.reference import PriorityCode, VerificationMethod
from app.services.base import Actor
from app.services.business_base import BusinessObjectService

CLONE_COLUMNS = ["requirement_text", "verification_method_id", "priority_code_id"]


class RequirementService(BusinessObjectService):
    item_type_code = "Requirement"
    version_attr = "requirement"

    def create_requirement(
        self,
        item_number: str,
        actor: Actor = None,
        *,
        requirement_text: str,
        verification_method: str = None,
        priority: str = None,
        description: str = None,
    ) -> Requirement:
        actor = self._actor(actor)
        method = self._lookup(VerificationMethod, verification_method)
        priority_obj = self._lookup(PriorityCode, priority)

        item = self.items.create_item(
            self.item_type_code, item_number, actor, commit=False
        )
        version = self.items.create_version(
            item.id, actor, description=description, commit=False
        )

        try:
            requirement = Requirement(
                item_version_id=version.id,
                requirement_text=requirement_text,
                verification_method_id=getattr(method, "id", None),
                priority_code_id=getattr(priority_obj, "id", None),
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
            )
            self.session.add(requirement)
            self.session.flush()
            self.audit.record(
                EVENT_CREATE, "Requirement", version.id, actor, item_id=item.id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return requirement

    def revise_requirement(
        self,
        item_id: int,
        change_type: str,
        actor: Actor = None,
        *,
        copy_relationships: bool = True,
        **overrides,
    ) -> Requirement:
        actor = self._actor(actor)
        current = self.items.get_current_version(item_id)
        current_requirement = self._require_subtype(current)

        data = self._clone_columns(current_requirement, CLONE_COLUMNS)
        data.update(overrides)

        new_version = self.items.revise_item(
            item_id,
            change_type,
            actor,
            copy_relationships=copy_relationships,
            commit=False,
        )
        try:
            requirement = Requirement(
                item_version_id=new_version.id,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
                **data,
            )
            self.session.add(requirement)
            self.audit.record(
                EVENT_REVISE, "Requirement", new_version.id, actor, item_id=item_id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return requirement
