"""Baseline views (spec §15.4).

Read-only after freeze. Creation goes through a standard ``SimpleFormView``
that calls ``BaselineService``; freezing is a one-way service-backed action.
"""

from flask import flash, g, redirect, request, url_for
from flask_appbuilder import BaseView, ModelView, SimpleFormView, expose, has_access
from flask_appbuilder.actions import action
from flask_appbuilder.fields import QuerySelectField
from flask_appbuilder.fieldwidgets import (
    BS3TextAreaFieldWidget,
    BS3TextFieldWidget,
    Select2Widget,
)
from flask_appbuilder.forms import DynamicForm
from flask_appbuilder.models.sqla.interface import SQLAInterface
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import DataRequired

from app import db
from app.models.baseline import Baseline, BaselineMember
from app.models.business import Product
from app.models.core import ItemVersion
from app.models.reference import LifecycleState
from app.services import Actor, BaselineService
from app.services.exceptions import PlmError
from app.views.action_utils import as_items, first_item
from app.views.form_mixins import ServiceFormMixin
from app.views.formatters import baseline_status, item_version_link, lifecycle_state


class BaselineMemberModelView(ModelView):
    datamodel = SQLAInterface(BaselineMember)
    route_base = "/baselinemembers"
    list_columns = [
        "item_version.item.item_number",
        "item_version.revision_label",
        "item_version.lifecycle_state",
        "quantity",
        "find_number",
    ]
    show_columns = [
        "item_version.item.item_number",
        "item_version.revision_label",
        "item_version.lifecycle_state",
        "quantity",
        "find_number",
    ]
    search_columns = ["item_version", "find_number"]
    base_order = ("id", "asc")
    page_size = 100
    formatters_columns = {"item_version.lifecycle_state": lifecycle_state}
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = {
        "item_version.item.item_number": "Item",
        "item_version.revision_label": "Revision",
        "item_version.lifecycle_state": "State",
        "quantity": "Quantity",
        "find_number": "Find number",
    }
    show_fieldsets = [
        (
            "Member",
            {
                "fields": [
                    "item_version.item.item_number",
                    "item_version.revision_label",
                    "item_version.lifecycle_state",
                ]
            },
        ),
        ("Structure", {"fields": ["quantity", "find_number"]}),
    ]


class BaselineModelView(ModelView):
    datamodel = SQLAInterface(Baseline)
    route_base = "/baselines"
    list_columns = [
        "baseline_number",
        "baseline_name",
        "product_version",
        "status",
        "frozen_at",
        "created_on",
    ]
    show_columns = [
        "baseline_number",
        "baseline_name",
        "product_version",
        "status",
        "frozen_at",
        "description",
        "created_on",
    ]
    search_columns = ["baseline_number", "baseline_name", "status"]
    base_order = ("baseline_number", "asc")
    page_size = 50
    formatters_columns = {
        "status": baseline_status,
        "product_version": item_version_link,
    }
    base_permissions = ["can_list", "can_show", "can_add", "freeze", "compare"]
    exclude_route_methods = {"edit", "delete"}
    related_views = [BaselineMemberModelView]
    label_columns = {
        "baseline_number": "Number",
        "baseline_name": "Name",
        "product_version": "Product version",
        "status": "Status",
        "frozen_at": "Frozen at",
        "description": "Description",
        "created_on": "Created",
    }
    show_fieldsets = [
        (
            "Baseline",
            {"fields": ["baseline_number", "baseline_name", "product_version"]},
        ),
        ("Status", {"fields": ["status", "frozen_at"]}),
        ("Details", {"fields": ["description"]}),
        ("Audit", {"fields": ["created_on"], "expanded": False}),
    ]
    description_columns = {
        "baseline_number": "Unique baseline identifier.",
        "product_version": "Product revision this baseline captures.",
        "status": "DRAFT baselines are editable; FROZEN are immutable.",
    }

    @expose("/add/", methods=["GET"])
    @has_access
    def add(self):
        return redirect(url_for("BaselineCreateView.this_form_get"))

    @action(
        "freeze",
        "Freeze",
        "Freeze this baseline? It becomes immutable.",
        "fa-lock",
        single=True,
    )
    def freeze(self, item):
        actor = Actor.from_user(g.user)
        service = BaselineService(db.session, actor)
        frozen = 0
        for baseline in as_items(item):
            try:
                service.freeze_baseline(baseline.id, actor)
                frozen += 1
            except PlmError as exc:
                flash(str(exc), "danger")
                return redirect(self.get_redirect())
        if frozen:
            flash(f"Frozen {frozen} baseline(s).", "success")
        return redirect(self.get_redirect())

    @action(
        "compare",
        "Compare",
        "Compare this baseline with another?",
        "fa-columns",
        multiple=False,
        single=True,
    )
    def compare(self, item):
        baseline = first_item(item)
        return redirect(url_for("BaselineCompareView.compare", a=baseline.id))


