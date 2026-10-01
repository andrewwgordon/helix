"""Product service (spec §14.3)."""

from app.models.audit import EVENT_CREATE, EVENT_REVISE
from app.models.business import Product
from app.models.reference import Market, ProductFamily
from app.services.base import Actor
from app.services.business_base import BusinessObjectService

CLONE_COLUMNS = ["product_family_id", "market_id", "platform", "release_target"]


class ProductService(BusinessObjectService):
    item_type_code = "Product"
    version_attr = "product"

    def create_product(
        self,
        item_number: str,
        actor: Actor = None,
        *,
        description: str = None,
        product_family: str = None,
        market: str = None,
        platform: str = None,
        release_target=None,
    ) -> Product:
        actor = self._actor(actor)
        family = self._lookup(ProductFamily, product_family)
        market_obj = self._lookup(Market, market)

        item = self.items.create_item(
            self.item_type_code, item_number, actor, commit=False
        )
        version = self.items.create_version(
            item.id, actor, description=description, commit=False
        )

        try:
            product = Product(
                item_version_id=version.id,
                product_family_id=getattr(family, "id", None),
                market_id=getattr(market_obj, "id", None),
                platform=platform,
                release_target=release_target,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
            )
            self.session.add(product)
            self.session.flush()
            self.audit.record(
                EVENT_CREATE, "Product", version.id, actor, item_id=item.id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return product

    def revise_product(
        self,
        item_id: int,
        change_type: str,
        actor: Actor = None,
        *,
        copy_relationships: bool = True,
        **overrides,
    ) -> Product:
        actor = self._actor(actor)
        current = self.items.get_current_version(item_id)
        current_product = self._require_subtype(current)

        data = self._clone_columns(current_product, CLONE_COLUMNS)
        data.update(overrides)

        new_version = self.items.revise_item(
            item_id,
            change_type,
            actor,
            copy_relationships=copy_relationships,
            commit=False,
        )
        try:
            product = Product(
                item_version_id=new_version.id,
                created_by_fk=actor.id,
                changed_by_fk=actor.id,
                **data,
            )
            self.session.add(product)
            self.audit.record(
                EVENT_REVISE, "Product", new_version.id, actor, item_id=item_id
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return product
