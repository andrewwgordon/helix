"""Core identity / revision ModelViews (spec §15.2).

These are read-only through the UI: revisions and relationships are created by
domain services, never by direct CRUD.
"""

from flask import flash, g, redirect, url_for
from flask_appbuilder import ModelView
from flask_appbuilder.actions import action
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.widgets import ListLinkWidget

from app import db
from app.models.core import Item, ItemRelationship, ItemVersion
from app.services import Actor, LifecycleService, RelationshipService
from app.services.exceptions import PlmError
from app.views.action_utils import as_items, first_item
from app.views.formatters import item_identity_link, item_version_link, lifecycle_state


class LifecycleActionsMixin:
    """Service-backed lifecycle transition buttons (spec §14.8)."""

    def _apply_lifecycle(self, item, method_name, label):
        actor = Actor.from_user(g.user)
        service = LifecycleService(db.session, actor)
        method = getattr(service, method_name)
        applied = []
        for version in as_items(item):
            try:
                applied.append(method(version.id, actor))
            except PlmError as exc:
                flash(str(exc), "danger")
                return redirect(self.get_redirect())
        if len(applied) == 1:
            flash(
                f"{label}. State is now '{applied[0].lifecycle_state.name}'.",
                "success",
            )
        elif applied:
            flash(f"{label} for {len(applied)} versions.", "success")
        return redirect(self.get_redirect())

    @action(
        "submit_for_review",
        "Submit for review",
        "Submit this version for review?",
        "fa-paper-plane",
        single=True,
    )
    def submit_for_review(self, item):
        return self._apply_lifecycle(item, "submit_for_review", "Submitted for review")

    @action(
        "approve",
        "Approve",
        "Approve this version?",
        "fa-check",
        single=True,
    )
    def approve(self, item):
        return self._apply_lifecycle(item, "approve", "Approved")

    @action(
        "release",
        "Release",
        "Release this version?",
        "fa-flag-checkered",
        single=True,
    )
    def release(self, item):
        return self._apply_lifecycle(item, "release", "Released")

    @action(
        "obsolete",
        "Obsolete",
        "Mark this version obsolete?",
        "fa-ban",
        single=True,
    )
    def obsolete(self, item):
        return self._apply_lifecycle(item, "obsolete", "Obsoleted")


class ItemModelView(ModelView):
    datamodel = SQLAInterface(Item)
    route_base = "/items"
    list_columns = ["item_number", "item_type", "current_version", "created_on"]
    show_columns = [
        "item_number",
        "item_type",
        "current_version",
        "created_on",
        "changed_on",
    ]
    search_columns = ["item_number", "item_type"]
    base_order = ("item_number", "asc")
    base_permissions = ["can_list", "can_show", "revisions"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = {
        "item_number": "Item number",
        "item_type": "Type",
        "current_version": "Current revision",
        "created_on": "Created",
        "changed_on": "Changed",
    }
    show_fieldsets = [
        ("Identification", {"fields": ["item_number", "item_type"]}),
        ("Latest revision", {"fields": ["current_version"]}),
        ("Audit", {"fields": ["created_on", "changed_on"], "expanded": False}),
    ]
    description_columns = {
        "item_number": "Stable business identity, unique within its item type.",
        "item_type": "Classification that selects the business-object subtype.",
    }

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
            url_for("ItemVersionModelView.list") + f"?_flt_0_item={item.id}"
        )


