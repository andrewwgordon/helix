# Product Lifecycle Management (PLM) Application Specification and Build Plan

**Document status:** Revised baseline (v2)
**Supersedes:** v1 initial concept
**Audience:** Engineering, product, QA

This document is the single source of truth for the functional specification,
domain model, architecture, service layer, Flask-AppBuilder implementation
guidance, security model, and phased build plan of the PLM application.

---

## Table of Contents

1. [Vision](#1-vision)
2. [Scope](#2-scope)
3. [Architectural Principles](#3-architectural-principles)
4. [Technology Stack](#4-technology-stack)
5. [Domain Model](#5-domain-model)
6. [Reference / Lookup Entities](#6-reference--lookup-entities)
7. [Core Identity & Revision Entities](#7-core-identity--revision-entities)
8. [Managed Business Objects](#8-managed-business-objects)
9. [Relationships & Product Structures](#9-relationships--product-structures)
10. [Versioning Semantics](#10-versioning-semantics)
11. [Lifecycle Management](#11-lifecycle-management)
12. [Configuration & Baseline Management](#12-configuration--baseline-management)
13. [Auditability](#13-auditability)
14. [Service Layer Design](#14-service-layer-design)
15. [Flask-AppBuilder Views](#15-flask-appbuilder-views)
16. [Security Model](#16-security-model)
17. [REST API](#17-rest-api)
18. [Database, Migrations & SQLite Notes](#18-database-migrations--sqlite-notes)
19. [Project Structure](#19-project-structure)
20. [Testing Strategy](#20-testing-strategy)
21. [Build Plan (Phased)](#21-build-plan-phased)
22. [Seed Data](#22-seed-data)
23. [Risks & Open Decisions](#23-risks--open-decisions)
24. [Glossary](#24-glossary)

---

# 1. Vision

Build a **configurable** Product Lifecycle Management platform enabling
organizations to manage product identity, revisions, structures, requirements,
documents, lifecycles, and frozen product configurations with full traceability.

The platform shall support:

- Item identity management
- Item version / revision management
- Product structures (BOM / assemblies)
- Requirements management
- Document management
- Lifecycle management and approval workflow
- Relationship traceability (upstream / downstream / where-used)
- Revision control
- Configuration management
- Baseline management
- Auditability
- Role-based security
- REST API access

# 2. Scope

## 2.1 MVP (Version 1.0)

- Core PLM infrastructure (Item / ItemVersion / relationships)
- Part, Document, Requirement, Product management
- Lifecycle states and transitions
- Revision control
- Product structures
- Baselines (create, freeze, list, compare)
- Role-based security
- Audit trail
- REST API for core resources

## 2.2 Explicitly Out of Scope for 1.0

- CAD / drawing geometry management
- Change Request / Change Order (ECR/ECO) workflow
- Effectivity by date/serial
- Supplier and procurement integration
- Multi-tenant isolation
- Real-time collaborative editing

> **Decision:** Change Request/Order is intentionally deferred, but the model
> reserves room for it (see [§23](#23-risks--open-decisions)). Revisit before
> 2.0 as it affects lifecycle and baseline semantics.

# 3. Architectural Principles

## 3.1 Separation of Identity and Revision

Every managed object consists of a stable **business identity** and one or more
**versions**:

```text
Item          = stable business identity (never deleted while referenced)
    └── ItemVersion = immutable-once-released revision
```

Examples:

```text
PART-10001
    Rev A
    Rev B

REQ-0001
    Rev A
```

## 3.2 Core Principles

1. **Identity/version separation** — never store revision data on `Item`.
2. **All writes go through the service layer.** FAB views are adapters; they
   must not mutate the database directly. CRUD views delegate to services in
   lifecycle hooks (see [§15](#15-flask-appbuilder-views)).
3. **Released is immutable.** Once an `ItemVersion` reaches `Released`, its
   business attributes and outgoing relationships are frozen.
4. **Baselines are immutable snapshots.** A frozen baseline never changes.
5. **Traceability is first-class.** Every mutation produces an audit record.
6. **Constraints are enforced in the database, not only in the UI.** Uniqueness,
   referential integrity, and lifecycle rules have database-level guards where
   feasible.
7. **No orphan cycles.** Structures (`Contains`) must be acyclic.
8. **Standard Flask-AppBuilder first.** Maximise the use of built-in
   `ModelView`, `MasterDetailView`, `MultipleView`, `CompactCRUDMixin`, `@action`
   methods, chart views, and bundled widgets. Create custom Flask template views
   **only when no standard FAB view can meet the requirement**, and never
   re-implement CRUD that FAB already provides. See
   [§3.3](#33-user-interface-architecture).
9. **Simple, consistent navigation.** The UI exposes one predictable pattern per
   concept (list → show → edit) across all domains, reusing FAB's list/show/edit
   widgets and layouts. Navigation depth is capped, menu categories follow a
   single consistent taxonomy, and equivalent entities are reached the same way.
   See [§3.3](#33-user-interface-architecture) and
   [§15.6](#156-navigation).

## 3.3 User Interface Architecture

### 3.3.1 Standard Flask-AppBuilder First

The UI is built from FAB's generated views and bundled widgets. Custom Jinja
templates are treated as a **last resort**.

**Preference order (highest to lowest):**

1. `ModelView` with configured `list_columns`, `show_fieldsets`,
   `add_fieldsets`, `edit_fieldsets`, `base_filters`, `related_views`, and
   `@action` methods.
2. Composite FAB views: `MasterDetailView`, `MultipleView`, `CompactCRUDMixin`,
   and `related_views` tabs — preferred over hand-built pages that combine the
   same data.
3. FAB-provided widgets (`ListWidget`, `ListLinkWidget`, `ListThumbnail`,
   `ShowWidget`, `FormWidget`, and their variants). Use as-is before
   subclassing; subclass only to change a template, never to re-implement
   behavior.
4. Chart views (`DirectByChartView`, `GroupByChartView`) for dashboard/reporting
   needs that aggregate existing models.
5. `BaseView` + a custom template **only** for functionality that has no model
   or list/show/edit equivalent (see the allowed exceptions below).

**Rules**

- No custom form, list, or show templates where a `ModelView` suffices.
- No custom CSS/JS to replicate widget behavior; prefer FAB configuration.
- Every custom template must be justified in the pull request against the
   preference order above.
- Reuse FAB's list/show/edit block structure and `appbuilder/base.html`; extend
   rather than fork if a template override is genuinely required.

### 3.3.2 Consistent Navigation and Interaction

- **One interaction pattern:** every domain entity uses the standard
  `list → show → edit` flow. Add/revise/lifecycle/baseline operations are
  exposed as `@action` buttons on the list or show page, not as bespoke pages.
- **One taxonomy:** menu categories are stable and shared across domains;
  logically similar entities live under the same category (for example all
  business objects under **PLM**, all reference data under **Administration**).
- **Bounded depth:** menus are at most two levels deep; entity pages are one
  click from their list.
- **Consistent labels and icons:** a concept uses the same label, icon, and
  ordering everywhere it appears.
- **No parallel UI:** reporting/analysis features operate on existing models
  and list views (filters, chart views, `related_views`) rather than a separate
  navigation tree.

**Allowed exceptions (custom views)** — only these justify a `BaseView` and
custom template, and each must be documented:

| Exception | Rationale | Preferred FAB alternative attempted first |
|---|---|---|
| Interactive multi-level **structure tree** | No standard FAB widget renders an expandable recursive tree | `related_views` / `MasterDetailView` with a filtered list first |
| **Baseline comparison diff** | Requires a side-by-side computed diff, not a model list | A read-only `ModelView` over a diff result first |

All other reporting and analysis requirements **must** be met with filters,
`related_views`, `MultipleView`, or chart views on standard `ModelView`s.

# 4. Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12–3.13 (target 3.13) |
| Web framework | Flask |
| Application framework | Flask-AppBuilder 5.2.x |
| ORM | SQLAlchemy 2.0.x (**not 2.1**) |
| Database | **SQLite 3** (WAL mode) |
| Migrations | Alembic (with `render_as_batch=True`) |
| Forms/validation | WTForms / marshmallow-sqlalchemy |
| Auth | FAB `AUTH_DB` (extensible to LDAP/OAuth/SAML) |
| API | FAB `ModelRestApi` + JWT |
| Testing | pytest, pytest-flask |

> **Note on Python version:** Flask-AppBuilder 5.2.x officially supports Python
> up to 3.13. The development virtualenv must be pinned to **3.13** to avoid
> unsupported 3.14 behavior. This is a required remediation.

> **Note on SQLAlchemy version (verified):** FAB 5.2.3 declares
> `SQLAlchemy <3`, but its dependency `sqlalchemy-utils` 0.42.1 subclasses
> `sqlalchemy.orm.attributes.ScalarAttributeImpl`, which was **removed in
> SQLAlchemy 2.1**. Importing FAB under SQLAlchemy 2.1 raises `AttributeError`.
> The project therefore pins **`sqlalchemy>=2.0,<2.1`** (verified working:
> SQLAlchemy 2.0.54). Revisit when `sqlalchemy-utils` supports 2.1.

> **Note on declarative metadata (verified):** FAB and Flask-SQLAlchemy use
> **two separate metadata objects**. `flask_appbuilder.models.sqla.Base.metadata`
> holds the 12 `ab_*` security tables; `db.metadata` is empty. All PLM models
> **must inherit `flask_appbuilder.Model`** so they share FAB's metadata and are
> created/audited/migrated together with the security tables. Schema creation
> uses `flask_appbuilder.models.sqla.Base.metadata.create_all(...)`, and Alembic
> targets that same metadata (see [§18.2](#182-migrations-alembic)).

> **Note on FAB 5.2 API surface (verified):** in FAB 5.2.3 the database helper
> is imported as `from flask_appbuilder.models.sqla.base import SQLA` (it is not
> re-exported at the package root), and `AppBuilder.init_app` must be called
> **inside an application context** because the security manager uses
> `current_app` during construction.

## 4.1 Why SQLite

SQLite was selected for the initial implementation because it is:

- Zero-administration and file-based — ideal for development, demos, and
  single-node deployments.
- Fully supported by SQLAlchemy 2.x and Alembic.

Limitations that must be accepted and mitigated:

- **Single writer.** Mitigate with WAL mode and short transactions.
- **Foreign keys are OFF by default.** Enforce with a `PRAGMA` connection event.
- **Limited `ALTER TABLE`.** Use Alembic batch migrations.
- **Concurrency.** Not suited to high-concurrency production; keep the
  repository layer portable so a future move to PostgreSQL is low-cost.

# 5. Domain Model

## 5.1 Entity Relationship Overview

```text
item_type ──< item >── item_version ──< item_relationship >── item_version
                 │           │
                 │           ├──< part
                 │           ├──< document
                 │           ├──< requirement
                 │           └──< product
                 │
                 └── current_version_id ──> item_version (circular, use_alter)

lifecycle_state ──< item_version
lifecycle_transition (from_state → to_state, configurable)

baseline ──< baseline_member >── item_version
audit_event (polymorphic, references entity + revision)
```

## 5.2 General Column Conventions

Every business/reference table includes:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Autoincrement |
| `created_on` | DateTime | FAB `AuditMixin` |
| `changed_on` | DateTime | FAB `AuditMixin` |
| `created_by_fk` | Integer FK `ab_user.id` | FAB `AuditMixin`, nullable |
| `changed_by_fk` | Integer FK `ab_user.id` | FAB `AuditMixin`, nullable |
| `is_active` | Boolean | Where soft-deactivation applies |

> **Audit columns are included from Phase 1.** Because SQLite `ALTER TABLE` is
> limited, adding audit columns later would require a batch migration on every
> table. Define them now.
>
> **Implementation note (verified):** FAB's `AuditMixin` marks `created_by_fk`
> and `changed_by_fk` as `NOT NULL` with a `g.user` default, which raises
> `IntegrityError` during seeding, CLI commands, and background/service calls.
> The PLM schema therefore uses `app.models.mixins.AuditMixin`, an otherwise
> identical mixin that makes both columns **nullable** (as specified above).

## 5.3 Data Type Conventions (SQLite)

| Logical type | SQLAlchemy type | SQLite storage |
|---|---|---|
| Short text / code | `String(n)` | TEXT |
| Long text | `Text` | TEXT |
| Integer | `Integer` | INTEGER |
| Boolean | `Boolean` | INTEGER 0/1 |
| Decimal | `Numeric(18, 6)` | NUMERIC (stored as TEXT/REAL) |
| Date | `Date` | TEXT ISO-8601 |
| Timestamp | `DateTime` | TEXT ISO-8601 |
| Binary/hash | `String(64)` | TEXT (SHA-256 hex) |

**Mandatory FK enforcement** (applied at engine creation):

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
```

# 6. Reference / Lookup Entities

Reference entities are small, admin-managed lookup tables. They make the
platform configurable instead of hardcoding enums.

## 6.1 ItemType

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `code` | String(32) | UNIQUE, NOT NULL |
| `name` | String(64) | NOT NULL |
| `description` | String(255) | |
| `is_active` | Boolean | NOT NULL, default True |

Seed: `Part`, `Document`, `Requirement`, `Product`.

## 6.2 LifecycleState

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `code` | String(32) | UNIQUE, NOT NULL |
| `name` | String(64) | NOT NULL |
| `sequence` | Integer | NOT NULL — ordering of states |
| `is_terminal` | Boolean | NOT NULL, default False |
| `is_releasable` | Boolean | NOT NULL, default False — may enter baseline |
| `description` | String(255) | |

Seed: `Draft`, `In Work`, `Review`, `Approved` *(releasable)*,
`Released` *(releasable, terminal)*, `Obsolete` *(terminal)*.

> **Note:** `Approved` and `Released` are both releasable. Revisions superseded
> by a newer revision are tracked via `ItemVersion.superseded_by_id`, not a
> separate lifecycle state.

## 6.3 RelationshipType

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `code` | String(32) | UNIQUE, NOT NULL |
| `name` | String(64) | NOT NULL |
| `is_structural` | Boolean | NOT NULL, default False — participates in BOM hierarchy |
| `allows_quantity` | Boolean | NOT NULL, default False |
| `allows_find_number` | Boolean | NOT NULL, default False |
| `is_active` | Boolean | NOT NULL, default True |

Seed:

| code | name | structural | qty | find |
|---|---|---|---|---|
| `CONTAINS` | Contains | ✅ | ✅ | ✅ |
| `REFERENCES` | References | ❌ | ❌ | ❌ |
| `SATISFIES` | Satisfies | ❌ | ❌ | ❌ |
| `DERIVED_FROM` | Derived From | ❌ | ❌ | ❌ |
| `RELATED_TO` | Related To | ❌ | ❌ | ❌ |

## 6.4 LifecycleTransition

Makes the lifecycle workflow **configurable and enforced** rather than a fixed
picture.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `from_state_id` | Integer | FK `lifecycle_state.id`, NOT NULL |
| `to_state_id` | Integer | FK `lifecycle_state.id`, NOT NULL |
| `required_role_id` | Integer | FK `ab_role.id`, nullable — min role to perform |
| `is_active` | Boolean | NOT NULL, default True |

- UNIQUE `(from_state_id, to_state_id)`.
- CHECK `from_state_id <> to_state_id`.

Seed (see [§11](#11-lifecycle-management) for the full table).

## 6.5 Domain Lookups

| Table | Purpose | Seed examples |
|---|---|---|
| `unit_of_measure` | Part UoM | `EA`, `MM`, `M`, `KG`, `L` |
| `make_buy_code` | Part sourcing | `MAKE`, `BUY`, `MAKE_OR_BUY` |
| `verification_method` | Requirement verification | `Test`, `Analysis`, `Inspection`, `Demonstration` |
| `priority_code` | Requirement priority | `Mandatory`, `High`, `Medium`, `Low` |
| `product_family` | Product grouping | user-defined |
| `market` | Target market | user-defined |

Each lookup table follows the standard shape: `id`, `code` (UNIQUE),
`name`, `description`, `is_active`, audit columns.

# 7. Core Identity & Revision Entities

## 7.1 Item

Business identity. Never carries revision-specific data.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `item_type_id` | Integer | FK `item_type.id`, NOT NULL, `ondelete=RESTRICT` |
| `item_number` | String(64) | NOT NULL |
| `current_version_id` | Integer | FK `item_version.id`, nullable, `use_alter=True`, `ondelete=SET NULL` |
| `created_at` | DateTime | NOT NULL, server default now |

**Constraints**

- UNIQUE `(item_type_id, item_number)`.
- INDEX on `current_version_id`.

**Relationship**

```python
current_version = relationship(
    "ItemVersion",
    foreign_keys=[current_version_id],
    post_update=True,          # breaks the circular INSERT dependency
)
versions = relationship(
    "ItemVersion",
    back_populates="item",
    foreign_keys="ItemVersion.item_id",
    cascade="all, delete-orphan",
)
```

> **Circular FK handling:** `Item.current_version_id` and
> `ItemVersion.item_id` form a cycle. `use_alter=True` on the FK plus
> `post_update=True` on the relationship is mandatory. Without it, table
> creation and inserts fail.

**`current_version` resolution rule:** `current_version_id` points to the
**latest created** version (highest `version_sequence`) regardless of lifecycle
state. "Latest released" is a separate query
(`ItemVersion` where state `is_releasable`, ordered by `version_sequence`).

## 7.2 ItemVersion

Revision entity.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `item_id` | Integer | FK `item.id`, NOT NULL, `ondelete=CASCADE` |
| `version_sequence` | Integer | NOT NULL, CHECK `>= 1` |
| `major_revision` | Integer | NOT NULL, default 0, CHECK `>= 0` |
| `minor_revision` | Integer | NOT NULL, default 0, CHECK `>= 0` |
| `revision_label` | String(16) | NOT NULL, derived (e.g. `A.1`) |
| `description` | Text | |
| `lifecycle_state_id` | Integer | FK `lifecycle_state.id`, NOT NULL |
| `superseded_by_id` | Integer | FK `item_version.id`, nullable |
| `effective_from` | Date | nullable |
| `effective_to` | Date | nullable, CHECK `effective_to IS NULL OR effective_to >= effective_from` |
| `created_at` | DateTime | NOT NULL, server default now |

**Constraints**

- UNIQUE `(item_id, version_sequence)`.
- UNIQUE `(item_id, major_revision, minor_revision)`.
- INDEX on `lifecycle_state_id`.

> **`revision_label` is derived, not user-entered.** It is computed on write by
> the service layer from `major_revision`/`minor_revision` (see
> [§10](#10-versioning-semantics)). It is stored for display and reporting.

## 7.3 ItemRelationship

Version-to-version directed edge.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `relationship_type_id` | Integer | FK `relationship_type.id`, NOT NULL |
| `source_item_version_id` | Integer | FK `item_version.id`, NOT NULL, `ondelete=CASCADE` |
| `target_item_version_id` | Integer | FK `item_version.id`, NOT NULL, `ondelete=CASCADE` |
| `quantity` | Numeric(18, 6) | nullable, CHECK `> 0` |
| `find_number` | String(32) | nullable |
| `sort_order` | Integer | nullable, default 0 |
| `created_at` | DateTime | NOT NULL, server default now |

**Constraints**

- UNIQUE `(relationship_type_id, source_item_version_id, target_item_version_id)`.
- CHECK `source_item_version_id <> target_item_version_id`.
- INDEX on `source_item_version_id`, `target_item_version_id`.

**Semantics**

- For structural relationships (`is_structural=True`), `source` is the **parent**
  and `target` is the **child**.
- `quantity` and `find_number` are only valid when the relationship type
  permits them (enforced in the service layer; see [§14](#14-service-layer-design)).
- The service layer must reject relationships that would create a **cycle** in
  the structural graph.

## 7.4 AuditEvent

Application-level audit trail beyond FAB's `AuditMixin` timestamps.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `event_type` | String(32) | NOT NULL — `CREATE`, `REVISE`, `STATE_CHANGE`, `REL_ADD`, `REL_REMOVE`, `BASELINE_CREATE`, `BASELINE_FREEZE`, `UPDATE`, `DELETE` |
| `entity_type` | String(64) | NOT NULL — logical entity name |
| `entity_id` | Integer | NOT NULL |
| `item_id` | Integer | FK `item.id`, nullable — for cross-revision queries |
| `from_value` | String(255) | nullable |
| `to_value` | String(255) | nullable |
| `comment` | Text | nullable |
| `actor_id` | Integer | FK `ab_user.id`, nullable |
| `created_at` | DateTime | NOT NULL, server default now |

**Constraints**

- INDEX `(entity_type, entity_id)`.
- INDEX `(item_id, created_at)`.

# 8. Managed Business Objects

Business objects use **shared-primary-key subtypes** of `ItemVersion`: each
subtype table's `item_version_id` is both its primary key and a foreign key to
`item_version.id` (1:1 composition, `ondelete=CASCADE`). This keeps the
generic identity/revision model clean and avoids a polymorphic discriminator
column. Access is via `ItemVersion.part` / `.document` / `.requirement` /
`.product` (at most one is populated, according to the item type).

> **Design note:** the initial draft called this "joined-table inheritance",
> but the column naming (`item_version_id`, not `id`) and the absence of a
discriminator column indicate 1:1 composition. Services enforce that the
> subtype matches the item's `ItemType`.

## 8.1 Part

| Column | Type | Constraints |
|---|---|---|
| `item_version_id` | Integer | PK, FK `item_version.id`, `ondelete=CASCADE` |
| `unit_of_measure_id` | Integer | FK `unit_of_measure.id`, NOT NULL |
| `make_buy_code_id` | Integer | FK `make_buy_code.id`, nullable |
| `weight` | Numeric(18, 6) | nullable, CHECK `>= 0` |
| `weight_uom_id` | Integer | FK `unit_of_measure.id`, nullable |
| `material` | String(128) | nullable |

## 8.2 Document

| Column | Type | Constraints |
|---|---|---|
| `item_version_id` | Integer | PK, FK `item_version.id`, `ondelete=CASCADE` |
| `file_name` | String(255) | NOT NULL |
| `mime_type` | String(128) | nullable |
| `file_size` | Integer | nullable, CHECK `>= 0` |
| `file_path` | String(512) | NOT NULL — relative path under `UPLOAD_FOLDER` |
| `checksum_sha256` | String(64) | nullable |

> **File handling:** Files are stored under `UPLOAD_FOLDER` using FAB's
> `FileManager`/`get_file_original_name`, never as absolute paths. Download
> access is permission-checked by the view. `file_path` is relative to
> `UPLOAD_FOLDER`.

## 8.3 Requirement

| Column | Type | Constraints |
|---|---|---|
| `item_version_id` | Integer | PK, FK `item_version.id`, `ondelete=CASCADE` |
| `requirement_text` | Text | NOT NULL |
| `verification_method_id` | Integer | FK `verification_method.id`, nullable |
| `priority_code_id` | Integer | FK `priority_code.id`, nullable |

> **Identifier:** The requirement identifier is `Item.item_number`
> (e.g. `REQ-0001`). The legacy `requirement_identifier` column is **removed**
> to prevent drift. Displays use `item_number`.

## 8.4 Product

| Column | Type | Constraints |
|---|---|---|
| `item_version_id` | Integer | PK, FK `item_version.id`, `ondelete=CASCADE` |
| `product_family_id` | Integer | FK `product_family.id`, nullable |
| `market_id` | Integer | FK `market.id`, nullable |
| `platform` | String(128) | nullable |
| `release_target` | Date | nullable |

# 9. Relationships & Product Structures

Product structures are represented by `ItemRelationship` rows whose
`relationship_type.is_structural = True` (i.e. `CONTAINS`).

```text
Product PRD-100 Rev B
 ├─ Part PART-10001 Rev A   (qty 2, find 10)
 ├─ Part PART-10002 Rev C   (qty 1, find 20)
 ├─ Requirement REQ-0001 Rev B
 └─ Document DOC-0005 Rev D
```

## 9.1 Structure Rules

1. A structural edge may only be created between **specific versions**, never
   between `Item`s.
2. **No cycles** — the service must traverse the ancestor chain of the target
   before insert and reject any path back to the source.
3. A parent may contain the same child at most once per relationship type
   (enforced by the unique constraint). Additional occurrences differ by
   `find_number`.
4. `quantity` defaults to `1` when the relationship type allows quantity and
   none is supplied.
5. `find_number` is unique per parent when supplied.

## 9.2 Traversal APIs

- `get_upstream(version)` — all ancestors (where-used).
- `get_downstream(version)` — all descendants (BOM explosion).
- Both support `max_depth`, `relationship_type`, and cycle-safe iteration.
- Implement with recursive CTEs where supported; SQLite 3.8.3+ supports
  `WITH RECURSIVE`. Provide a pure-Python fallback in `RelationshipService`.

# 10. Versioning Semantics

## 10.1 Revision Model

- `major_revision` — incremented for **form/fit/function** changes that make the
  new revision incompatible or require re-approval of dependents.
- `minor_revision` — incremented for **documentation, comment, or
  non-functional** changes that do not alter fit/form/function.
- `version_sequence` — a monotonic counter per `Item`, incremented on every new
  version regardless of major/minor.

## 10.2 Revision Label

Derived as:

```text
major 0, minor 0   -> "A"      (initial)
major N, minor 0   -> chr(ord('A') + N)          e.g. N=1 -> "B"
major N, minor M>0 -> chr(ord('A') + N) + "." + M e.g. "B.1"
```

Implementation is centralized in `_format_revision(major, minor)` and tested.

## 10.3 `revise_item` Rules

`ItemService.revise_item(item_id, change_type, actor, **attrs)`:

1. Load the current version. Reject if the item has **no** current version
   (create the first version instead).
2. Determine the new major/minor:
   - `change_type="major"` → `major+1`, `minor=0`.
   - `change_type="minor"` → `major` unchanged, `minor+1`.
3. New `version_sequence = max(existing) + 1`.
4. Clone: all business-object attributes (Part/Document/Requirement/Product),
   and **copy structural + non-structural relationships** from the source
   version. (Configurable flag `copy_relationships=True` default.)
5. New version lifecycle = `Draft`.
6. Set `superseded_by_id` on the previous version to the new version.
7. Update `Item.current_version_id` to the new version.
8. Write an `AuditEvent(event_type="REVISE")`.
9. Execute in a single transaction; on any failure, roll back fully.

## 10.4 Immutability Rule

When an `ItemVersion` is in a state where `lifecycle_state.is_releasable` is
true **or** it has been frozen into a baseline, its business attributes and
relationships are read-only. Attempts to modify throw
`ReleasedVersionImmutableError`.

# 11. Lifecycle Management

## 11.1 State Diagram

```text
Draft
  │
  ▼
In Work
  │
  ▼
Review
  │
  ▼
Approved ──────┐
  │            │
  ▼            │
Released       │
  │            │
  ▼            │
Obsolete ◀─────┘ (from Approved, release may be skipped for non-hardware docs)
```

## 11.2 Transition Table (configurable, seeded into `lifecycle_transition`)

| From | To | Allowed | Min role |
|---|---|---|---|
| Draft | In Work | ✅ | Engineer |
| In Work | Review | ✅ | Engineer |
| Review | In Work | ✅ (rework) | Reviewer |
| Review | Approved | ✅ | Reviewer |
| Approved | Review | ✅ (reject) | Reviewer |
| Approved | Released | ✅ | PLM Manager |
| Released | Obsolete | ✅ | PLM Manager |
| Draft | Obsolete | ✅ (abandon) | PLM Manager |
| * | * | ❌ | — |

Any transition not present in the table (and `is_active`) is **rejected** with
`InvalidLifecycleTransitionError`.

## 11.3 Lifecycle Rules

1. Transitions are validated by `LifecycleService` against
   `lifecycle_transition`.
2. The acting user must hold at least `required_role_id`.
3. Entering a releasable state requires the version to have **no validation
   errors** (business rule hook, extensible).
4. `Obsolete` and `Released` are terminal unless an explicit reverse transition
   is configured.
5. Every transition writes an `AuditEvent(event_type="STATE_CHANGE")` with
   `from_value`/`to_value` = state codes and an optional comment.

# 12. Configuration & Baseline Management

## 12.1 Baseline

Immutable, named snapshot of a product configuration.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `baseline_number` | String(32) | UNIQUE, NOT NULL |
| `baseline_name` | String(128) | NOT NULL |
| `product_version_id` | Integer | FK `item_version.id`, NOT NULL |
| `status` | String(16) | NOT NULL, `DRAFT` or `FROZEN` |
| `frozen_at` | DateTime | nullable |
| `description` | Text | nullable |

Standard audit columns (`created_on`, `changed_on`, `created_by_fk`,
`changed_by_fk`) are present per [§5.2](#52-general-column-conventions).

**Constraints**

- CHECK `status IN ('DRAFT','FROZEN')`.
- CHECK `(status = 'DRAFT' AND frozen_at IS NULL) OR (status = 'FROZEN' AND frozen_at IS NOT NULL)`.

## 12.2 BaselineMember

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `baseline_id` | Integer | FK `baseline.id`, NOT NULL, `ondelete=CASCADE` |
| `item_version_id` | Integer | FK `item_version.id`, NOT NULL |
| `parent_member_id` | Integer | FK `baseline_member.id`, nullable — snapshots structure |
| `quantity` | Numeric(18,6) | nullable |
| `find_number` | String(32) | nullable |

**Constraints**

- UNIQUE `(baseline_id, item_version_id, parent_member_id)`.

## 12.3 Baseline Rules

1. **Only releasable versions may enter a baseline** (lifecycle state
   `is_releasable = True`). Validation runs for the root and **every captured
   descendant**.
2. When a baseline is created, `BaselineService` performs a full recursive
   structure explosion from `product_version_id` and records each descendant
   as a member with its `parent_member_id` linkage.
3. A baseline may be created in `DRAFT` (members editable), then **frozen**.
4. **Freezing is one-way.** A `FROZEN` baseline is immutable: no member
   add/remove, no re-freeze.
5. `compare_baselines(a, b)` returns a structured diff:
   - `added` — members in B not in A
   - `removed` — members in A not in B
   - `changed` — same item, different `item_version_id`
   - `unchanged` — same item and version
6. `list_members(baseline_id)` returns members ordered by structure depth.

> **Scope clarification:** A baseline captures exactly one product version and
> its descendant structure. It does **not** capture unrelated items.

# 13. Auditability

Auditability has three layers:

| Layer | Mechanism | Covers |
|---|---|---|
| Row metadata | FAB `AuditMixin` (`created_on`, `changed_on`, `created_by_fk`, `changed_by_fk`) | Every table |
| Domain events | `audit_event` table | Lifecycle, revisions, relationships, baselines |
| Immutable snapshots | `baseline` / `baseline_member` | Released configurations |

Requirements:

1. Every service mutating operation writes an `AuditEvent` within the same
   transaction.
2. Audit records are **append-only**; no update/delete permissions are granted
   to any non-Admin role.
3. Audit records expose `actor_id`, timestamp, entity, and before/after values
   where meaningful.
4. `AuditEventService.query(entity_type, entity_id)` and
   `query_by_item(item_id)` provide read access for history views.

# 14. Service Layer Design

All business operations execute through domain services. Services own
**transaction boundaries**, **authorization checks**, **validation**, and
**audit emission**.

## 14.1 Common Service Conventions

- Services are constructed with a SQLAlchemy `Session` and an `Actor` context
  (current user + roles).
- Public methods raise domain exceptions (see [§14.8](#148-exceptions)) on
  violation; they never return `None` to signal failure.
- Mutating methods wrap their work in `with session.begin():` (or the caller's
  transaction) and emit audit events.
- Services accept **IDs**, not ORM instances, at their public boundary.
- Services never render HTTP responses.

## 14.2 ItemService

```python
create_item(item_type_code: str, item_number: str, actor) -> Item
create_version(item_id: int, actor, *, description=None,
               lifecycle_code="DRAFT", business_data: dict | None = None) -> ItemVersion
revise_item(item_id: int, change_type: str, actor, *,
            copy_relationships: bool = True,
            business_data: dict | None = None) -> ItemVersion
change_lifecycle(version_id: int, to_state_code: str, actor, comment=None) -> ItemVersion
get_current_version(item_id: int) -> ItemVersion | None
list_versions(item_id: int) -> list[ItemVersion]
```

## 14.3 ProductService

```python
create_product(item_number, actor, *, description=None,
               product_family=None, market=None,
               platform=None, release_target=None) -> Product
revise_product(product_item_id, change_type, actor, **kwargs) -> ItemVersion
get_structure(product_version_id, max_depth=None) -> StructureNode
add_child(parent_version_id, child_version_id, actor, *,
          quantity=None, find_number=None) -> ItemRelationship
remove_child(parent_version_id, child_version_id, actor) -> None
```

## 14.4 PartService

```python
create_part(item_number, actor, *, uom_code, make_buy=None,
            weight=None, material=None, description=None) -> Part
revise_part(item_id, change_type, actor, **kwargs) -> ItemVersion
```

## 14.5 DocumentService

```python
create_document(item_number, actor, *, uploaded_file, description=None) -> Document
revise_document(item_id, change_type, actor, *,
                new_file: FileStorage | None = None, **kwargs) -> ItemVersion
```

## 14.6 RequirementService

```python
create_requirement(item_number, actor, *, requirement_text,
                   verification_method=None, priority=None,
                   description=None) -> Requirement
revise_requirement(item_id, change_type, actor, **kwargs) -> ItemVersion
```

## 14.7 RelationshipService

```python
add_relationship(source_version_id, target_version_id, relationship_type_code,
                 actor, *, quantity=None, find_number=None) -> ItemRelationship
remove_relationship(relationship_id, actor) -> None
get_upstream(version_id, *, relationship_type=None, max_depth=None) -> list[ItemVersion]
get_downstream(version_id, *, relationship_type=None, max_depth=None) -> list[ItemVersion]
would_create_cycle(source_version_id, target_version_id) -> bool
```

## 14.8 LifecycleService

```python
submit_for_review(version_id, actor, comment=None) -> ItemVersion
approve(version_id, actor, comment=None) -> ItemVersion
release(version_id, actor, comment=None) -> ItemVersion
obsolete(version_id, actor, comment=None) -> ItemVersion
available_transitions(version_id, actor) -> list[LifecycleTransition]
can_transition(version_id, to_state_code, actor) -> bool
```

## 14.9 BaselineService

```python
create_baseline(product_version_id, baseline_number, baseline_name, actor,
                *, description=None, freeze_immediately=False) -> Baseline
add_member(baseline_id, item_version_id, actor, *,
           parent_member_id=None, quantity=None, find_number=None) -> BaselineMember
freeze_baseline(baseline_id, actor) -> Baseline
compare_baselines(baseline_a_id, baseline_b_id) -> BaselineDiff
list_members(baseline_id) -> list[BaselineMember]
```

## 14.10 AuditEventService

```python
record(event_type, entity_type, entity_id, actor, *,
       item_id=None, from_value=None, to_value=None, comment=None) -> AuditEvent
query(entity_type, entity_id) -> list[AuditEvent]
query_by_item(item_id) -> list[AuditEvent]
```

## 14.11 Exceptions

```text
PlmError                       (base)
├── NotFoundError
├── ValidationError            (field-level detail)
├── ConflictError              (uniqueness, duplicate edge)
├── InvalidLifecycleTransitionError
├── ReleasedVersionImmutableError
├── BaselineFrozenError
├── BaselineValidationError    (non-releasable member)
├── RelationshipCycleError
└── AuthorizationError
```

FAB views/APIs map these to HTTP status codes in one place
(400/404/409/403) via an error-handling helper.

## 14.12 Transaction & Concurrency Notes (SQLite)

- Keep write transactions short; do not perform file I/O inside a DB
  transaction.
- Use `version_sequence = SELECT MAX(...) + 1` inside the transaction; SQLite's
  writer lock provides serialization. Optionally add a `UNIQUE` retry loop.
- Document uploads happen **before** the DB transaction and are cleaned up on
  rollback.

# 15. Flask-AppBuilder Views

Views are thin adapters. Mutations delegate to services; `ModelView`
`pre_add`/`pre_update`/`pre_delete` hooks call service methods and can abort by
raising `ValidationError`.

> **UI principle (see [§3.3](#33-user-interface-architecture)):** use standard
> FAB `ModelView`s, composite views, actions, and bundled widgets. Custom Flask
> template views are introduced **only** for the documented exceptions in
> [§15.5](#155-custom-views-exceptions-only). Every entity follows the same
> `list → show → edit` pattern and appears under the same menu taxonomy.

## 15.1 Reference Views (Read-heavy / Admin)

| View | Model | Permissions |
|---|---|---|
| `ItemTypeModelView` | ItemType | list/show/add/edit (Admin) |
| `LifecycleStateModelView` | LifecycleState | list/show/add/edit (Admin) |
| `LifecycleTransitionModelView` | LifecycleTransition | list/show/add/edit (Admin) |
| `RelationshipTypeModelView` | RelationshipType | list/show/add/edit (Admin) |
| Lookup `*ModelView`s | UoM, MakeBuy, VerificationMethod, Priority, Family, Market | list/show/add/edit (Admin) |

## 15.2 Core Views

| View | Model | Notes |
|---|---|---|
| `ItemModelView` | Item | list/show; edit restricted to `item_number`/type with care |
| `ItemVersionModelView` | ItemVersion | list/show/about; **no direct add/edit** |
| `ItemRelationshipModelView` | ItemRelationship | list/show; add via service |

`ItemVersionModelView` uses:
- `base_permissions` covering `can_list`, `can_show`, `audit`, the lifecycle
  actions (`submit_for_review`, `approve`, `release`, `obsolete`), the structure
  actions (`structure`, `where_used`, `add_child`).
- A custom `audit` action that redirects to the audit trail filtered by
  ``item_id`` (`?_flt_0_item_id=<id>`), and the lifecycle actions that call
  `LifecycleService`.

> **FAB action permissions:** an ``@action("audit", ...)`` method generates the
> permission **`audit`** (not ``can_audit``); the action name is the permission
> identifier.

## 15.3 Business Object Views

| View | Model | Notes |
|---|---|---|
| `PartModelView` | Part | Create/revise via actions + `pre_add` |
| `DocumentModelView` | Document | FileColumn widget, download permission |
| `RequirementModelView` | Requirement | |
| `ProductModelView` | Product | Structure editor/browser actions |

Each view:

- `list_columns` include `item_number`, `revision_label`, lifecycle state.
- `base_permissions` per the permission matrix ([§16](#16-security-model)).
- `@action("revise_major"/"revise_minor")` calling `*Service.revise_*` (the
  document view opens a revise form so a replacement file can be uploaded).
- **No direct `edit`/`delete` routes** (`exclude_route_methods = {"edit", "delete"}`);
  all writes go through services. Released-version immutability is therefore
  enforced by the service (`ReleasedVersionImmutableError`) rather than by a
  view hook.
- `add` is overridden to redirect to the entity's service-backed create form.

> **Create-from-UI (implemented in Phase 4):** business objects cannot use
> FAB's generated add form directly, because an :class:`Item` (`item_number`,
> `item_type`) must be created together with a subtype row — the subtype model
> has no `item_number` field and its PK is the `ItemVersion` id. Creation uses
> FAB's standard `SimpleFormView` + `DynamicForm` (rendering the bundled
> `edit.html`), registered without a menu entry and launched from the entity's
> list page, calling the same ``*Service.create_*`` methods. This keeps the UI
> template-free and the navigation consistent.

## 15.4 Baseline Views

| View | Model | Notes |
|---|---|---|
| `BaselineModelView` | Baseline | list/show; actions `freeze`, `compare`, `list_members` |
| `BaselineMemberModelView` | BaselineMember | Embedded as related view; no edit once frozen |

Restrictions:

- `freeze` action is a one-way transition (PLM Manager only).
- `can_edit`/`can_delete` return false when `status == "FROZEN"`.

## 15.5 Custom Views (Exceptions Only)

Per [§3.3.1](#331-standard-flask-appbuilder-first), these are the **only**
approved custom views. Each must be implemented as a FAB `BaseView` (or a
`ModelView` override) and must not re-implement CRUD.

| View | Purpose | Why no standard view suffices |
|---|---|---|
| `StructureTreeView` | Interactive recursive tree of a product version (downstream) | No bundled FAB widget renders an expandable multi-level structure tree |
| `BaselineCompareView` | Side-by-side computed diff of two baselines | `compare_baselines` returns computed classification, not a model list |

Everything else must use standard views:

| Requirement | Standard FAB mechanism |
|---|---|
| Audit trail | Read-only `AuditEventModelView` (`base_permissions = ["can_list", "can_show"]`) with `base_filters` / search columns |
| Where-used (upstream) | `StructureTreeView` in `direction=up` mode, launched from an `@action` on `ItemVersionModelView` |
| Structure children | `@action` `add_child` → `StructureChildAddView`; removal via a `remove` action on `ItemRelationshipModelView` |
| Dashboard / metrics | `IndexView` subclass (standard pattern) and/or `GroupByChartView` / `DirectByChartView` |
| Baseline members | `related_views = [BaselineMemberModelView]` on `BaselineModelView` |

## 15.6 Navigation

Navigation is simple, flat, and identical in shape across domains: each entity
is a `ModelView` under **PLM** (or **Administration** for reference data), and
all operations are actions or related views on that page. Reporting concepts do
not get their own parallel menu tree.

```text
PLM
 ├── Items                     (ItemModelView)
 ├── Parts                     (PartModelView)
 ├── Documents                 (DocumentModelView)
 ├── Requirements              (RequirementModelView)
 ├── Products                  (ProductModelView)
 ├── Relationships             (ItemRelationshipModelView)
 ├── Baselines                 (BaselineModelView)
 └── Audit Trail               (AuditEventModelView, read-only)

Administration
 ├── Item Types
 ├── Lifecycle States
 ├── Lifecycle Transitions
 ├── Relationship Types
 └── Lookups (UoM, Make/Buy, Verification, Priority, Family, Market)
```

**Navigation rules**

1. At most two menu levels (category → view).
2. The `StructureTreeView` and `BaselineCompareView` are **actions** launched
   from the relevant `ProductModelView` / `BaselineModelView` page, not
   top-level menu entries.
3. Every entity list uses the standard FAB list widget, search, and filters.
4. The dashboard is the FAB `IndexView`, not a separate menu section.

# 16. Security Model

## 16.1 Roles

| Role | Description |
|---|---|
| `Admin` | Full system access, security management |
| `PLM Manager` | Release, obsolete, baseline freeze, reference-data view |
| `Engineer` | Create/edit drafts, in-work, submit for review |
| `Reviewer` | Approve/reject, review transitions |
| `Viewer` | Read-only access to permitted data |

## 16.2 Permission Matrix

Legend: ✅ full, ➕ add/edit/custom, 👁 view only, ❌ denied.

| View / Capability | Admin | PLM Manager | Engineer | Reviewer | Viewer |
|---|---|---|---|---|---|
| `ItemTypeModelView` | ✅ | 👁 | 👁 | 👁 | 👁 |
| `LifecycleStateModelView` | ✅ | 👁 | 👁 | 👁 | 👁 |
| `LifecycleTransitionModelView` | ✅ | 👁 | 👁 | 👁 | 👁 |
| `RelationshipTypeModelView` | ✅ | 👁 | 👁 | 👁 | 👁 |
| Lookups | ✅ | 👁 | 👁 | 👁 | 👁 |
| `ItemModelView` | ✅ | 👁 | 👁 | 👁 | 👁 |
| `ItemVersionModelView` | ✅ | 👁 | 👁 | 👁 | 👁 |
| `ItemRelationshipModelView` | ✅ | ➕ | ➕ | 👁 | 👁 |
| `PartModelView` | ✅ | ➕ | ➕ | 👁 | 👁 |
| `DocumentModelView` | ✅ | ➕ | ➕ | 👁 | 👁 |
| `RequirementModelView` | ✅ | ➕ | ➕ | 👁 | 👁 |
| `ProductModelView` | ✅ | ➕ | ➕ | 👁 | 👁 |
| `BaselineModelView` | ✅ | ➕ | 👁 | 👁 | 👁 |
| `BaselineMemberModelView` | ✅ | ➕ (draft only) | 👁 | 👁 | 👁 |
| `AuditEventModelView` (read-only) | ✅ | 👁 | 👁 | 👁 | 👁 |
| `StructureTreeView` (action/page) | ✅ | 👁 | 👁 | 👁 | 👁 |
| `BaselineCompareView` (action/page) | ✅ | 👁 | 👁 | 👁 | 👁 |
| Lifecycle: submit for review | ✅ | ✅ | ✅ | ✅ | ❌ |
| Lifecycle: approve/reject | ✅ | ✅ | ❌ | ✅ | ❌ |
| Lifecycle: release/obsolete | ✅ | ✅ | ❌ | ❌ | ❌ |
| Baseline: freeze | ✅ | ✅ | ❌ | ❌ | ❌ |
| REST API (all) | ✅ | ➕ | ➕/👁 | 👁 | 👁 |
| Security admin | ✅ | ❌ | ❌ | ❌ | ❌ |

## 16.3 Enforcement Notes

- FAB permissions are generated per view/action
  (`can_list on PartModelView`, etc.). Grant them to roles via the matrix.
- Lifecycle and baseline actions are **service-level** guarded in addition to
  FAB permissions; the service checks the actor's roles. UI hiding is not
  sufficient.
- Row-level restriction: `Viewer` sees all data (this is an engineering
  repository); if needed later, add `base_filters` scoped by program.
- `Admin` bypasses service authorization checks by design.
- Read-only custom roles can be defined via `FAB_ROLES` regex patterns.

## 16.4 Authentication

- `AUTH_TYPE = AUTH_DB` for 1.0.
- `AUTH_USER_REGISTRATION = False` initially; enable with email activation when
  `MAIL_*` and `RECAPTCHA_*` are configured.
- Passwords hashed with FAB's scrypt default. Enable
  `FAB_PASSWORD_COMPLEXITY_ENABLED = True`.
- Rate-limit login attempts via Flask-Limiter.

# 17. REST API

Implemented with FAB `ModelRestApi` under `/api/v1/`. JWT-protected.

## 17.1 Endpoints

| Resource | Route | Notes |
|---|---|---|
| Items | `/api/v1/items` | read + create |
| Item Versions | `/api/v1/itemversions` | read + revise action |
| Parts | `/api/v1/parts` | CRUD in draft |
| Documents | `/api/v1/documents` | metadata CRUD; upload via multipart |
| Requirements | `/api/v1/requirements` | CRUD in draft |
| Products | `/api/v1/products` | CRUD in draft |
| Relationships | `/api/v1/relationships` | add/remove/list |
| Baselines | `/api/v1/baselines` | create/freeze/compare/list members |

## 17.2 Custom Actions

Custom `@expose` methods on the corresponding `ModelRestApi`:

```text
POST /api/v1/items/{id}/revise           -> ItemService.revise_item
POST /api/v1/itemversions/{id}/transition -> LifecycleService.change_lifecycle
GET  /api/v1/itemversions/{id}/upstream   -> RelationshipService.get_upstream
GET  /api/v1/itemversions/{id}/downstream -> RelationshipService.get_downstream
POST /api/v1/baselines/{id}/freeze        -> BaselineService.freeze_baseline
GET  /api/v1/baselines/{id}/members       -> BaselineService.list_members
GET  /api/v1/baselines/compare?a=&b=      -> BaselineService.compare_baselines
```

- Every custom endpoint calls the same service layer — no duplicated logic.
- Domain exceptions are mapped to HTTP codes centrally via
  `@safe` + an error-mapping helper.
- OpenAPI documentation is maintained per endpoint (YAML docstrings), served at
  `/api/v1/_openapi`; Swagger UI at `/swagger/v1`.
- API version is `v1`; breaking changes require a new version path.

# 18. Database, Migrations & SQLite Notes

## 18.1 Connection & Pragmas

Configured in `app/__init__.py` / `app/database.py`:

```python
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "plm.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
```

Per-connection `PRAGMA foreign_keys=ON` and `journal_mode=WAL` via the
`Engine` `connect` event (see [§5.3](#53-data-type-conventions-sqlite)).

> **`check_same_thread=False`** is only safe because SQLAlchemy uses a
> connection pool; do not share a raw connection across threads.

## 18.2 Migrations (Alembic)

- Alembic is initialized with `render_as_batch=True` because SQLite has limited
  `ALTER TABLE`.
- Migrations live under `migrations/` at the project root.
- `migrations/env.py` targets `flask_appbuilder.models.sqla.Base.metadata` (the
  shared security + PLM metadata). It imports the model modules directly and
  does **not** call `create_app`, so loading migration metadata has no schema
  side effects.
- The baseline migration creates all tables in dependency order, including the
  `ab_*` security tables, so a fresh database can be built entirely from
  migrations (`FAB_CREATE_DB=False` in production).
- Because of the circular FK, the initial migration creates `item` **without**
  `current_version_id` FK, creates `item_version`, then adds the FK in a batch
  operation (or relies on `use_alter=True`).
- Every schema change requires a migration. Auto-create via `FAB_CREATE_DB` is
  enabled only for development/test; tests build the schema with
  `Base.metadata.create_all`.
- CI runs `alembic upgrade head` on a fresh database, then executes tests.

## 18.3 Backup & Integrity

- `PRAGMA integrity_check` is exposed as a maintenance command.
- For backups, use SQLite's online backup API or file copy while no writer is
  active. Document this in the README.

## 18.4 Portability to PostgreSQL

To keep a future migration cheap:

- No SQLite-only SQL in application code.
- Use `Numeric`/`Boolean`/`DateTime` via SQLAlchemy types, not raw SQL.
- Case-insensitive uniqueness is handled in application code (SQLite `NOCASE`
  would not port directly).

# 19. Project Structure

```text
helix/
├── pyproject.toml
├── README.md
├── alembic.ini
├── config.py                     # configuration classes
├── run.py                        # dev launcher
├── migrations/                   # Alembic
│   ├── env.py
│   └── versions/
├── docs/
│   └── PLM_Application_Specification_and_Build_Plan.md
├── app/
│   ├── __init__.py               # create_app, db, appbuilder
│   ├── database.py               # engine pragmas, session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── reference.py          # ItemType, LifecycleState, transitions, lookups
│   │   ├── core.py               # Item, ItemVersion, ItemRelationship
│   │   ├── business.py           # Part, Document, Requirement, Product
│   │   ├── baseline.py           # Baseline, BaselineMember
│   │   └── audit.py              # AuditEvent
│   ├── services/
│   │   ├── __init__.py
│   │   ├── item_service.py
│   │   ├── product_service.py
│   │   ├── part_service.py
│   │   ├── document_service.py
│   │   ├── requirement_service.py
│   │   ├── relationship_service.py
│   │   ├── lifecycle_service.py
│   │   ├── baseline_service.py
│   │   ├── audit_service.py
│   │   ├── business_base.py     # shared business-object service helpers
│   │   ├── base.py              # Actor, BaseService
│   │   ├── storage.py           # document file storage
│   │   └── exceptions.py
│   ├── views/
│   │   ├── __init__.py
│   │   ├── reference_views.py
│   │   ├── core_views.py
│   │   ├── business_views.py
│   │   ├── baseline_views.py     # Baseline list + create/freeze
│   │   ├── audit_views.py        # read-only AuditEventModelView
│   │   ├── business_forms.py     # service-backed create/revise SimpleFormViews
│   │   ├── structure_views.py    # §15.5 StructureTreeView exception
│   │   └── action_utils.py       # @action single/list normalization
│   │   #  §15.5 exception (Phase 8): baseline_compare_view.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── items.py
│   │       ├── parts.py
│   │       ├── documents.py
│   │       ├── requirements.py
│   │       ├── products.py
│   │       ├── relationships.py
│   │       └── baselines.py
│   ├── security/
│   │   ├── __init__.py           # SecurityManager, role seeding
│   │   └── manager.py
│   ├── cli.py                    # custom flask commands (seed, integrity)
│   ├── seed.py                   # seed reference data
│   └── templates/
│       └── plm/                  # only for the §15.5 exception templates
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── api/
└── .github/workflows/ci.yml
```

# 20. Testing Strategy

## 20.1 Levels

| Level | Scope | Tooling |
|---|---|---|
| Unit | Services with in-memory SQLite | pytest |
| Integration | Multi-service flows, FK/circular inserts | pytest + file SQLite |
| API | `ModelRestApi` endpoints incl. JWT auth | pytest + Flask test client |
| View | ModelView hooks, permission enforcement | pytest + FAB test client |
| Migration | `alembic upgrade head` on empty DB | CI job |

## 20.2 Required Test Cases (examples)

- Circular FK: create `Item` → `ItemVersion` → set `current_version_id`.
- Unique constraints: duplicate `(item_type_id, item_number)`,
  duplicate relationship edge, duplicate `(item_id, version_sequence)`.
- FK enforcement: deleting a referenced `ItemType` is rejected by SQLite
  (`PRAGMA foreign_keys=ON`).
- Versioning: `_format_revision` boundaries; major/minor bump rules.
- Lifecycle: every allowed transition succeeds; disallowed transition raises
  `InvalidLifecycleTransitionError`; role guard rejects `Engineer` release.
- Structure: `would_create_cycle` rejects A→B→A; quantity/find rules.
- Baseline: non-releasable member rejected; frozen baseline rejects mutation;
  `compare_baselines` diff correctness.
- Immutability: editing a released version raises
  `ReleasedVersionImmutableError`.
- Audit: every service mutation writes exactly one `AuditEvent`.
- Security: each role's matrix cells enforced.

## 20.3 Coverage & CI

- Target ≥ 85% line coverage on `app/services` and `app/models`.
- CI pipeline: install → lint (`ruff`) → `alembic upgrade head` → `pytest` →
  coverage gate.

# 21. Build Plan (Phased)

Each phase lists **Deliverables**, **Acceptance Criteria**, and **Dependencies**.
A phase is complete only when its acceptance tests pass in CI.

## Phase 0 — Project Scaffolding & Environment

**Deliverables**

- Pin Python 3.13; `pyproject.toml` with FAB, SQLAlchemy, Alembic, pytest, ruff.
- `config.py` (dev/test/prod), `run.py`, `create_app()` app factory.
- `app/database.py` with SQLite pragmas (FK on, WAL).
- Alembic configured with `render_as_batch=True`.
- CI workflow, README, `.gitignore`.
- Empty test harness (`tests/conftest.py`, in-memory + file SQLite fixtures).

**Acceptance**

- `flask run` starts; `/` loads the FAB index.
- `alembic upgrade head` runs on a fresh DB.
- `pytest` executes with the smoke tests passing.
- `PRAGMA foreign_keys` returns `1` in a test.
- `flask fab create-admin` creates an admin and `flask fab list-users` shows it.
- Verified pins: Python 3.13, FAB 5.2.3, SQLAlchemy 2.0.54.

**Dependencies:** none.

## Phase 1 — Core Infrastructure + Audit

**Deliverables**

- Reference models: `ItemType`, `LifecycleState`, `RelationshipType`,
  `LifecycleTransition`, lookups.
- Core models: `Item`, `ItemVersion`, `ItemRelationship`.
- `AuditEvent` model and `AuditMixin` on all tables.
- Initial Alembic migration (handles circular FK).
- Seed command for reference data.
- `ItemService`, `RelationshipService`, `AuditEventService` (create/revise/
  relationship basics).

**Acceptance**

- Create items, versions, and relationships through services.
- Circular FK insert works; duplicate constraints rejected.
- Deleting a referenced `ItemType` is rejected.
- Every mutation writes an `AuditEvent`.
- `alembic upgrade head` + `downgrade` cycle succeeds.

**Dependencies:** Phase 0.

## Phase 2 — Business Objects

**Deliverables**

- Models: `Part`, `Document`, `Requirement`, `Product` (joined inheritance).
- Services: `PartService`, `DocumentService`, `RequirementService`,
  `ProductService`.
- File upload handling for `Document` (FAB `FileManager`).

**Acceptance**

- Users create business objects **through services** via the API/views.
- Subtype + `ItemVersion` rows are created atomically.
- File upload stores under `UPLOAD_FOLDER` with relative `file_path`.

**Dependencies:** Phase 1.

> **Reconciliation:** v1 stated users create objects "directly". This is
> superseded: all creation flows through services; views and APIs are adapters.

## Phase 3 — Flask-AppBuilder UI

**Deliverables**

- Reference, core, and business `ModelView`s (standard FAB only); baseline
  views are added in Phase 7.
- Navigation, search, filters, `list_columns`, fieldsets.
- Service-backed `@action` revise buttons on business views; `audit` and
  `transition` actions on revisions.
- Business-object create forms (standard `SimpleFormView`) are added in
  Phase 4 with the revision UI.
- `IndexView` dashboard (standard FAB pattern) — chart views deferred to the
  reporting work in Phase 10.

**Acceptance**

- List/show works for all business objects.
- Search and filters operate on columns and joined/relationship fields.
- Menu structure matches [§15.6](#156-navigation) (two levels, consistent taxonomy).
- No custom Jinja templates introduced beyond the §15.5 exceptions.

**Dependencies:** Phase 2.

## Phase 4 — Revision Control  ✅ implemented

**Deliverables**

- *(done in Phases 1–3)* `revise_item`/`revise_*` with relationship copy and
  `superseded_by_id`; `revision_label` derivation; `ItemVersionModelView`
  revision history; `ReleasedVersionImmutableError` guard; service-backed
  revise actions on business views.
- **Create-from-UI forms** for Part/Document/Requirement/Product using FAB's
  standard `SimpleFormView` + `DynamicForm` (no menu entry), launched from each
  entity's list page via an overridden `add`; they call ``*Service.create_*``.
- **Document upload** on create, and a resolve-form that uploads a replacement
  file and records a reason.
- Direct `edit`/`delete` routes disabled on business and core views.

**Acceptance**

- Major/minor revision produces correct label and sequence.
- Relationships copied per flag.
- Editing a released version is rejected (service and UI).
- A business object can be created end-to-end from the UI and appears with the
  correct item number, revision label, and subtype attributes.

**Dependencies:** Phase 3.

## Phase 5 — Product Structures  ✅ implemented

**Deliverables**

- *(done in Phase 1)* `Contains` relationship enforcement (quantity, find
  number) and cycle detection/rejection in `RelationshipService`.
- `RelationshipService.build_tree()` — nested downstream/upstream tree with
  `max_depth` and cycle-safe expansion.
- `StructureTreeView` — the sanctioned custom view (spec §15.5) rendering the
  recursive tree, with `direction=down` (BOM) and `direction=up` (where-used).
- `StructureChildAddView` — standard `SimpleFormView` calling
  `RelationshipService.add_relationship`; `remove` action on
  `ItemRelationshipModelView` calling `remove_relationship`.
- Actions on `ProductModelView` and `ItemVersionModelView` to launch the
  structure browser and add-child form.

**Acceptance**

- A→B→A cycle is rejected.
- Structure tree renders a multi-level tree with quantities and find numbers.
- Where-used returns all parents (upstream tree).

**Dependencies:** Phase 4.

## Phase 6 — Lifecycle Management  ✅ implemented

**Deliverables**

- `LifecycleService` (spec §14.8) as the single owner of lifecycle logic,
  driven entirely by the configurable `LifecycleTransition` table:
  `change_lifecycle`, `submit_for_review`, `approve`, `release`, `obsolete`,
  `available_transitions`, `can_transition`. `ItemService.change_lifecycle`
  and friends are now thin delegating shims.
- Role guards read `LifecycleTransition.required_role_id` and raise
  `AuthorizationError`; `Admin` bypasses.
- UI: `submit_for_review` / `approve` / `release` / `obsolete` action buttons on
  `ItemVersionModelView` (via a `LifecycleActionsMixin`).
- REST endpoints for transitions are delivered in Phase 11; the service API is
  complete here.

**Acceptance**

- Allowed transitions succeed; disallowed raise
  `InvalidLifecycleTransitionError`.
- `Engineer` cannot approve/release; `Reviewer` can approve; `PLM Manager` can
  release/obsolete.
- Each transition writes a `STATE_CHANGE` audit event with from/to values and
  the optional comment.

**Dependencies:** Phase 5.

## Phase 7 — Baseline Management  ✅ implemented

**Deliverables**

- `Baseline`, `BaselineMember` models and `BaselineService`.
- Recursive structure capture with member linkage.
- Freeze (one-way) and member listing.
- *Implemented:* Alembic migration `5597f1a0f266_phase_7_baseline.py`; standard
  `BaselineModelView` / `BaselineMemberModelView` plus a service-backed
  `BaselineCreateView` (`SimpleFormView`); `freeze` action; `add_member` for
  draft baselines. `create_baseline` rolls back fully if any captured
  descendant is not releasable. `compare_baselines` is implemented in the
  service ahead of the Phase 8 UI.

**Acceptance**

- Only releasable versions captured; invalid member raises
  `BaselineValidationError`.
- Frozen baseline rejects all mutations.
- `list_members` returns the full structure.

**Dependencies:** Phase 6.

## Phase 8 — Configuration Analysis

**Deliverables**

- `compare_baselines` diff (added/removed/changed/unchanged).
- Impact analysis (downstream/upstream from a version) via service queries.
- Where-used exposed through a standard `@action` / filtered list.
- `BaselineCompareView` as the sole approved custom view.

**Acceptance**

- Diff correctly classifies a known pair of baselines.
- Where-used returns expected parents for a moved part.

**Dependencies:** Phase 7.

## Phase 9 — Security Hardening

**Deliverables**

- Custom `SecurityManager` and role seeding per [§16](#16-security-model).
- Permission matrix applied to all views/APIs.
- Service-level role checks.
- Login rate limiting; password policy.

**Acceptance**

- Automated tests assert each matrix cell.
- Direct service calls as an unauthorized role fail.
- `flask fab create-admin` and role seeding documented and working.

**Dependencies:** Phase 8.

> **Note:** A baseline security layer runs from Phase 1 (so devs can log in).
> Phase 9 is *hardening and full matrix enforcement*.

## Phase 10 — Auditability UI

**Deliverables**

- Read-only `AuditEventModelView` with search/filters (entity, item, actor,
  date, event type) using the standard FAB list widget.
- `can_audit` action on item/version views.
- Append-only enforcement (no edit/delete permissions).

**Acceptance**

- Audit trail shows lifecycle, revision, relationship, and baseline events.
- Non-Admin cannot modify or delete audit rows.

**Dependencies:** Phase 9.

## Phase 11 — REST API

**Deliverables**

- `ModelRestApi` for items, versions, parts, documents, requirements, products,
  relationships, baselines.
- Custom action endpoints ([§17.2](#172-custom-actions)).
- JWT login, OpenAPI docs, Swagger UI.
- Central domain-exception → HTTP mapping.

**Acceptance**

- Authenticated CRUD works for all resources.
- Custom actions call the service layer.
- OpenAPI spec validates; Swagger UI loads.
- 403/404/409/422 returned correctly for domain errors.

**Dependencies:** Phase 10.

## Phase 12 — Future Enhancements (Backlog)

- Change Request / Change Order (ECR/ECO) — highest priority backlog item.
- Drawing / CAD model management.
- Supplier part and approved-manufacturer list.
- Manufacturing BOM variants.
- Test cases and verification results.
- Effectivity by date/serial range.
- Classification / taxonomy.
- Configurable workflow engine beyond linear lifecycle.
- Optional migration path to PostgreSQL.

# 22. Seed Data

`app/seed.py`, invoked by `flask seed` (idempotent upsert by `code`):

```text
ItemType:            Part, Document, Requirement, Product
LifecycleState:      Draft, In Work, Review, Approved, Released, Obsolete
RelationshipType:    Contains, References, Satisfies, Derived From, Related To
LifecycleTransition: (see §11.2)
UnitOfMeasure:       EA, MM, M, KG, G, L, ML, SET
MakeBuyCode:         MAKE, BUY, MAKE_OR_BUY
VerificationMethod:  Test, Analysis, Inspection, Demonstration
PriorityCode:        Mandatory, High, Medium, Low
Roles:               Admin, PLM Manager, Engineer, Reviewer, Viewer (+ perms)
```

Reference seeding is re-runnable and must not duplicate rows.

# 23. Risks & Open Decisions

| # | Risk / Decision | Impact | Status / Mitigation |
|---|---|---|---|
| 1 | SQLite single-writer concurrency | Medium | Mitigate with WAL + short transactions; keep DB layer portable |
| 2 | Python 3.14 vs FAB 5.2 support | High | Pin 3.13 now |
| 3 | Circular FK `Item.current_version_id` | High | `use_alter=True` + `post_update=True`; migration ordering |
| 4 | Baseline semantics (product-scoped vs arbitrary) | Medium | Chosen: product-scoped recursive structure |
| 5 | Change Request/Order deferred | High (2.0) | Reserve model room; revisit before 2.0 |
| 6 | `viewer` sees all data (no row-level) | Low | Accept for 1.0; add program scoping later |
| 7 | SQLite `Numeric` precision | Low | Document precision bounds; validate in service |
| 8 | Duplicate `version_sequence` race | Medium | Serialize within transaction; unique constraint as backstop |
| 9 | File storage vs DB consistency | Medium | Upload before txn; cleanup on rollback |
| 10 | Alembic batch mode limitations | Medium | Test upgrade/downgrade in CI on every migration |

# 24. Glossary

| Term | Definition |
|---|---|
| **Item** | Stable business identity of a managed object. |
| **ItemVersion** | A specific revision of an Item. |
| **Revision label** | Human-readable version (e.g. `A.1`). |
| **Lifecycle state** | Workflow position of a version (Draft…Obsolete). |
| **Releasable** | Lifecycle state allowed to enter a baseline. |
| **Structure** | Directed acyclic graph of `Contains` relationships. |
| **Upstream / where-used** | Ancestors of a version. |
| **Downstream / BOM** | Descendants of a version. |
| **Baseline** | Frozen, immutable snapshot of a product configuration. |
| **Freeze** | One-way transition of a baseline to immutable status. |
| **AuditEvent** | Application-level record of a domain mutation. |
