# Helix PLM

A configurable **Product Lifecycle Management (PLM)** system built on
[Flask-AppBuilder](https://flask-appbuilder.readthedocs.io/).

Helix manages product identity, revisions, product structures (BOMs),
functional breakdowns, requirements, documents, lifecycle workflows, frozen
configurations (baselines), and a full audit trail — with role-based security
and a standard FAB user interface.

The functional specification and phased build plan live in
[`docs/PLM_Application_Specification_and_Build_Plan.md`](docs/PLM_Application_Specification_and_Build_Plan.md).

---

## Features

- **Identity / revision separation** — every managed object has a stable `Item`
  identity and one or more immutable-once-released `ItemVersion`s.
- **Revision control** — major/minor revisioning, revision labels, and
  released-version immutability enforced in the service layer.
- **Business objects** — `Part`, `Document` (file upload + checksum +
  download link), `Requirement`, `Product`, and `Function` subtypes.
- **Product structures (BOM)** — directed `CONTAINS` relationships with
  quantity and find number, cycle detection, an interactive structure tree, and
  where-used (upstream) analysis.
- **Functional breakdown** — a `Function` object with a parent/child function
  hierarchy; products *perform* functions (`PERFORMS`) and parts *fulfill*
  them (`FULFILLS`), keeping the functional model separate from the physical
  BOM.
- **Lifecycle management** — configurable states and role-guarded transitions
  (Draft → In Work → Review → Approved → Released → Obsolete).
- **Traceability relationships** — Satisfies, Derived From, References,
  Related To, Performs, Fulfills, plus extensible relationship types.
- **Baselines** — create, freeze, and compare configuration snapshots.
- **Task-oriented navigation** — the menu groups the domain into Product Data,
  Change & Release, and Traceability; a *Pending Review* queue collects
  revisions awaiting approval; and lifecycle actions (submit, approve, release,
  obsolete) plus an audit-trail link are available directly on the list and
  show pages.
- **Related-view tabs** — show pages expose their linked objects as read-only
  tabs: a product's child parts, documents, performed functions, and parent
  requirements; a part's fulfilled functions; a function's fulfilling parts.
- **Audit trail** — append-only audit events for every mutation.
- **Search & filters** — FAB's standard search widget is enabled on every
  entity list view.
- **Summary dashboard** — a standard FAB `IndexView` showing counts by entity,
  revisions per lifecycle state, baselines per status, a pending-review badge,
  and quick-create actions.
- **Role-based security** — Admin, PLM Manager, Engineer, Reviewer, Viewer.

## Technology stack

| Layer | Choice |
|---|---|
| Language | Python 3.12–3.13 |
| Web framework | Flask (via Flask-AppBuilder 5.2) |
| UI | Flask-AppBuilder `ModelView`s, actions, and bundled Bootstrap/Font Awesome |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (development); PostgreSQL or any SQLAlchemy URL in production |
| Migrations | Alembic |
| Tooling | [uv](https://docs.astral.sh/uv/), pytest, ruff |

---

## Quick start

Requires Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install dependencies (creates .venv)
uv sync

# 2. Run the development server
uv run python run.py
```

The app starts on <http://localhost:8080>. On first boot it creates the SQLite
database (`plm.db`), the reference data, and the five application roles.

### Create the first admin user

No user is created automatically, so register one before logging in:

```bash
uv run flask --app run.py fab create-admin
```

You can also run the app with the Flask CLI:

```bash
uv run flask --app run.py run --port 8080
```

---

## Seeding data

Reference data and roles are seeded automatically on startup (idempotent).
Two CLI commands are also available:

```bash
# Re-seed reference data and roles explicitly
uv run flask --app run.py seed

# Load the HoverX-4 quadcopter demonstration dataset
uv run flask --app run.py seed-uav

# Remove that demonstration dataset
uv run flask --app run.py teardown-uav
```

The **HoverX-4** seed creates a realistic end-to-end example through the domain
services: one product (`PRD-HX4`) with two revisions, a three-level part
structure, managed documents, a full requirement hierarchy with trace links, a
functional breakdown (six top-level functions with child functions, performed
by the product and fulfilled by the parts), and a frozen baseline over the
released configuration.

---

## Configuration

Configuration lives in `config.py` and is selected with the `FLASK_CONFIG`
environment variable (`development` by default):

| Class | `FLASK_CONFIG` | Notes |
|---|---|---|
| `DevelopmentConfig` | `development` (default) | SQLite `plm.db`, debug on |
| `TestConfig` | `test` | In-memory SQLite, CSRF off |
| `ProductionConfig` | `production` | `FAB_CREATE_DB=False`; Alembic owns the schema |

Environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `FLASK_CONFIG` | Selects the config class | `development` |
| `DATABASE_URL` | SQLAlchemy database URI override (e.g. `postgresql+psycopg2://...`) | `sqlite:///plm.db` |
| `SECRET_KEY` | Flask session secret (set in production) | insecure dev value |

FAB-specific flags in `config.py`:

- `APP_NAME`, `APP_THEME`
- `FAB_INDEX_VIEW` — points at the summary dashboard
- `FAB_CREATE_DB` — create the schema on startup
- `SEED_REFERENCE_DATA` — seed reference data on startup
- `UPLOAD_FOLDER`, `FILE_ALLOWED_EXTENSIONS` — document uploads

---

## Running with PostgreSQL

Helix defaults to SQLite for development, but runs unchanged on PostgreSQL via
SQLAlchemy. Install a PostgreSQL driver alongside the project dependencies
(the default `psycopg2` dialect is used below):

```bash
# Add the PostgreSQL driver to the project's dependencies
uv add "psycopg2-binary"

# (Alternative: the newer driver, dialect postgresql+psycopg)
uv add "psycopg[binary]"
```

### 1. Create the database and user

On the PostgreSQL server, create an empty database — Helix creates its own
schema:

```sql
CREATE USER plm WITH PASSWORD 'change-me';
CREATE DATABASE plm OWNER plm;
```

### 2. Point the application at it

Set the connection URI through `DATABASE_URL` (the format differs slightly
depending on the driver you installed):

```bash
# psycopg2
export DATABASE_URL="postgresql+psycopg2://plm:change-me@localhost:5432/plm"

# psycopg 3
export DATABASE_URL="postgresql+psycopg://plm:change-me@localhost:5432/plm"
```

This works with both `FLASK_CONFIG=development` and `production`:

- **Development** — the app factory creates the schema directly
  (`FAB_CREATE_DB=True`) and seeds reference data + roles on first boot, just
  like with SQLite.
- **Production** — `FAB_CREATE_DB=False`; the schema must be created with
  Alembic (step 3). The connection string is also read by the Alembic
  environment, so migrations target the same database.

### 3. Create the schema (production only)

```bash
export FLASK_CONFIG=production
uv run alembic upgrade head
```

The migrations are plain SQLAlchemy DDL and are dialect-neutral (the SQLite
batch mode is only exercised for SQLite URLs), so the same scripts build the
schema on PostgreSQL — including FAB's `ab_*` security tables.

### 4. Create the first admin user and run

```bash
uv run flask --app run.py fab create-admin
uv run flask --app run.py run --port 8080
```

Reference data (item types, lifecycle states, roles) is seeded automatically
and idempotently on startup regardless of the backend. You can also load the
HoverX-4 demonstration dataset into PostgreSQL:

```bash
uv run flask --app run.py seed-uav
```

---

## Project structure

```
app/
  __init__.py       App factory; initialises SQLAlchemy + Flask-AppBuilder
  dashboard.py      SummaryIndexView (dashboard metrics)
  database.py       SQLite connection event listener
  seed.py           Idempotent reference data + role seeding
  uav_seed.py       HoverX-4 demonstration dataset
  cli.py            flask seed / seed-uav / teardown-uav commands
  models/           SQLAlchemy domain models (core, business, baseline, audit, reference)
  services/         Service layer — all writes go through here
  views/            FAB ModelViews, actions, create/revise forms, related-view tabs
  templates/        Approved custom templates (structure tree, baseline diff, dashboard)
config.py           Configuration classes
run.py              Development launcher
migrations/         Alembic migration scripts
tests/              Pytest unit + integration tests
docs/               Specification and build plan
```

### Architecture principles

1. **All writes go through the service layer.** FAB views are thin adapters;
   they never mutate the database directly.
2. **Released versions are immutable.** The service rejects edits to released
   revisions.
3. **Baselines are immutable snapshots** once frozen.
4. **Traceability is first-class** — every mutation produces an audit record.
5. **Standard FAB first.** Custom Jinja templates are used only for the two
   sanctioned exceptions (structure tree, baseline comparison) plus the
   dashboard `IndexView`.
6. **Consistent navigation.** One `list → show → edit` pattern per concept, at
   most two menu levels, with domain entities grouped by task (Product Data,
   Change & Release, Traceability) and reference data under **Administration**.

---

## Roles

| Role | Capabilities |
|---|---|
| `Admin` | Full system and security access |
| `PLM Manager` | Release/obsolete, baseline freeze, reference-data view |
| `Engineer` | Create/edit drafts, submit for review |
| `Reviewer` | Approve/reject transitions |
| `Viewer` | Read-only access |

Lifecycle and baseline actions are additionally guarded in the service layer,
not only by UI permissions.

---

## Testing & quality

```bash
# Run the test suite
uv run pytest

# With coverage
uv run pytest --cov=app

# Lint
uv run ruff check .
```

Tests cover the service layer (revisions, lifecycle, relationships, baselines,
documents, audit), the domain constraints, the seeded datasets, and the UI
(list/show routes, actions, forms, navigation, search, and the dashboard).

---

## Database migrations

Alembic migration scripts live in `migrations/versions/`. In production,
disable automatic schema creation (`FAB_CREATE_DB = False` /
`ProductionConfig`) and manage the schema explicitly:

```bash
uv run alembic upgrade head
```

---

## Status & roadmap

Implemented: core infrastructure, audit, business objects (including the
`Function` object and functional breakdown), the FAB UI, revision control,
product structures, lifecycle management, task-oriented navigation with
related-view tabs, and baseline management (spec Phases 0–7 and 10).

Not yet implemented (see the spec's build plan): configuration-analysis
reporting (Phase 8), security hardening (Phase 9), and the REST API
(Phase 11).

---

## License

MIT — see [LICENSE](LICENSE).
