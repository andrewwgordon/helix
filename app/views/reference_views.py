"""Reference / lookup ModelViews (spec §15.1).

Reference data is administrative and uses FAB's standard CRUD views.
"""

from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface

from app.models.reference import (
    ItemType,
    LifecycleState,
    LifecycleTransition,
    MakeBuyCode,
    Market,
    PriorityCode,
    ProductFamily,
    RelationshipType,
    UnitOfMeasure,
    VerificationMethod,
)
from app.views.formatters import active_flag


class BaseLookupView(ModelView):
    """Shared configuration for simple code/name lookup tables."""

    list_columns = ["code", "name", "description", "is_active"]
    show_columns = ["code", "name", "description", "is_active", "created_on", "changed_on"]
    add_columns = ["code", "name", "description", "is_active"]
    edit_columns = ["code", "name", "description", "is_active"]
    search_columns = ["code", "name"]
    base_order = ("code", "asc")
    formatters_columns = {"is_active": active_flag}
    label_columns = {
        "code": "Code",
        "name": "Name",
        "description": "Description",
        "is_active": "Active",
    }
    show_fieldsets = [
        ("Lookup", {"fields": ["code", "name", "description", "is_active"]}),
        ("Audit", {"fields": ["created_on", "changed_on"], "expanded": False}),
    ]


class ItemTypeModelView(ModelView):
    datamodel = SQLAInterface(ItemType)
    route_base = "/itemtypes"
    list_columns = ["code", "name", "description", "is_active"]
    add_columns = ["code", "name", "description", "is_active"]
    edit_columns = ["code", "name", "description", "is_active"]
    search_columns = ["code", "name"]
    base_order = ("code", "asc")
    formatters_columns = {"is_active": active_flag}
    label_columns = {
        "code": "Code",
        "name": "Name",
        "description": "Description",
        "is_active": "Active",
    }
    show_fieldsets = [
        ("Item type", {"fields": ["code", "name", "description", "is_active"]}),
    ]


class LifecycleStateModelView(ModelView):
    datamodel = SQLAInterface(LifecycleState)
    route_base = "/lifecyclestates"
    list_columns = [
        "sequence",
        "code",
        "name",
        "is_releasable",
        "is_terminal",
    ]
    add_columns = [
        "code",
        "name",
        "sequence",
        "is_releasable",
        "is_terminal",
        "description",
    ]
    edit_columns = add_columns
    search_columns = ["code", "name"]
    base_order = ("sequence", "asc")
    label_columns = {
        "code": "Code",
        "name": "Name",
        "sequence": "Sequence",
        "is_releasable": "Releasable",
        "is_terminal": "Terminal",
        "description": "Description",
    }
    show_fieldsets = [
        (
            "Lifecycle state",
            {
                "fields": [
                    "code",
                    "name",
                    "sequence",
                    "is_releasable",
                    "is_terminal",
                    "description",
                ]
            },
        ),
    ]


class LifecycleTransitionModelView(ModelView):
    datamodel = SQLAInterface(LifecycleTransition)
    route_base = "/lifecycle-transitions"
    list_columns = ["from_state", "to_state", "required_role", "is_active"]
    add_columns = ["from_state", "to_state", "required_role", "is_active"]
    edit_columns = add_columns
    search_columns = ["from_state", "to_state", "required_role"]
    base_order = ("from_state_id", "asc")
    formatters_columns = {"is_active": active_flag}
    label_columns = {
        "from_state": "From",
        "to_state": "To",
        "required_role": "Required role",
        "is_active": "Active",
    }
    show_fieldsets = [
        (
            "Transition",
            {"fields": ["from_state", "to_state", "required_role", "is_active"]},
        ),
    ]


class RelationshipTypeModelView(ModelView):
    datamodel = SQLAInterface(RelationshipType)
    route_base = "/relationshiptypes"
    list_columns = [
        "code",
        "name",
        "is_structural",
        "allows_quantity",
        "allows_find_number",
        "is_active",
    ]
    add_columns = list_columns
    edit_columns = list_columns
    search_columns = ["code", "name"]
    base_order = ("code", "asc")
    formatters_columns = {"is_active": active_flag}
    label_columns = {
        "code": "Code",
        "name": "Name",
        "is_structural": "Structural",
        "allows_quantity": "Quantity",
        "allows_find_number": "Find number",
        "is_active": "Active",
    }
    show_fieldsets = [
        (
            "Relationship type",
            {
                "fields": [
                    "code",
                    "name",
                    "is_structural",
                    "allows_quantity",
                    "allows_find_number",
                    "is_active",
                ]
            },
        ),
    ]


class UnitOfMeasureModelView(BaseLookupView):
    datamodel = SQLAInterface(UnitOfMeasure)
    route_base = "/uoms"


class MakeBuyCodeModelView(BaseLookupView):
    datamodel = SQLAInterface(MakeBuyCode)
    route_base = "/makebuycodes"


class VerificationMethodModelView(BaseLookupView):
    datamodel = SQLAInterface(VerificationMethod)
    route_base = "/verificationmethods"


class PriorityCodeModelView(BaseLookupView):
    datamodel = SQLAInterface(PriorityCode)
    route_base = "/prioritycodes"


class ProductFamilyModelView(BaseLookupView):
    datamodel = SQLAInterface(ProductFamily)
    route_base = "/productfamilies"


class MarketModelView(BaseLookupView):
    datamodel = SQLAInterface(Market)
    route_base = "/markets"
