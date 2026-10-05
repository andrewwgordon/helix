"""Product structure browser and editor (spec §15.5 approved exceptions).

``StructureTreeView`` is one of the two sanctioned custom views (spec §3.3.1):
no bundled FAB widget renders an expandable recursive structure tree. It
supports both directions - downstream (BOM) and upstream (where-used) - and is
launched from actions, never from the main menu.

``StructureChildAddView`` uses FAB's standard ``SimpleFormView`` + a
``QuerySelectField`` (Select2) calling ``RelationshipService``.
"""

from flask import flash, g, redirect, request, url_for
from flask_appbuilder import BaseView, SimpleFormView, expose, has_access
from flask_appbuilder.fields import QuerySelectField
from flask_appbuilder.fieldwidgets import BS3TextFieldWidget, Select2Widget
from flask_appbuilder.forms import DynamicForm
from wtforms import DecimalField, HiddenField, StringField
from wtforms.validators import DataRequired, NumberRange, Optional

from app import db
from app.models.core import Item, ItemVersion
from app.models.reference import ItemType
from app.services import Actor, RelationshipService
from app.services.exceptions import PlmError
from app.views.form_mixins import ServiceFormMixin


class StructureTreeView(BaseView):
    route_base = "/structures"
    default_view = "tree"

    @expose("/tree")
    @has_access
    def tree(self):
        version_id = request.args.get("version_id", type=int)
        direction = request.args.get("direction", "down")
        if version_id is None:
            flash("No structure root was selected.", "warning")
            return redirect(request.referrer or "/")

        service = RelationshipService(db.session)
        try:
            root = service.build_tree(version_id, direction=direction)
        except PlmError as exc:
            flash(str(exc), "danger")
            return redirect(request.referrer or "/")

        downstream = direction == "down"
        if downstream:
            title = "Product structure"
            back_url = url_for("ProductModelView.list")
            back_label = "Back to products"
        else:
            title = "Where used"
            back_url = url_for("ItemVersionModelView.list")
            back_label = "Back to revisions"

        other_direction = "up" if downstream else "down"
        return self.render_template(
            "plm/structure_tree.html",
            root=root,
            direction=direction,
            title=title,
            back_url=back_url,
            back_label=back_label,
            version_id=version_id,
            toggle_url=url_for(
                "StructureTreeView.tree",
                version_id=version_id,
                direction=other_direction,
            ),
            toggle_label="Show where used" if downstream else "Show structure",
        )


def _child_candidates():
    """Items that have a current version and can be structure children.

    Parts/Products extend the product structure (BOM); Functions extend the
    functional breakdown (performed by the parent product, or nested under a
    parent function).
    """
    return (
        db.session.query(Item)
        .join(ItemType, Item.item_type_id == ItemType.id)
        .filter(ItemType.code.in_(("Part", "Product", "Function")))
        .filter(Item.current_version_id.isnot(None))
        .order_by(Item.item_number.asc())
        .all()
    )


def _child_label(item):
    return f"{item.item_number} [{item.item_type.code}]"


class StructureChildForm(DynamicForm):
    parent_version_id = HiddenField()
    child = QuerySelectField(
        "Child item",
        query_func=_child_candidates,
        get_pk_func=lambda item: item.current_version_id,
        get_label=_child_label,
        validators=[DataRequired()],
        widget=Select2Widget(),
        description=(
            "Only Part/Product/Function items with a current revision are "
            "listed. A function child under a product records a PERFORMS "
            "link; under a function it extends the functional breakdown."
        ),
    )
    quantity = DecimalField(
        "Quantity",
        validators=[Optional(), NumberRange(min=0)],
        description="Defaults to 1 when left blank.",
    )
    find_number = StringField(
        "Find number",
        widget=BS3TextFieldWidget(),
        description="Optional position identifier within the parent.",
    )


class StructureChildAddView(ServiceFormMixin, SimpleFormView):
    route_base = "/structures/add-child"
    form = StructureChildForm
    form_title = "Add structure child"
    edit_fieldsets = [
        ("Child", {"fields": ["child", "quantity", "find_number"]}),
    ]

    def form_get(self, form):
        form.parent_version_id.data = request.args.get("parent_version_id")

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            parent_version_id = int(form.parent_version_id.data)
        except (TypeError, ValueError):
            flash("Missing parent version.", "danger")
            return redirect(url_for("ItemModelView.list"))

        child_item = form.child.data
        parent_version = db.session.get(ItemVersion, parent_version_id)
        if parent_version is None:
            flash("Parent version not found.", "danger")
            return redirect(url_for("ItemModelView.list"))

        # Containment semantics by item type: product structure (BOM) and the
        # functional breakdown both use structural CONTAINS edges, while a
        # function attached directly to a product is a PERFORMS link.
        parent_type = parent_version.item.item_type.code
        if parent_type == "Function":
            relationship_type = "CONTAINS"
        elif child_item.item_type.code == "Function":
            relationship_type = "PERFORMS"
        else:
            relationship_type = "CONTAINS"

        try:
            RelationshipService(db.session, actor).add_relationship(
                parent_version_id,
                child_item.current_version_id,
                relationship_type,
                actor,
                quantity=form.quantity.data,
                find_number=form.find_number.data or None,
            )
            flash("Child added to the structure.", "success")
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")

        return redirect(
            url_for("StructureTreeView.tree", version_id=parent_version_id)
        )


def _fulfilling_part_candidates():
    """Parts with a current revision that can fulfil a function."""
    return (
        db.session.query(Item)
        .join(ItemType, Item.item_type_id == ItemType.id)
        .filter(ItemType.code == "Part")
        .filter(Item.current_version_id.isnot(None))
        .order_by(Item.item_number.asc())
        .all()
    )


class FunctionFulfillmentForm(DynamicForm):
    function_version_id = HiddenField()
    part = QuerySelectField(
        "Fulfilling part",
        query_func=_fulfilling_part_candidates,
        get_pk_func=lambda item: item.current_version_id,
        get_label=_child_label,
        validators=[DataRequired()],
        widget=Select2Widget(),
        description="Only Part items with a current revision are listed.",
    )


class FunctionFulfillmentAddView(ServiceFormMixin, SimpleFormView):
    """Link a part that fulfils a function (a FULFILLS edge)."""

    route_base = "/functions/add-fulfillment"
    form = FunctionFulfillmentForm
    form_title = "Add fulfilling part"
    edit_fieldsets = [
        ("Fulfillment", {"fields": ["part"]}),
    ]

    def form_get(self, form):
        form.function_version_id.data = request.args.get("function_version_id")

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            function_version_id = int(form.function_version_id.data)
        except (TypeError, ValueError):
            flash("Missing function version.", "danger")
            return redirect(url_for("FunctionModelView.list"))

        part_item = form.part.data
        try:
            RelationshipService(db.session, actor).add_relationship(
                part_item.current_version_id,
                function_version_id,
                "FULFILLS",
                actor,
            )
            flash("Part linked as fulfilling the function.", "success")
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")

        return redirect(
            url_for("FunctionModelView.show", pk=function_version_id)
        )
