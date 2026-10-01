"""Service-backed create / revise forms (spec §15.3 / Phase 4).

These use FAB's standard ``SimpleFormView`` + ``DynamicForm`` (which render the
bundled ``appbuilder/general/model/edit.html`` template). They are registered
without a menu entry and launched from each entity's list page, so navigation
stays consistent.
"""

from flask import flash, g, redirect, request, url_for
from flask_appbuilder import SimpleFormView
from flask_appbuilder.fields import QuerySelectField
from flask_appbuilder.fieldwidgets import (
    BS3TextAreaFieldWidget,
    BS3TextFieldWidget,
    DatePickerWidget,
    Select2Widget,
)
from flask_appbuilder.forms import DynamicForm
from flask_wtf.file import FileField
from wtforms import DateField, DecimalField, HiddenField, StringField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional

from app import db
from app.models.reference import (
    MakeBuyCode,
    Market,
    PriorityCode,
    ProductFamily,
    UnitOfMeasure,
    VerificationMethod,
)
from app.services import (
    Actor,
    DocumentService,
    PartService,
    ProductService,
    RequirementService,
)
from app.services.exceptions import PlmError
from app.views.form_mixins import ServiceFormMixin


def _query(model):
    return lambda: db.session.query(model).filter_by(is_active=True).all()


def _pk(obj):
    return obj.id


class PartForm(DynamicForm):
    item_number = StringField(
        "Item number",
        validators=[DataRequired()],
        widget=BS3TextFieldWidget(),
        description="Stable business identity, unique within the Part item type.",
    )
    description = TextAreaField(
        "Description",
        widget=BS3TextAreaFieldWidget(),
        description="Optional summary of this revision.",
    )
    uom = QuerySelectField(
        "Unit of measure",
        query_func=_query(UnitOfMeasure),
        get_pk_func=_pk,
        get_label="name",
        validators=[DataRequired()],
        widget=Select2Widget(),
        description="Stock unit of measure.",
    )
    make_buy = QuerySelectField(
        "Make / Buy",
        query_func=_query(MakeBuyCode),
        get_pk_func=_pk,
        get_label="name",
        allow_blank=True,
        blank_text="--",
        description="Sourcing decision: Make, Buy or Make-or-Buy.",
    )
    weight = DecimalField(
        "Weight",
        validators=[Optional(), NumberRange(min=0)],
        description="Part weight in the selected weight unit.",
    )
    material = StringField(
        "Material",
        widget=BS3TextFieldWidget(),
        description="Primary material.",
    )


class PartCreateView(ServiceFormMixin, SimpleFormView):
    route_base = "/parts/create"
    form = PartForm
    form_title = "Create Part"
    edit_fieldsets = [
        ("Identification", {"fields": ["item_number", "description"]}),
        ("Classification", {"fields": ["uom", "make_buy"]}),
        ("Physical", {"fields": ["weight", "material"]}),
    ]

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            result = PartService(db.session, actor).create_part(
                form.item_number.data,
                actor,
                uom_code=form.uom.data.code,
                make_buy=form.make_buy.data.code if form.make_buy.data else None,
                weight=form.weight.data,
                material=form.material.data or None,
                description=form.description.data or None,
            )
            flash(
                f"Created part {result.item_version.item.item_number}.",
                "success",
            )
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")
        return redirect(url_for("PartModelView.list"))


class ProductForm(DynamicForm):
    item_number = StringField(
        "Item number",
        validators=[DataRequired()],
        widget=BS3TextFieldWidget(),
        description="Stable business identity, unique within the Product item type.",
    )
    description = TextAreaField(
        "Description",
        widget=BS3TextAreaFieldWidget(),
        description="Optional summary of this revision.",
    )
    product_family = QuerySelectField(
        "Product family",
        query_func=_query(ProductFamily),
        get_pk_func=_pk,
        get_label="name",
        allow_blank=True,
        blank_text="--",
        description="Product family grouping.",
    )
    market = QuerySelectField(
        "Market",
        query_func=_query(Market),
        get_pk_func=_pk,
        get_label="name",
        allow_blank=True,
        blank_text="--",
        description="Target market.",
    )
    platform = StringField(
        "Platform",
        widget=BS3TextFieldWidget(),
        description="Platform identifier.",
    )
    release_target = DateField(
        "Release target",
        validators=[Optional()],
        widget=DatePickerWidget(),
        description="Target release date.",
    )


class ProductCreateView(ServiceFormMixin, SimpleFormView):
    route_base = "/products/create"
    form = ProductForm
    form_title = "Create Product"
    edit_fieldsets = [
        ("Identification", {"fields": ["item_number", "description"]}),
        ("Classification", {"fields": ["product_family", "market"]}),
        ("Planning", {"fields": ["platform", "release_target"]}),
    ]

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            result = ProductService(db.session, actor).create_product(
                form.item_number.data,
                actor,
                description=form.description.data or None,
                product_family=(
                    form.product_family.data.code if form.product_family.data else None
                ),
                market=form.market.data.code if form.market.data else None,
                platform=form.platform.data or None,
                release_target=form.release_target.data,
            )
            flash(
                f"Created product {result.item_version.item.item_number}.",
                "success",
            )
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")
        return redirect(url_for("ProductModelView.list"))


