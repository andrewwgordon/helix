"""Business-object ModelViews (spec §15.3).

Standard FAB list/show views. All writes are routed through the service layer:
- ``add`` redirects to a service-backed ``SimpleFormView`` create form.
- revise buttons either call ``*Service.revise_*`` directly or open the document
  revise form when a replacement file may be uploaded.
"""

from flask import (
    current_app,
    flash,
    g,
    redirect,
    send_from_directory,
    url_for,
)
from flask_appbuilder import ModelView, expose, has_access
from flask_appbuilder.actions import action
from flask_appbuilder.models.sqla.interface import SQLAInterface

from app import db
from app.models.business import Document, Function, Part, Product, Requirement
from app.services import (
    Actor,
    FunctionService,
    PartService,
    ProductService,
    RequirementService,
)
from app.services.exceptions import PlmError
from app.views.action_utils import as_items, first_item
from app.views.columns import (
    _AUDIT_FIELDSET,
    _IDENTIFICATION_FIELDSET,
    _NOTES_FIELDSET,
    _VERSION_COLUMNS,
    _VERSION_LABELS,
)
from app.views.core_views import (
    AuditTrailActionMixin,
    CurrentVersionLifecycleMixin,
)
from app.views.filters import current_version_filter
from app.views.formatters import (
    download_link,
    item_identity_link,
    lifecycle_state,
    make_buy_code,
    priority_code,
)

# Workflow permissions shared by every business-object view: the revision
# actions, the lifecycle transitions and the audit-trail jump.
_WORKFLOW_PERMISSIONS = [
    "revisions",
    "audit",
    "submit_for_review",
    "approve",
    "release",
    "obsolete",
]


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


class PartModelView(
    RevisionHistoryMixin,
    ReviseActionsMixin,
    CurrentVersionLifecycleMixin,
    AuditTrailActionMixin,
    ModelView,
):
    datamodel = SQLAInterface(Part)
    route_base = "/parts"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["unit_of_measure", "make_buy_code", "material"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
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
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "make_buy_code": make_buy_code,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revise_major",
        "revise_minor",
    ] + _WORKFLOW_PERMISSIONS
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
        _NOTES_FIELDSET,
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


class DocumentModelView(
    RevisionHistoryMixin,
    CurrentVersionLifecycleMixin,
    AuditTrailActionMixin,
    ModelView,
):
    datamodel = SQLAInterface(Document)
    route_base = "/documents"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["file_name", "download_url", "file_size"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "file_name",
        "download_url",
        "mime_type",
        "file_size",
        "checksum_sha256",
        "created_on",
    ]
    search_columns = ["item_version", "file_name"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "download_url": download_link,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "can_download",
        "revise_major",
        "revise_minor",
    ] + _WORKFLOW_PERMISSIONS
    label_columns = dict(
        _VERSION_LABELS,
        file_name="File",
        download_url="",
        mime_type="Type",
        file_size="Size",
        checksum_sha256="SHA-256",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        (
            "File",
            {
                "fields": [
                    "file_name",
                    "download_url",
                    "mime_type",
                    "file_size",
                    "checksum_sha256",
                ]
            },
        ),
        _NOTES_FIELDSET,
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

    @expose("/download/<int:pk>", methods=["GET"])
    @has_access
    def download(self, pk):
        """Serve the stored document (spec §15.3: download permission)."""
        document = self.datamodel.get(pk)
        if document is None:
            flash("Document not found.", "danger")
            return redirect(self.get_redirect())
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"],
            document.file_path,
            download_name=document.file_name,
        )

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


class RequirementModelView(
    RevisionHistoryMixin,
    ReviseActionsMixin,
    CurrentVersionLifecycleMixin,
    AuditTrailActionMixin,
    ModelView,
):
    datamodel = SQLAInterface(Requirement)
    route_base = "/requirements"
    page_size = 25
    list_columns = _VERSION_COLUMNS + [
        "requirement_text",
        "verification_method",
        "priority_code",
    ]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "requirement_text",
        "verification_method",
        "priority_code",
        "created_on",
    ]
    search_columns = ["item_version", "requirement_text", "priority_code"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "priority_code": priority_code,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revise_major",
        "revise_minor",
    ] + _WORKFLOW_PERMISSIONS
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
        _NOTES_FIELDSET,
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


