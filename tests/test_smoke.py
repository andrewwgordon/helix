"""Phase 0 smoke tests: app boots and SQLite pragmas are active."""

from sqlalchemy import text


def test_app_boots(app):
    assert app is not None
    assert app.config["TESTING"] is True


def test_foreign_keys_enabled(app):
    with app.app_context():
        result = app.extensions["sqlalchemy"].session.execute(
            text("PRAGMA foreign_keys")
        ).scalar()
    assert result == 1


def test_index_responds(app):
    client = app.test_client()
    response = client.get("/")
    # Unauthenticated users are redirected to the login page (or get 200).
    assert response.status_code in (200, 302)
