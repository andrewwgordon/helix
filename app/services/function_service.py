"""Function service (functional breakdown object).

Functions are versioned business objects like parts/requirements: a Function
row shares the primary key of its ``ItemVersion``. A function breaks down into
child functions through structural ``CONTAINS`` relationships, a product
*performs* functions (``PERFORMS``) and a part *fulfils* functions
(``FULFILLS``) - see :mod:`app.services.relationship_service`.
"""

from app.models.audit import EVENT_CREATE, EVENT_REVISE
from app.models.business import Function
from app.services.base import Actor
from app.services.business_base import BusinessObjectService

CLONE_COLUMNS = ["function_text"]


class FunctionService(BusinessObjectService):
    item_type_code = "Function"
    version_attr = "function"

    def create_function(
        self,
        item_number: str,
        actor: Actor = None,
        *,
        function_text: str,
        description: str = None,
    ) -> Function:
        actor = self._actor(actor)

        item = self.items.create_item(
            self.item_type_code, item_number, actor, commit=False
        )
        version = self.items.create_version(
            item.id, actor, description=description, commit=False
        )

        try:
            function = Function(
                item_version_id=version.id,
                function_text=function_text,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
            )
            self.session.add(function)
            self.session.flush()
            self.audit.record(
                EVENT_CREATE, "Function", version.id, actor, item_id=item.id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return function

    def revise_function(
        self,
        item_id: int,
        change_type: str,
        actor: Actor = None,
        *,
        copy_relationships: bool = True,
        **overrides,
    ) -> Function:
        actor = self._actor(actor)
        current = self.items.get_current_version(item_id)
        current_function = self._require_subtype(current)

        data = self._clone_columns(current_function, CLONE_COLUMNS)
        data.update(overrides)

        new_version = self.items.revise_item(
            item_id,
            change_type,
            actor,
            copy_relationships=copy_relationships,
            commit=False,
        )
        try:
            function = Function(
                item_version_id=new_version.id,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
                **data,
            )
            self.session.add(function)
            self.audit.record(
                EVENT_REVISE, "Function", new_version.id, actor, item_id=item_id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return function
