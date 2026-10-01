"""Shared list filters for standard FAB ``ModelView``s (spec §3.3).

These are used with ``base_filters`` so the standard FAB list widgets present
the most useful default view without any custom templates.
"""

from app import db
from app.models.core import Item


def current_version_ids():
    """Return the ids of every item's current version.

    Intended for ``FilterInFunction``: business-object lists show the current
    revision of each item by default instead of every historical revision.
    The function is evaluated per request.
    """
    return [
        row[0]
        for row in db.session.query(Item.current_version_id)
        .filter(Item.current_version_id.isnot(None))
        .all()
    ]


def current_version_filter():
    """Build a fresh ``base_filters`` list restricting to current revisions."""
    from flask_appbuilder.models.sqla.filters import FilterInFunction

    return [["item_version_id", FilterInFunction, current_version_ids]]
