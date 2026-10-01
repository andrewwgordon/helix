"""Phase 7: baseline UI tests (spec §15.4 / §15.6).

Baseline views use FAB's standard ``ModelView`` and ``SimpleFormView``. The
list view is registered under the **PLM** menu; freeze is a service-backed
one-way action.
"""

from app import db
from app.models.baseline import Baseline
from app.services import (
    Actor,
    BaselineService,
    LifecycleService,
    ProductService,
)


def _actor():
    return Actor(username="testadmin", roles=frozenset({"Admin"}), is_admin=True)


def _releasable_product(number):
    actor = _actor()
    product = ProductService(db.session).create_product(number, actor)
    version = product.item_version
    lifecycle = LifecycleService(db.session)
    lifecycle.change_lifecycle(version.id, "IN_WORK", actor)
    lifecycle.change_lifecycle(version.id, "REVIEW", actor)
    lifecycle.change_lifecycle(version.id, "APPROVED", actor)
    return product


def test_baseline_add_redirects_to_form(admin_client):
    response = admin_client.get("/baselines/add/")
    assert response.status_code == 302
    assert "/baselines/create/form" in response.headers["Location"]


def test_baseline_create_form_renders(admin_client):
    assert admin_client.get("/baselines/create/form").status_code == 200


def test_create_baseline_through_form(admin_client, app):
    with app.app_context():
        product = _releasable_product("T-B7-UI-PRD")
        version_id = product.item_version_id

    response = admin_client.post(
        "/baselines/create/form",
        data={
            "baseline_number": "BL-T7-UI-1",
            "baseline_name": "UI baseline",
            "product": str(version_id),
            "description": "created from the UI",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        baseline = (
            db.session.query(Baseline)
            .filter_by(baseline_number="BL-T7-UI-1")
            .one()
        )
        assert baseline.status == "DRAFT"
        assert baseline.product_version_id == version_id


def test_freeze_action_freezes_baseline(admin_client, app):
    with app.app_context():
        product = _releasable_product("T-B7-UI-FRZ")
        baseline = BaselineService(db.session, _actor()).create_baseline(
            product.item_version_id, "BL-T7-UI-FRZ", "Freeze me", _actor()
        )
        baseline_id = baseline.id

    response = admin_client.post(
        "/baselines/action_post",
        data={"action": "freeze", "rowid": str(baseline_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        refreshed = db.session.get(Baseline, baseline_id)
        assert refreshed.status == "FROZEN"
        assert refreshed.frozen_at is not None


def test_baseline_menu_entry_present(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 200
    assert b"Baselines" in response.data
