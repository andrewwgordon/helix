"""Summary dashboard (spec §15.5 / §15.6 rule 4).

A standard Flask-AppBuilder ``IndexView`` subclass. It renders the bundled
``appbuilder/index.html`` layout, overridden in ``app/templates`` with a small
set of read-only aggregate counts. No custom routes, navigation tree, or
parallel reporting UI are introduced: every card links to an existing standard
list view (optionally pre-filtered), per spec §3.3.2.

Model imports are deliberately local to :meth:`SummaryIndexView._build_summary`
because FAB imports this module (via ``FAB_INDEX_VIEW``) during ``init_app``
before the application registers its views and models.
"""

from flask import url_for
from flask_appbuilder import IndexView, expose
from sqlalchemy import func

from app import db


class SummaryIndexView(IndexView):
    """FAB index page showing PLM summary metrics."""

    index_template = "appbuilder/index.html"

    @expose("/")
    def index(self):
        self.update_redirect()
        return self.render_template(
            self.index_template,
            appbuilder=self.appbuilder,
            summary=self._build_summary(),
        )

    def _build_summary(self):
        """Return read-only aggregate counts for the dashboard template."""
        from app.models.baseline import Baseline
        from app.models.business import Document, Function, Part, Product, Requirement
        from app.models.core import Item, ItemVersion
        from app.models.reference import LifecycleState

        def count(model):
            return db.session.query(func.count()).select_from(model).scalar() or 0

        # Business subtypes share the ``item_version`` primary key (no ``id``),
        # so the helper counts whole rows rather than a named column.

        cards = [
            {
                "label": "Items",
                "count": count(Item),
                "icon": "fa-list",
                "url": url_for("ItemModelView.list"),
            },
            {
                "label": "Parts",
                "count": count(Part),
                "icon": "fa-cube",
                "url": url_for("PartModelView.list"),
            },
            {
                "label": "Documents",
                "count": count(Document),
                "icon": "fa-file-text-o",
                "url": url_for("DocumentModelView.list"),
            },
            {
                "label": "Requirements",
                "count": count(Requirement),
                "icon": "fa-check-square-o",
                "url": url_for("RequirementModelView.list"),
            },
            {
                "label": "Products",
                "count": count(Product),
                "icon": "fa-cubes",
                "url": url_for("ProductModelView.list"),
            },
            {
                "label": "Baselines",
                "count": count(Baseline),
                "icon": "fa-camera-retro",
                "url": url_for("BaselineModelView.list"),
            },
            {
                "label": "Functions",
                "count": count(Function),
                "icon": "fa-cogs",
                "url": url_for("FunctionModelView.list"),
            },
        ]

        lifecycle = [
            {
                "name": name,
                "code": code,
                "count": revision_count,
                "url": url_for("ItemVersionModelView.list")
                + f"?_flt_0_lifecycle_state={state_id}",
            }
            for state_id, code, name, revision_count in (
                db.session.query(
                    LifecycleState.id,
                    LifecycleState.code,
                    LifecycleState.name,
                    func.count(ItemVersion.id),
                )
                .outerjoin(
                    ItemVersion,
                    ItemVersion.lifecycle_state_id == LifecycleState.id,
                )
                .group_by(LifecycleState.id)
                .order_by(LifecycleState.sequence.asc())
                .all()
            )
        ]

        baselines = [
            {
                "status": status,
                "count": baseline_count,
                "url": url_for("BaselineModelView.list") + f"?_flt_0_status={status}",
            }
            for status, baseline_count in (
                db.session.query(Baseline.status, func.count(Baseline.id))
                .group_by(Baseline.status)
                .order_by(Baseline.status.asc())
                .all()
            )
        ]

        # Task-oriented entry points: one-click creation of each object type
        # (standard service-backed SimpleFormViews, no menu entries) and the
        # reviewer's pending-review queue.
        quick_actions = [
            {
                "label": "New product",
                "icon": "fa-cubes",
                "url": url_for("ProductCreateView.this_form_get"),
            },
            {
                "label": "New part",
                "icon": "fa-cube",
                "url": url_for("PartCreateView.this_form_get"),
            },
            {
                "label": "New document",
                "icon": "fa-file-text-o",
                "url": url_for("DocumentCreateView.this_form_get"),
            },
            {
                "label": "New requirement",
                "icon": "fa-check-square-o",
                "url": url_for("RequirementCreateView.this_form_get"),
            },
            {
                "label": "New function",
                "icon": "fa-cogs",
                "url": url_for("FunctionCreateView.this_form_get"),
            },
            {
                "label": "New baseline",
                "icon": "fa-camera-retro",
                "url": url_for("BaselineCreateView.this_form_get"),
            },
        ]

        pending_review_count = (
            db.session.query(func.count())
            .select_from(ItemVersion)
            .join(LifecycleState, ItemVersion.lifecycle_state_id == LifecycleState.id)
            .filter(LifecycleState.code == "REVIEW")
            .scalar()
            or 0
        )

        return {
            "cards": cards,
            "lifecycle": lifecycle,
            "baselines": baselines,
            "quick_actions": quick_actions,
            "pending_review": {
                "count": pending_review_count,
                "url": url_for("PendingReviewModelView.list"),
            },
        }
