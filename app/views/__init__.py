"""View registration (spec §15.6 navigation).

Menu is flat, at most two levels, and organised by **user task** rather than by
internal table: *Product Data* is where users author the four business-object
types, *Change & Release* is where the revision workflow is driven (the
reviewer's "Pending Review" queue, the full revision history and baselines),
*Traceability* holds the cross-cutting lookups (items, relationships, audit),
and *Administration* holds reference data. Every view is a standard FAB
``ModelView``/``SimpleFormView``; only the documented exceptions in spec §15.5
use a custom view.
"""

from app import appbuilder
from app.views.audit_views import AuditEventModelView
from app.views.baseline_views import (
    BaselineCreateView,
    BaselineMemberModelView,
    BaselineModelView,
)
from app.views.business_forms import (
    DocumentCreateView,
    DocumentReviseView,
    FunctionCreateView,
    PartCreateView,
    ProductCreateView,
    RequirementCreateView,
)
from app.views.business_views import (
    DocumentModelView,
    FunctionFulfilledByPartModelView,
    FunctionModelView,
    PartFulfillsFunctionModelView,
    PartModelView,
    ProductChildDocumentModelView,
    ProductChildFunctionModelView,
    ProductChildPartModelView,
    ProductModelView,
    ProductParentRequirementModelView,
    RequirementModelView,
)
from app.views.core_views import (
    ItemModelView,
    ItemRelationshipModelView,
    ItemVersionModelView,
    PendingReviewModelView,
)
from app.views.reference_views import (
    ItemTypeModelView,
    LifecycleStateModelView,
    LifecycleTransitionModelView,
    MakeBuyCodeModelView,
    MarketModelView,
    PriorityCodeModelView,
    ProductFamilyModelView,
    RelationshipTypeModelView,
    UnitOfMeasureModelView,
    VerificationMethodModelView,
)
from app.views.structure_views import (
    FunctionFulfillmentAddView,
    StructureChildAddView,
    StructureTreeView,
)

# --- Product Data: authoring the four business-object types ------------
appbuilder.add_view(
    ProductModelView,
    "Products",
    icon="fa-cubes",
    category="Product Data",
    category_icon="fa-folder-open",
)
appbuilder.add_view(
    PartModelView, "Parts", icon="fa-cube", category="Product Data"
)
appbuilder.add_view(
    DocumentModelView, "Documents", icon="fa-file-text-o", category="Product Data"
)
appbuilder.add_view(
    RequirementModelView,
    "Requirements",
    icon="fa-check-square-o",
    category="Product Data",
)
appbuilder.add_view(
    FunctionModelView,
    "Functions",
    icon="fa-cogs",
    category="Product Data",
)

# Related-view tabs embedded on the Product show page (spec §3.3.2: FAB
# ``related_views`` is preferred over a hand-built page). No menu entries.
appbuilder.add_view_no_menu(ProductChildPartModelView)
appbuilder.add_view_no_menu(ProductChildDocumentModelView)
appbuilder.add_view_no_menu(ProductParentRequirementModelView)
appbuilder.add_view_no_menu(ProductChildFunctionModelView)
appbuilder.add_view_no_menu(FunctionFulfilledByPartModelView)
appbuilder.add_view_no_menu(PartFulfillsFunctionModelView)

# --- Change & Release: the revision workflow ---------------------------
# "Pending Review" is the reviewer's task queue (REVIEW-state revisions, with
# approve/reject actions on the same page); "All Revisions" is the full
# history including superseded revisions.
appbuilder.add_view(
    PendingReviewModelView,
    "Pending Review",
    icon="fa-inbox",
    category="Change & Release",
    category_icon="fa-exchange",
)
appbuilder.add_view(
    ItemVersionModelView,
    "All Revisions",
    icon="fa-code-fork",
    category="Change & Release",
)
appbuilder.add_view(
    BaselineModelView,
    "Baselines",
    icon="fa-camera-retro",
    category="Change & Release",
)

# --- Traceability: cross-cutting lookups -------------------------------
appbuilder.add_view(
    ItemModelView, "Items", icon="fa-list", category="Traceability", category_icon="fa-search"
)
appbuilder.add_view(
    ItemRelationshipModelView,
    "Relationships",
    icon="fa-sitemap",
    category="Traceability",
)
appbuilder.add_view(
    AuditEventModelView,
    "Audit Trail",
    icon="fa-history",
    category="Traceability",
)

# --- Administration: reference data -----------------------------------
appbuilder.add_view(
    ItemTypeModelView, "Item Types", icon="fa-tags", category="Administration"
)
appbuilder.add_view(
    LifecycleStateModelView,
    "Lifecycle States",
    icon="fa-random",
    category="Administration",
)
appbuilder.add_view(
    LifecycleTransitionModelView,
    "Lifecycle Transitions",
    icon="fa-exchange",
    category="Administration",
)
appbuilder.add_view(
    RelationshipTypeModelView,
    "Relationship Types",
    icon="fa-link",
    category="Administration",
)
appbuilder.add_view(
    UnitOfMeasureModelView,
    "Units of Measure",
    icon="fa-balance-scale",
    category="Administration",
)
appbuilder.add_view(
    MakeBuyCodeModelView,
    "Make / Buy",
    icon="fa-shopping-cart",
    category="Administration",
)
appbuilder.add_view(
    VerificationMethodModelView,
    "Verification Methods",
    icon="fa-flask",
    category="Administration",
)
appbuilder.add_view(
    PriorityCodeModelView,
    "Priorities",
    icon="fa-sort-amount-desc",
    category="Administration",
)
appbuilder.add_view(
    ProductFamilyModelView,
    "Product Families",
    icon="fa-object-group",
    category="Administration",
)
appbuilder.add_view(
    MarketModelView, "Markets", icon="fa-globe", category="Administration"
)

# --- Baseline member view is embedded via BaselineModelView.related_views.
appbuilder.add_view_no_menu(BaselineMemberModelView)

# --- Service-backed create/revise forms (no menu entries) -------------
appbuilder.add_view_no_menu(BaselineCreateView)
appbuilder.add_view_no_menu(PartCreateView)
appbuilder.add_view_no_menu(DocumentCreateView)
appbuilder.add_view_no_menu(DocumentReviseView)
appbuilder.add_view_no_menu(RequirementCreateView)
appbuilder.add_view_no_menu(ProductCreateView)
appbuilder.add_view_no_menu(FunctionCreateView)

# --- Structure browser/editor (approved custom view, no menu entry) ---
appbuilder.add_view_no_menu(StructureTreeView)
appbuilder.add_view_no_menu(StructureChildAddView)
appbuilder.add_view_no_menu(FunctionFulfillmentAddView)
