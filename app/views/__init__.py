"""View registration (spec §15.6 navigation).

Menu is intentionally flat and consistent: all domain entities live under
**PLM**, all reference data under **Administration**. Every entity is a
standard FAB ``ModelView``; only the documented exceptions in spec §15.5 use a
custom view.
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
    PartCreateView,
    ProductCreateView,
    RequirementCreateView,
)
from app.views.business_views import (
    DocumentModelView,
    PartModelView,
    ProductModelView,
    RequirementModelView,
)
from app.views.core_views import (
    ItemModelView,
    ItemRelationshipModelView,
    ItemVersionModelView,
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
from app.views.structure_views import StructureChildAddView, StructureTreeView

# --- PLM domain --------------------------------------------------------
appbuilder.add_view(
    ItemModelView, "Items", icon="fa-list", category="PLM"
)
appbuilder.add_view(PartModelView, "Parts", icon="fa-cube", category="PLM")
appbuilder.add_view(
    DocumentModelView, "Documents", icon="fa-file-text-o", category="PLM"
)
appbuilder.add_view(
    RequirementModelView, "Requirements", icon="fa-check-square-o", category="PLM"
)
appbuilder.add_view(
    ProductModelView, "Products", icon="fa-cubes", category="PLM"
)
appbuilder.add_view(
    ItemVersionModelView,
    "Revisions",
    icon="fa-code-fork",
    category="PLM",
)
appbuilder.add_view(
    ItemRelationshipModelView,
    "Relationships",
    icon="fa-sitemap",
    category="PLM",
)
appbuilder.add_view(
    BaselineModelView, "Baselines", icon="fa-camera-retro", category="PLM"
)
appbuilder.add_view(
    AuditEventModelView, "Audit Trail", icon="fa-history", category="PLM"
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

# --- Structure browser/editor (approved custom view, no menu entry) ---
appbuilder.add_view_no_menu(StructureTreeView)
appbuilder.add_view_no_menu(StructureChildAddView)
