"""Search feature tests (spec §15.6 rule 3).

Every entity list view must expose FAB's standard Search widget. FAB builds
the effective ``search_columns`` from the view attribute or, if it is unset,
from the model's searchable columns. These tests assert both the configuration
and the rendered widget, so a newly added list view cannot silently ship
without search.
"""

from flask_appbuilder import ModelView


def _app_modelviews(app):
    """Yield the application's own ``ModelView``s (exclude FAB security views)."""
    for view in app.appbuilder.baseviews:
        if not isinstance(view, ModelView):
            continue
        if view.__class__.__module__.startswith("flask_appbuilder"):
            continue
        yield view


def test_all_entity_views_declare_search_columns(app):
    missing = [
        view.__class__.__name__
        for view in _app_modelviews(app)
        if not view.search_columns
    ]
    assert not missing, f"list views without search columns: {missing}"


def test_all_entity_lists_render_search_widget(admin_client, app):
    checked = 0
    for view in _app_modelviews(app):
        route = f"{view.route_base}/list/"
        response = admin_client.get(route)
        assert response.status_code == 200, route
        # FAB's standard search widget: the filter form plus its Add Filter
        # dropdown built from ``search_columns``.
        assert b'id="filter_form"' in response.data, route
        assert b"Add Filter" in response.data, route
        checked += 1
    assert checked >= 19
