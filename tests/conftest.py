"""Shared pytest fixtures.

Flask-AppBuilder registers views and permissions on process-global registries,
so the application is created **once per test session**. Tests use unique item
numbers to stay independent within the shared in-memory database.
"""

import pytest

from app import create_app, db
from app.services import Actor


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    application = create_app("test")
    # Keep test document uploads out of the project tree.
    application.config["UPLOAD_FOLDER"] = str(tmp_path_factory.mktemp("uploads"))
    with application.app_context():
        yield application


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def admin_client(app):
    """A test client authenticated as an Admin user."""
    with app.app_context():
        sm = app.appbuilder.sm
        user = sm.find_user(username="testadmin")
        if user is None:
            sm.add_user(
                username="testadmin",
                first_name="Test",
                last_name="Admin",
                email="testadmin@example.com",
                role=sm.find_role("Admin"),
                password="secret",
            )
    client = app.test_client()
    response = client.post(
        "/login/",
        data={"username": "testadmin", "password": "secret"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client


@pytest.fixture()
def session(app):
    return db.session


@pytest.fixture()
def admin():
    return Actor(username="admin", roles=frozenset({"Admin"}), is_admin=True)


@pytest.fixture()
def engineer():
    return Actor(username="engineer", roles=frozenset({"Engineer"}))


@pytest.fixture()
def reviewer():
    return Actor(username="reviewer", roles=frozenset({"Reviewer"}))


@pytest.fixture()
def plm_manager():
    return Actor(username="plm_manager", roles=frozenset({"PLM Manager"}))
