"""Helpers for FAB ``@action`` methods.

Flask-AppBuilder invokes an ``@action`` method with a **list** of model
instances when the action is triggered from a list view (``action_post``) and
with a single instance from a show view (``/action/<name>/<pk>``). These
helpers normalize both cases so each action is written once and works from
either page.
"""


def as_items(item_or_items):
    """Return ``item_or_items`` as a list, accepting a single instance."""
    if item_or_items is None:
        return []
    if isinstance(item_or_items, (list, tuple)):
        return list(item_or_items)
    return [item_or_items]


def first_item(item_or_items):
    """Return the first instance from a single item or a list (or ``None``)."""
    items = as_items(item_or_items)
    return items[0] if items else None
