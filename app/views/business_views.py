"""Business-object ModelViews (spec §15.3).

Standard FAB list/show views. All writes are routed through the service layer:
- ``add`` redirects to a service-backed ``SimpleFormView`` create form.
- revise buttons either call ``*Service.revise_*`` directly or open the document
  revise form when a replacement file may be uploaded.
"""

from flask import flash, g, redirect, url_for
from flask_appbuilder import ModelView, expose, has_access
from flask_appbuilder.actions import action
from flask_appbuilder.models.sqla.interface import SQLAInterface

from app import db
from app.models.business import Document, Part, Product, Requirement
from app.services import (
    Actor,
    PartService,
    ProductService,
    RequirementService,
)
from app.services.exceptions import PlmError
from app.views.action_utils import as_items, first_item
from app.views.filters import current_version_filter
from app.views.formatters import lifecycle_state, make_buy_code, priority_code

_VERSION_COLUMNS = [
    "item_version.item.item_number",
    "item_version.revision_label",
    "item_version.lifecycle_state",
]
_VERSION_LABELS = {
    "item_version.item.item_number": "Item",
    "item_version.revision_label": "Revision",
    "item_version.lifecycle_state": "State",
    "created_on": "Created",
}
_IDENTIFICATION_FIELDSET = ("Identification", {"fields": _VERSION_COLUMNS})
_AUDIT_FIELDSET = ("Audit", {"fields": ["created_on"], "expanded": False})


class RevisionHistoryMixin:
    """Adds a standard "Revisions" action to a business-object ModelView.

    Business lists show only the current revision (``base_filters``); this
    action gives one-click access to the full history in the standard
    ``ItemVersionModelView`` rather than a parallel custom page.
    """

    @action(
        "revisions",
        "Revisions",
        "Show all revisions of this item?",
        "fa-code-fork",
        multiple=False,
        single=True,
    )
    def revisions(self, item):
        item = first_item(item)
        return redirect(
            url_for("ItemVersionModelView.list")
            + f"?_flt_0_item={item.item_version.item_id}"
        )


class ReviseActionsMixin:
    """Adds service-backed major/minor revision buttons to a ModelView."""

    def do_revise(self, item, change_type, actor):
        raise NotImplementedError

    def _revise_and_redirect(self, item, change_type):
        actor = Actor.from_user(g.user)
        labels = []
        for record in as_items(item):
            try:
                new = self.do_revise(record, change_type, actor)
                labels.append(new.item_version.revision_label)
            except PlmError as exc:
                flash(str(exc), "danger")
                return redirect(self.get_redirect())
        if len(labels) == 1:
            flash(f"Created revision {labels[0]}.", "success")
        elif labels:
            flash(f"Created revisions {', '.join(labels)}.", "success")
        return redirect(self.get_redirect())

    @action(
        "revise_major",
        "Revise (major)",
        "Create a new major revision of this item?",
        "fa-level-up",
        single=True,
    )
    def revise_major(self, item):
        return self._revise_and_redirect(item, "major")

    @action(
        "revise_minor",
        "Revise (minor)",
        "Create a new minor revision of this item?",
        "fa-level-up",
        single=True,
    )
    def revise_minor(self, item):
        return self._revise_and_redirect(item, "minor")


class PartModelView(RevisionHistoryMixin, ReviseActionsMixin, ModelView):
    datamodel = SQLAInterface(Part)
    route_base = "/parts"
    list_columns = _VERSION_COLUMNS + ["unit_of_measure", "make_buy_code", "material"]
    show_columns = _VERSION_COLUMNS + [
        "unit_of_measure",
        "make_buy_code",
        "weight",
        "weight_uom",
        "material",
        "created_on",
    ]
    search_columns = ["item_version", "unit_of_measure", "material"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.lifecycle_state": lifecycle_state,
        "make_buy_code": make_buy_code,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revisions",
        "revise_major",
        "revise_minor",
    ]
    label_columns = dict(
        _VERSION_LABELS,
        unit_of_measure="UoM",
        make_buy_code="Make / Buy",
        weight_uom="Weight UoM",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        ("Classification", {"fields": ["unit_of_measure", "make_buy_code"]}),
        ("Physical", {"fields": ["weight", "weight_uom", "material"]}),
        _AUDIT_FIELDSET,
    ]
    description_columns = {
        "unit_of_measure": "Stock unit of measure.",
        "make_buy_code": "Sourcing decision: Make, Buy or Make-or-Buy.",
        "weight": "Part weight in the selected weight unit.",
        "material": "Primary material.",
    }

    exclude_route_methods = {"edit", "delete"}

    @expose("/add/", methods=["GET"])
    @has_access
    def add(self):
        return redirect(url_for("PartCreateView.this_form_get"))

    def do_revise(self, item, change_type, actor):
        return PartService(db.session, actor).revise_part(
            item.item_version.item_id, change_type, actor
        )