class ProductModelView(
    RevisionHistoryMixin,
    ReviseActionsMixin,
    CurrentVersionLifecycleMixin,
    AuditTrailActionMixin,
    ModelView,
):
    datamodel = SQLAInterface(Product)
    route_base = "/products"
    page_size = 25
    list_columns = _VERSION_COLUMNS + [
        "product_family",
        "market",
        "platform",
        "release_target",
    ]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "product_family",
        "market",
        "platform",
        "release_target",
        "created_on",
    ]
    search_columns = ["item_version", "platform", "product_family"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revise_major",
        "revise_minor",
        "structure",
        "add_child",
    ] + _WORKFLOW_PERMISSIONS
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
        _NOTES_FIELDSET,
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


class FunctionModelView(
    RevisionHistoryMixin,
    ReviseActionsMixin,
    CurrentVersionLifecycleMixin,
    AuditTrailActionMixin,
    ModelView,
):
    """Functions of a product (functional breakdown objects).

    The functional breakdown structure (parent/child functions) is navigated
    with the structure tree actions: "Structure" walks downstream to child
    functions, "Where used" walks upstream to the parent function and
    "Add child" appends a child function (a ``CONTAINS`` edge).
    """

    datamodel = SQLAInterface(Function)
    route_base = "/functions"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["function_text"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "function_text",
        "created_on",
    ]
    search_columns = ["item_version", "function_text"]
    base_filters = current_version_filter()
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "can_add",
        "revise_major",
        "revise_minor",
        "structure",
        "where_used",
        "add_child",
        "add_fulfillment",
    ] + _WORKFLOW_PERMISSIONS
    label_columns = dict(
        _VERSION_LABELS,
        function_text="Function",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        ("Function", {"fields": ["function_text"]}),
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]
    description_columns = {
        "function_text": "What the function must achieve.",
    }

    exclude_route_methods = {"edit", "delete"}

    @expose("/add/", methods=["GET"])
    @has_access
    def add(self):
        return redirect(url_for("FunctionCreateView.this_form_get"))

    @action(
        "structure",
        "Structure",
        "Browse the child functions?",
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
        "where_used",
        "Where used",
        "Show the parent function(s)?",
        "fa-search",
        multiple=False,
        single=True,
    )
    def where_used(self, item):
        item = first_item(item)
        return redirect(
            url_for(
                "StructureTreeView.tree",
                version_id=item.item_version_id,
                direction="up",
            )
        )

    @action(
        "add_child",
        "Add child function",
        "Add a child function to this function?",
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

    @action(
        "add_fulfillment",
        "Add fulfilling part",
        "Link a part that fulfils this function?",
        "fa-plug",
        multiple=False,
        single=True,
    )
    def add_fulfillment(self, item):
        item = first_item(item)
        return redirect(
            url_for(
                "FunctionFulfillmentAddView.this_form_get",
                function_version_id=item.item_version_id,
            )
        )

    def do_revise(self, item, change_type, actor):
        return FunctionService(db.session, actor).revise_function(
            item.item_version.item_id, change_type, actor
        )


# --- Related-view tabs on the Product show page -------------------------
#
# Standard FAB ``related_views`` tabs: each is a read-only ``ModelView`` on a
# business-object model joined to the shown product through a viewonly
# many-to-many relationship (see ``app/models/business.py``). Rows show the
# *linked* revisions - not necessarily the current one - because structure and
# traceability links always point at exact revisions.


class ProductChildPartModelView(ModelView):
    """Parts structurally contained by the shown product (CONTAINS edges)."""

    datamodel = SQLAInterface(Part)
    route_base = "/products/related-parts"
    default_view = "list"
    list_title = "Child Parts"
    title = "Child Parts"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["unit_of_measure", "material"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "unit_of_measure",
        "make_buy_code",
        "weight",
        "weight_uom",
        "material",
        "created_on",
    ]
    search_columns = ["item_version", "material"]
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "make_buy_code": make_buy_code,
    }
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
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
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]