class ItemVersionModelView(LifecycleActionsMixin, ModelView):
    datamodel = SQLAInterface(ItemVersion)
    route_base = "/itemversions"
    list_columns = [
        "item",
        "revision_label",
        "lifecycle_state",
        "version_sequence",
        "description",
        "created_on",
    ]
    show_columns = [
        "item.item_number",
        "revision_label",
        "lifecycle_state",
        "version_sequence",
        "major_revision",
        "minor_revision",
        "description",
        "superseded_by",
        "effective_from",
        "effective_to",
        "created_on",
    ]
    search_columns = ["item", "revision_label", "lifecycle_state"]
    base_order = ("item.item_number", "asc")
    formatters_columns = {
        "item": item_identity_link,
        "lifecycle_state": lifecycle_state,
    }
    base_permissions = [
        "can_list",
        "can_show",
        "audit",
        "submit_for_review",
        "approve",
        "release",
        "obsolete",
        "structure",
        "where_used",
        "add_child",
    ]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = {
        "item": "Item",
        "item.item_number": "Item",
        "revision_label": "Revision",
        "lifecycle_state": "State",
        "version_sequence": "Sequence",
        "major_revision": "Major",
        "minor_revision": "Minor",
        "superseded_by": "Superseded by",
        "effective_from": "Effective from",
        "effective_to": "Effective to",
        "description": "Description",
        "created_on": "Created",
    }
    show_fieldsets = [
        (
            "Identification",
            {"fields": ["item.item_number", "revision_label", "version_sequence"]},
        ),
        ("Lifecycle", {"fields": ["lifecycle_state", "superseded_by"]}),
        (
            "Revision",
            {
                "fields": [
                    "major_revision",
                    "minor_revision",
                    "effective_from",
                    "effective_to",
                ]
            },
        ),
        ("Notes", {"fields": ["description"]}),
        ("Audit", {"fields": ["created_on"], "expanded": False}),
    ]
    description_columns = {
        "lifecycle_state": "Workflow position of this revision.",
        "superseded_by": "The revision that replaced this one, if any.",
        "major_revision": "Incremented for form/fit/function changes.",
        "minor_revision": "Incremented for non-functional changes.",
        "effective_from": "Start of the revision's effectivity window.",
        "effective_to": "End of the revision's effectivity window.",
    }

    @action(
        "audit",
        "Audit trail",
        "Show the audit trail for this version?",
        "fa-history",
        multiple=False,
        single=True,
    )
    def audit(self, item):
        item = first_item(item)
        return redirect(
            url_for("AuditEventModelView.list")
            + f"?_flt_0_item_id={item.item_id}"
        )

    @action(
        "structure",
        "Structure",
        "Browse the downstream structure?",
        "fa-tree",
        multiple=False,
        single=True,
    )
    def structure(self, item):
        item = first_item(item)
        return redirect(
            url_for("StructureTreeView.tree", version_id=item.id, direction="down")
        )

    @action(
        "where_used",
        "Where used",
        "Show where this version is used?",
        "fa-search",
        multiple=False,
        single=True,
    )
    def where_used(self, item):
        item = first_item(item)
        return redirect(
            url_for("StructureTreeView.tree", version_id=item.id, direction="up")
        )

    @action(
        "add_child",
        "Add child",
        "Add a structural child to this version?",
        "fa-plus",
        multiple=False,
        single=True,
    )
    def add_child(self, item):
        item = first_item(item)
        return redirect(
            url_for("StructureChildAddView.this_form_get", parent_version_id=item.id)
        )


# Embed the revision list on the Item show page (spec §3.3.2: entity pages are
# one click from their list, and FAB ``related_views`` is preferred over a
# hand-built page). Assigned after the class body because the two views
# reference each other.
ItemModelView.related_views = [ItemVersionModelView]


class ItemRelationshipModelView(ModelView):
    datamodel = SQLAInterface(ItemRelationship)
    route_base = "/relationships"
    list_columns = [
        "relationship_type",
        "source_item_version",
        "target_item_version",
        "quantity",
        "find_number",
    ]
    show_columns = [
        "relationship_type",
        "source_item_version",
        "target_item_version",
        "quantity",
        "find_number",
        "sort_order",
        "created_on",
    ]
    search_columns = ["relationship_type", "source_item_version", "target_item_version"]
    base_order = ("source_item_version_id", "asc")
    page_size = 50
    list_widget = ListLinkWidget
    formatters_columns = {
        "source_item_version": item_version_link,
        "target_item_version": item_version_link,
    }
    base_permissions = ["can_list", "can_show", "remove"]
    exclude_route_methods = {"add", "edit", "delete"}
    label_columns = {
        "relationship_type": "Type",
        "source_item_version": "Source",
        "target_item_version": "Target",
        "quantity": "Quantity",
        "find_number": "Find number",
        "sort_order": "Sort order",
        "created_on": "Created",
    }
    show_fieldsets = [
        (
            "Relationship",
            {
                "fields": [
                    "relationship_type",
                    "source_item_version",
                    "target_item_version",
                ]
            },
        ),
        ("Structure data", {"fields": ["quantity", "find_number", "sort_order"]}),
        ("Audit", {"fields": ["created_on"], "expanded": False}),
    ]
    description_columns = {
        "relationship_type": "Structural (BOM) or traceability semantics.",
        "quantity": "Only valid for relationship types that permit a quantity.",
        "find_number": "Position identifier within the parent.",
    }

    @action(
        "remove",
        "Remove",
        "Remove this relationship?",
        "fa-trash",
        single=True,
    )
    def remove(self, item):
        actor = Actor.from_user(g.user)
        service = RelationshipService(db.session, actor)
        removed = 0
        for relationship in as_items(item):
            try:
                service.remove_relationship(relationship.id, actor)
                removed += 1
            except PlmError as exc:
                flash(str(exc), "danger")
                return redirect(self.get_redirect())
        if removed:
            flash(f"Removed {removed} relationship(s).", "success")
        return redirect(self.get_redirect())
