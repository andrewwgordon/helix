"""Column formatters for the bundled FAB list/show widgets (spec §3.3.1).

FAB's list and show widgets accept ``formatters_columns`` and call the
formatter for each displayed value. Returning :class:`markupsafe.Markup`
renders Bootstrap labels using the CSS FAB already bundles, with no custom
template.
"""

from flask import url_for
from markupsafe import Markup

_STATE_LABELS = {
    "DRAFT": "default",
    "IN_WORK": "info",
    "REVIEW": "warning",
    "APPROVED": "primary",
    "RELEASED": "success",
    "OBSOLETE": "danger",
}

_PRIORITY_LABELS = {
    "MANDATORY": "danger",
    "HIGH": "warning",
    "MEDIUM": "info",
    "LOW": "default",
}

_MAKE_BUY_LABELS = {
    "MAKE": "primary",
    "BUY": "info",
    "MAKE_OR_BUY": "default",
}

_BASELINE_LABELS = {"DRAFT": "warning", "FROZEN": "success"}


def _badge(text, css_class):
    return Markup(f'<span class="label label-{css_class}">{text}</span>')


def _coded(value, palette):
    if value is None:
        return ""
    code = getattr(value, "code", str(value))
    name = getattr(value, "name", code)
    return _badge(name, palette.get(code, "default"))


def lifecycle_state(value):
    """Render a ``LifecycleState`` as a coloured bootstrap label."""
    return _coded(value, _STATE_LABELS)


def priority_code(value):
    """Render a ``PriorityCode`` as a coloured bootstrap label."""
    return _coded(value, _PRIORITY_LABELS)


def make_buy_code(value):
    """Render a ``MakeBuyCode`` as a coloured bootstrap label."""
    return _coded(value, _MAKE_BUY_LABELS)


def baseline_status(value):
    """Render a baseline ``DRAFT``/``FROZEN`` status label."""
    if not value:
        return ""
    code = str(value)
    return _badge(code.title(), _BASELINE_LABELS.get(code, "default"))


def active_flag(value):
    """Render an ``is_active`` boolean as Active/Inactive."""
    return _badge("Active", "success") if value else _badge("Inactive", "default")


def boolean_flag(value):
    """Render a generic boolean as Yes/No."""
    return _badge("Yes", "success") if value else _badge("No", "default")


def download_link(value):
    """Render a download URL (e.g. ``Document.download_url``) as a link.

    Used on the standard list/show widgets so users can open the current
    document in one click without any custom template.
    """
    if not value:
        return ""
    return Markup(
        f'<a class="btn btn-xs btn-default" href="{value}">'
        '<i class="fa fa-download"></i> Open</a>'
    )


def item_link(value):
    """Render an ``Item`` id as a link to its show page."""
    if not value:
        return ""
    try:
        href = url_for("ItemModelView.show", pk=value)
    except Exception:  # pragma: no cover - only if the view is unregistered
        return str(value)
    return Markup(f'<a href="{href}">{value}</a>')


def item_version_link(value):
    """Render an ``ItemVersion`` instance as a link to its show page."""
    if value is None:
        return ""
    try:
        href = url_for("ItemVersionModelView.show", pk=value.id)
    except Exception:  # pragma: no cover
        return str(value)
    label = f"{value.item.item_number} {value.revision_label}"
    return Markup(f'<a href="{href}">{label}</a>')


def item_identity_link(value):
    """Render an ``Item`` instance as a link to its (identity) show page.

    Used on revision lists so users can navigate from a specific revision
    back to the stable item it belongs to.
    """
    if value is None:
        return ""
    try:
        href = url_for("ItemModelView.show", pk=value.id)
    except Exception:  # pragma: no cover - only if the view is unregistered
        return getattr(value, "item_number", str(value))
    return Markup(f'<a href="{href}">{value.item_number}</a>')