def _releasable_products():
    return (
        db.session.query(Product)
        .join(ItemVersion, Product.item_version_id == ItemVersion.id)
        .join(LifecycleState, ItemVersion.lifecycle_state_id == LifecycleState.id)
        .filter(LifecycleState.is_releasable.is_(True))
        .all()
    )


def _product_label(product):
    version = product.item_version
    return (
        f"{version.item.item_number} {version.revision_label} "
        f"({version.lifecycle_state.name})"
    )


class BaselineForm(DynamicForm):
    baseline_number = StringField(
        "Baseline number",
        validators=[DataRequired()],
        widget=BS3TextFieldWidget(),
        description="Unique baseline identifier, e.g. BL-0001.",
    )
    baseline_name = StringField(
        "Baseline name",
        validators=[DataRequired()],
        widget=BS3TextFieldWidget(),
        description="Human-readable name for the frozen configuration.",
    )
    product = QuerySelectField(
        "Product version",
        query_func=_releasable_products,
        get_pk_func=lambda product: product.item_version_id,
        get_label=_product_label,
        validators=[DataRequired()],
        widget=Select2Widget(),
        description="Only releasable (Approved/Released) product revisions are listed.",
    )
    description = TextAreaField(
        "Description",
        widget=BS3TextAreaFieldWidget(),
        description="Optional purpose or scope of the baseline.",
    )
    freeze_immediately = BooleanField(
        "Freeze immediately",
        description="Freeze the baseline on creation. Freezing is one-way.",
    )


class BaselineCreateView(ServiceFormMixin, SimpleFormView):
    route_base = "/baselines/create"
    form = BaselineForm
    form_title = "Create Baseline"
    edit_fieldsets = [
        ("Baseline", {"fields": ["baseline_number", "baseline_name", "product"]}),
        ("Options", {"fields": ["description", "freeze_immediately"]}),
    ]

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            baseline = BaselineService(db.session, actor).create_baseline(
                form.product.data.item_version_id,
                form.baseline_number.data,
                form.baseline_name.data,
                actor,
                description=form.description.data or None,
                freeze_immediately=bool(form.freeze_immediately.data),
            )
            flash(f"Created baseline {baseline.baseline_number}.", "success")
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")
        return redirect(url_for("BaselineModelView.list"))


class BaselineCompareView(BaseView):
    """Sanctioned custom view (spec §15.5): side-by-side computed diff."""

    route_base = "/baselines/compare"
    default_view = "compare"

    @expose("/")
    @has_access
    def compare(self):
        a_id = request.args.get("a", type=int)
        b_id = request.args.get("b", type=int)
        baselines = (
            db.session.query(Baseline)
            .order_by(Baseline.baseline_number.asc())
            .all()
        )

        diff = None
        baseline_a = baseline_b = None
        if a_id and b_id:
            try:
                diff = BaselineService(db.session).compare_baselines(a_id, b_id)
                baseline_a = db.session.get(Baseline, a_id)
                baseline_b = db.session.get(Baseline, b_id)
            except PlmError as exc:
                flash(str(exc), "danger")

        return self.render_template(
            "plm/baseline_compare.html",
            baselines=baselines,
            baseline_a=baseline_a,
            baseline_b=baseline_b,
            diff=diff,
            a_id=a_id,
            b_id=b_id,
        )