class ProductChildDocumentModelView(ModelView):
    """Documents structurally contained by the shown product (CONTAINS edges)."""

    datamodel = SQLAInterface(Document)
    route_base = "/products/related-documents"
    default_view = "list"
    list_title = "Child Documents"
    title = "Child Documents"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["file_name", "download_url", "file_size"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "file_name",
        "download_url",
        "mime_type",
        "file_size",
        "checksum_sha256",
        "created_on",
    ]
    search_columns = ["item_version", "file_name"]
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "download_url": download_link,
    }
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = dict(
        _VERSION_LABELS,
        file_name="File",
        download_url="",
        mime_type="Type",
        file_size="Size",
        checksum_sha256="SHA-256",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        (
            "File",
            {
                "fields": [
                    "file_name",
                    "download_url",
                    "mime_type",
                    "file_size",
                    "checksum_sha256",
                ]
            },
        ),
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]


class ProductParentRequirementModelView(ModelView):
    """Requirements linked to the shown product (non-structural edges).

    The requirement is the source of the link - the parent side of the
    traceability edge (SATISFIES, REFERENCES, DERIVED_FROM, RELATED_TO).
    """

    datamodel = SQLAInterface(Requirement)
    route_base = "/products/related-requirements"
    default_view = "list"
    list_title = "Parent Requirements"
    title = "Parent Requirements"
    page_size = 25
    list_columns = _VERSION_COLUMNS + [
        "requirement_text",
        "verification_method",
        "priority_code",
    ]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "requirement_text",
        "verification_method",
        "priority_code",
        "created_on",
    ]
    search_columns = ["item_version", "requirement_text", "priority_code"]
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "priority_code": priority_code,
    }
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
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
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]


class ProductChildFunctionModelView(ModelView):
    """Functions performed by the shown product (PERFORMS edges)."""

    datamodel = SQLAInterface(Function)
    route_base = "/products/related-functions"
    default_view = "list"
    list_title = "Functions"
    title = "Functions"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["function_text"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "function_text",
        "created_on",
    ]
    search_columns = ["item_version", "function_text"]
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
    }
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = dict(
        _VERSION_LABELS,
        function_text="Function",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        ("Function", {"fields": ["function_text"]}),
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]


class FunctionFulfilledByPartModelView(ModelView):
    """Parts that fulfil the shown function (FULFILLS edges)."""

    datamodel = SQLAInterface(Part)
    route_base = "/functions/related-parts"
    default_view = "list"
    list_title = "Fulfilled by Parts"
    title = "Fulfilled by Parts"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["unit_of_measure", "material"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "unit_of_measure",
        "make_buy_code",
        "weight",
        "weight_uom",
        "material",
        "created_on",
    ]
    search_columns = ["item_version", "material"]
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
        "make_buy_code": make_buy_code,
    }
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
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
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]


class PartFulfillsFunctionModelView(ModelView):
    """Functions fulfilled by the shown part (FULFILLS edges)."""

    datamodel = SQLAInterface(Function)
    route_base = "/parts/related-functions"
    default_view = "list"
    list_title = "Fulfills Functions"
    title = "Fulfills Functions"
    page_size = 25
    list_columns = _VERSION_COLUMNS + ["function_text"]
    show_columns = _VERSION_COLUMNS + [
        "item_version.description",
        "function_text",
        "created_on",
    ]
    search_columns = ["item_version", "function_text"]
    base_order = ("item_version_id", "asc")
    formatters_columns = {
        "item_version.item": item_identity_link,
        "item_version.lifecycle_state": lifecycle_state,
    }
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = dict(
        _VERSION_LABELS,
        function_text="Function",
    )
    show_fieldsets = [
        _IDENTIFICATION_FIELDSET,
        ("Function", {"fields": ["function_text"]}),
        _NOTES_FIELDSET,
        _AUDIT_FIELDSET,
    ]


# Assigned after the class body: the related tab views are defined above and
# must exist before FAB resolves the tabs.
ProductModelView.related_views = [
    ProductChildPartModelView,
    ProductChildDocumentModelView,
    ProductParentRequirementModelView,
    ProductChildFunctionModelView,
]
PartModelView.related_views = [PartFulfillsFunctionModelView]
FunctionModelView.related_views = [FunctionFulfilledByPartModelView]
