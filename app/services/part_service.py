"""Part service (spec §14.4)."""

from app.models.audit import EVENT_CREATE, EVENT_REVISE
from app.models.business import Part
from app.models.reference import MakeBuyCode, UnitOfMeasure
from app.services.base import Actor
from app.services.business_base import BusinessObjectService

CLONE_COLUMNS = [
    "unit_of_measure_id",
    "make_buy_code_id",
    "weight",
    "weight_uom_id",
    "material",
]


class PartService(BusinessObjectService):
    item_type_code = "Part"
    version_attr = "part"

    def create_part(
        self,
        item_number: str,
        actor: Actor = None,
        *,
        uom_code: str,
        make_buy: str = None,
        weight=None,
        weight_uom: str = None,
        material: str = None,
        description: str = None,
    ) -> Part:
        actor = self._actor(actor)
        uom = self._lookup(UnitOfMeasure, uom_code, required=True)
        make_buy_obj = self._lookup(MakeBuyCode, make_buy)
        weight_uom_obj = self._lookup(UnitOfMeasure, weight_uom)

        item = self.items.create_item(
            self.item_type_code, item_number, actor, commit=False
        )
        version = self.items.create_version(
            item.id, actor, description=description, commit=False
        )

        try:
            part = Part(
                item_version_id=version.id,
                unit_of_measure_id=uom.id,
                make_buy_code_id=getattr(make_buy_obj, "id", None),
                weight=weight,
                weight_uom_id=getattr(weight_uom_obj, "id", None),
                material=material,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
            )
            self.session.add(part)
            self.session.flush()
            self.audit.record(
                EVENT_CREATE,
                "Part",
                version.id,
                actor,
                item_id=item.id,
                to_value=uom.code,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return part

    def revise_part(
        self,
        item_id: int,
        change_type: str,
        actor: Actor = None,
        *,
        copy_relationships: bool = True,
        **overrides,
    ) -> Part:
        actor = self._actor(actor)
        current = self.items.get_current_version(item_id)
        current_part = self._require_subtype(current)

        data = self._clone_columns(current_part, CLONE_COLUMNS)
        data.update(overrides)

        new_version = self.items.revise_item(
            item_id,
            change_type,
            actor,
            copy_relationships=copy_relationships,
            commit=False,
        )
        try:
            part = Part(
                item_version_id=new_version.id,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
                **data,
            )
            self.session.add(part)
            self.audit.record(
                EVENT_REVISE, "Part", new_version.id, actor, item_id=item_id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return part