class RequirementForm(DynamicForm):
    item_number = StringField(
        "Item number",
        validators=[DataRequired()],
        widget=BS3TextFieldWidget(),
        description="Stable business identity, e.g. REQ-0001.",
    )
    description = TextAreaField(
        "Description",
        widget=BS3TextAreaFieldWidget(),
        description="Optional summary or classification of this revision.",
    )
    requirement_text = TextAreaField(
        "Requirement text",
        validators=[DataRequired()],
        widget=BS3TextAreaFieldWidget(),
        description="The requirement statement. Use 'shall' wording.",
    )
    verification_method = QuerySelectField(
        "Verification method",
        query_func=_query(VerificationMethod),
        get_pk_func=_pk,
        get_label="name",
        allow_blank=True,
        blank_text="--",
        description="How the requirement is verified.",
    )
    priority = QuerySelectField(
        "Priority",
        query_func=_query(PriorityCode),
        get_pk_func=_pk,
        get_label="name",
        allow_blank=True,
        blank_text="--",
        description="Requirement priority.",
    )


class RequirementCreateView(ServiceFormMixin, SimpleFormView):
    route_base = "/requirements/create"
    form = RequirementForm
    form_title = "Create Requirement"
    edit_fieldsets = [
        ("Identification", {"fields": ["item_number", "description"]}),
        (
            "Requirement",
            {"fields": ["requirement_text", "verification_method", "priority"]},
        ),
    ]

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            result = RequirementService(db.session, actor).create_requirement(
                form.item_number.data,
                actor,
                requirement_text=form.requirement_text.data,
                verification_method=(
                    form.verification_method.data.code
                    if form.verification_method.data
                    else None
                ),
                priority=form.priority.data.code if form.priority.data else None,
                description=form.description.data or None,
            )
            flash(
                f"Created requirement {result.item_version.item.item_number}.",
                "success",
            )
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")
        return redirect(url_for("RequirementModelView.list"))


class DocumentForm(DynamicForm):
    item_number = StringField(
        "Item number",
        validators=[DataRequired()],
        widget=BS3TextFieldWidget(),
        description="Stable business identity, e.g. DOC-0001.",
    )
    description = TextAreaField(
        "Description",
        widget=BS3TextAreaFieldWidget(),
        description="Optional summary of this revision.",
    )
    file = FileField(
        "File",
        validators=[DataRequired()],
        description="Allowed file types are configured by the administrator.",
    )


class DocumentCreateView(ServiceFormMixin, SimpleFormView):
    route_base = "/documents/create"
    form = DocumentForm
    form_title = "Create Document"
    edit_fieldsets = [
        ("Identification", {"fields": ["item_number", "description"]}),
        ("File", {"fields": ["file"]}),
    ]

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        try:
            result = DocumentService(db.session, actor).create_document(
                form.item_number.data,
                actor,
                uploaded_file=form.file.data,
                description=form.description.data or None,
            )
            flash(
                f"Created document {result.item_version.item.item_number}.",
                "success",
            )
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")
        return redirect(url_for("DocumentModelView.list"))


class DocumentReviseForm(DynamicForm):
    item_id = HiddenField()
    change_type = HiddenField()
    description = TextAreaField(
        "Reason / description",
        widget=BS3TextAreaFieldWidget(),
        description="Reason for the revision (recorded on the new revision).",
    )
    file = FileField(
        "Replacement file (optional)",
        description="Leave blank to clone the current document metadata.",
    )


class DocumentReviseView(ServiceFormMixin, SimpleFormView):
    route_base = "/documents/revise"
    form = DocumentReviseForm
    form_title = "Revise Document"
    edit_fieldsets = [
        ("Revision", {"fields": ["description", "file"]}),
    ]

    def form_get(self, form):
        form.item_id.data = request.args.get("item_id")
        form.change_type.data = request.args.get("change_type", "minor")

    def form_post(self, form):
        actor = Actor.from_user(g.user)
        uploaded = form.file.data
        new_file = uploaded if (uploaded and getattr(uploaded, "filename", "")) else None
        try:
            result = DocumentService(db.session, actor).revise_document(
                int(form.item_id.data),
                form.change_type.data or "minor",
                actor,
                new_file=new_file,
                description=form.description.data or None,
            )
            flash(
                f"Created revision {result.item_version.revision_label}.",
                "success",
            )
        except PlmError as exc:
            if self.attach_field_error(form, exc):
                return self.render_service_form(form)
            flash(str(exc), "danger")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("DocumentModelView.list"))
