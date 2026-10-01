# Helix PLM

A configurable **Product Lifecycle Management (PLM)** system built on
[Flask-AppBuilder](https://flask-appbuilder.readthedocs.io/).

Helix manages product identity, revisions, product structures (BOMs),
requirements, documents, lifecycle workflows, frozen configurations
(baselines), and a full audit trail — with role-based security and a standard
FAB user interface.

The functional specification and phased build plan live in
[`docs/PLM_Application_Specification_and_Build_Plan.md`](docs/PLM_Application_Specification_and_Build_Plan.md).

---

## Features

- **Identity / revision separation** — every managed object has a stable `Item`
  identity and one or more immutable-once-released `ItemVersion`s.
- **Revision control** — major/minor revisioning, revision labels, and
  released-version immutability enforced in the service layer.
- **Business objects** — `Part`, `Document` (file upload + checksum),
  `Requirement`, and `Product` subtypes.
- **Product structures (BOM)** — directed `CONTAINS` relationships with
  quantity and find number, cycle detection, an interactive structure tree, and
  where-used (upstream) analysis.
- **Lifecycle management** — configurable states and role-guarded transitions
  (Draft → In Work → Review → Approved → Released → Obsolete).
- **Traceability relationships** — Satisfies, Derived From, References,
  Related To, plus extensible relationship types.
- **Baselines** — create, freeze, and compare configuration snapshots.
- **Audit trail** — append-only audit events for every mutation.
- **Search & filters** — FAB's standard search widget is enabled on every
  entity list view.
- **Summary dashboard** — a standard FAB `IndexView` showing counts by entity,
  revisions per lifecycle state, and baselines per status.
- **Role-based security** — Admin, PLM Manager, Engineer, Reviewer, Viewer.

## Technology stack

| Layer | Choice |
|---|---|
| Language | Python 3.12–3.13 |
| Web framework | Flask (via Flask-AppBuilder 5.2) |
| UI | Flask-AppBuilder `ModelView`s, actions, and bundled Bootstrap/Font Awesome |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (development); any SQLAlchemy URL in production |
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
structure, managed documents, a full requirement hierarchy with trace links, and
a frozen baseline over the released configuration.

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
| `DATABASE_URL` | SQLAlchemy database URI override | `sqlite:///plm.db` |
| `SECRET_KEY` | Flask session secret (set in production) | insecure dev value |

FAB-specific flags in `config.py`:

- `APP_NAME`, `APP_THEME`
- `FAB_INDEX_VIEW` — points at the summary dashboard
- `FAB_CREATE_DB` — create the schema on startup
- `SEED_REFERENCE_DATA` — seed reference data on startup
- `UPLOAD_FOLDER`, `FILE_ALLOWED_EXTENSIONS` — document uploads

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
  views/            FAB ModelViews, actions, create/revise forms
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
   most two menu levels, with all domain entities under **PLM** and reference
   data under **Administration**.

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

Implemented: core infrastructure, audit, business objects, the FAB UI,
revision control, product structures, lifecycle management, and baseline
management (spec Phases 0–7).

Not yet implemented (see the spec's build plan): configuration-analysis
reporting (Phase 8), security hardening (Phase 9), a dedicated audit-trail UI
(Phase 10), and the REST API (Phase 11).

---

## License

MIT — see [LICENSE](LICENSE).
