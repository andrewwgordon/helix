"""Shared list/show column definitions for versioned business objects.

Business-object rows are revisions (``ItemVersion`` keyed subtypes), so every
list starts with the same identification columns: the stable item number, the
revision label and the lifecycle state.
"""

_VERSION_COLUMNS = [
    "item_version.item",
    "item_version.revision_label",
    "item_version.lifecycle_state",
]
_VERSION_LABELS = {
    "item_version.item": "Item",
    "item_version.revision_label": "Revision",
    "item_version.lifecycle_state": "State",
    "created_on": "Created",
}
_IDENTIFICATION_FIELDSET = ("Identification", {"fields": _VERSION_COLUMNS})
_NOTES_FIELDSET = ("Notes", {"fields": ["item_version.description"]})
_AUDIT_FIELDSET = ("Audit", {"fields": ["created_on"], "expanded": False})