class DocumentModelView(RevisionHistoryMixin, ModelView):
    datamodel = SQLAInterface(Document)
    route_base = "/documents"
    list_columns = _VERSION_COLUMNS + ["file_name", "mime_type", "file_size"]
    show_columns = _VERSION_COLUMNS + [
        "file_name",
        "mime_type",
        "file_size",
        "checksum_sha256",
        "created_on",
    ]
    search_columns = ["item_version", "file_name"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {"item_version.lifecycle_state": lifecycle_state}
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revisions",
        "revise_major",
        "revise_minor",
    ]
    label_columns = dict(
        _VERSION_LABELS,
        file_name="File",
        mime_type="Type",
        file_size="Size",
        checksum_sha256="SHA-256",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        (
            "File",
            {"fields": ["file_name", "mime_type", "file_size", "checksum_sha256"]},
        ),
        _AUDIT_FIELDSET,
    ]
    description_columns = {
        "file_name": "Original uploaded file name.",
        "checksum_sha256": "SHA-256 checksum of the stored file.",
    }

    exclude_route_methods = {"edit", "delete"}

    @expose("/add/", methods=["GET"])
    @has_access
    def add(self):
        return redirect(url_for("DocumentCreateView.this_form_get"))

    @action(
        "revise_major",
        "Revise (major)",
        "Create a new major revision of this document?",
        "fa-level-up",
        multiple=False,
        single=True,
    )
    def revise_major(self, item):
        item = first_item(item)
        return redirect(
            url_for(
                "DocumentReviseView.this_form_get",
                item_id=item.item_version.item_id,
                change_type="major",
            )
        )

    @action(
        "revise_minor",
        "Revise (minor)",
        "Create a new minor revision of this document?",
        "fa-level-up",
        multiple=False,
        single=True,
    )
    def revise_minor(self, item):
        item = first_item(item)
        return redirect(
            url_for(
                "DocumentReviseView.this_form_get",
                item_id=item.item_version.item_id,
                change_type="minor",
            )
        )


class RequirementModelView(RevisionHistoryMixin, ReviseActionsMixin, ModelView):
    datamodel = SQLAInterface(Requirement)
    route_base = "/requirements"
    list_columns = _VERSION_COLUMNS + [
        "requirement_text",
        "verification_method",
        "priority_code",
    ]
    show_columns = _VERSION_COLUMNS + [
        "requirement_text",
        "verification_method",
        "priority_code",
        "created_on",
    ]
    search_columns = ["item_version", "requirement_text", "priority_code"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.lifecycle_state": lifecycle_state,
        "priority_code": priority_code,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revisions",
        "revise_major",
        "revise_minor",
    ]
    label_columns = dict(
        _VERSION_LABELS,
        requirement_text="Requirement",
        verification_method="Verification",
        priority_code="Priority",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        ("Requirement", {"fields": ["requirement_text"]}),
        ("Verification", {"fields": ["verification_method", "priority_code"]}),
        _AUDIT_FIELDSET,
    ]
    description_columns = {
        "requirement_text": "The requirement statement.",
        "verification_method": "How the requirement is verified.",
        "priority_code": "Requirement priority.",
    }

    exclude_route_methods = {"edit", "delete"}

    @expose("/add/", methods=["GET"])
    @has_access
    def add(self):
        return redirect(url_for("RequirementCreateView.this_form_get"))

    def do_revise(self, item, change_type, actor):
        return RequirementService(db.session, actor).revise_requirement(
            item.item_version.item_id, change_type, actor
        )


class ProductModelView(RevisionHistoryMixin, ReviseActionsMixin, ModelView):
    datamodel = SQLAInterface(Product)
    route_base = "/products"
    list_columns = _VERSION_COLUMNS + [
        "product_family",
        "market",
        "platform",
        "release_target",
    ]
    show_columns = _VERSION_COLUMNS + [
        "product_family",
        "market",
        "platform",
        "release_target",
        "created_on",
    ]
    search_columns = ["item_version", "platform", "product_family"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {"item_version.lifecycle_state": lifecycle_state}
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revisions",
        "revise_major",
        "revise_minor",
        "structure",
        "add_child",
    ]
    label_columns = dict(
        _VERSION_LABELS,
        product_family="Product family",
        market="Market",
        release_target="Release target",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        ("Classification", {"fields": ["product_family", "market"]}),
        ("Planning", {"fields": ["platform", "release_target"]}),
        _AUDIT_FIELDSET,
    ]
    description_columns = {
        "product_family": "Product family grouping.",
        "market": "Target market.",
        "platform": "Platform identifier.",
        "release_target": "Target release date.",
    }

    exclude_route_methods = {"edit", "delete"}

    @expose("/add/", methods=["GET"])
    @has_access
    def add(self):
        return redirect(url_for("ProductCreateView.this_form_get"))

    @action(
        "structure",
        "Structure",
        "Browse the product structure?",
        "fa-sitemap",
        multiple=False,
        single=True,
    )
    def structure(self, item):
        item = first_item(item)
        return redirect(
            url_for(
                "StructureTreeView.tree",
                version_id=item.item_version_id,
                direction="down",
            )
        )

    @action(
        "add_child",
        "Add child",
        "Add a child to this product?",
        "fa-plus",
        multiple=False,
        single=True,
    )
    def add_child(self, item):
        item = first_item(item)
        return redirect(
            url_for(
                "StructureChildAddView.this_form_get",
                parent_version_id=item.item_version_id,
            )
        )

    def do_revise(self, item, change_type, actor):
        return ProductService(db.session, actor).revise_product(
            item.item_version.item_id, change_type, actor
        )
