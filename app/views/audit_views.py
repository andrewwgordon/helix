"""Read-only audit trail ModelView (spec §15.5).

Uses FAB's standard list widget with search/filters. Audit rows are append-only:
only ``can_list`` and ``can_show`` are granted.
"""

from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface

from app.models.audit import AuditEvent
from app.views.formatters import item_link


class AuditEventModelView(ModelView):
    datamodel = SQLAInterface(AuditEvent)
    route_base = "/audit"
    list_columns = [
        "created_on",
        "event_type",
        "entity_type",
        "entity_id",
        "item_id",
        "from_value",
        "to_value",
        "created_by",
    ]
    show_columns = [
        "created_on",
        "event_type",
        "entity_type",
        "entity_id",
        "item_id",
        "from_value",
        "to_value",
        "comment",
        "created_by",
    ]
    search_columns = ["event_type", "entity_type", "entity_id", "item_id"]
    base_order = ("created_on", "desc")
    page_size = 50
    formatters_columns = {"item_id": item_link}
    base_permissions = ["can_list", "can_show"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = {
        "created_on": "When",
        "event_type": "Event",
        "entity_type": "Entity",
        "entity_id": "Entity id",
        "item_id": "Item id",
        "from_value": "From",
        "to_value": "To",
        "comment": "Comment",
        "created_by": "Actor",
    }
    show_fieldsets = [
        (
            "Event",
            {
                "fields": [
                    "created_on",
                    "event_type",
                    "entity_type",
                    "entity_id",
                    "item_id",
                ]
            },
        ),
        ("Change", {"fields": ["from_value", "to_value", "comment"]}),
        ("Actor", {"fields": ["created_by"]}),
    ]
