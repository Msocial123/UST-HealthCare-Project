# Facility & Department Service

Phase 4 of the Smart Hospital & Patient Management System (development demo). This service owns **facilities,
departments, facility timezone metadata and rooms**. It contains no clinical logic, and all data is synthetic.

## Responsibilities and data ownership

| Owns | Does not own |
|------|--------------|
| `facilities`, `departments`, `rooms` tables | Users, passwords or token issuance (Identity service) |
| Its own Alembic migration history (`migrations/`) | Providers, patients, schedules or appointments |
| Facility-service authorization (role → permission map) | Any other service's database. The facility database must not be shared |

The service makes **no runtime calls** to other services. Access tokens issued by the Identity service are verified
locally (see [Authentication](#authentication)). Other services (e.g. Provider, and later Scheduling) reference
facilities and departments by UUID and read their data through this API only.

## Layout

```
app/
  api/            # routers (v1/facilities.py, v1/departments.py, health.py), deps (auth, clock), errors, middleware
  core/           # config (env validation), JWT verifier, logging, errors, time helpers
  domain/         # roles.py (Role / Permission map), facilities.py (enums, IANA timezone helpers)
  models/         # SQLAlchemy models (Facility, Department, Room)
  repositories/   # data access
  schemas/        # Pydantic request/response models
  services/       # use cases (business rules)
  main.py         # application factory (create_app)
migrations/       # Alembic environment + versions
tests/            # pytest suite (SQLite in-memory by default, optional PostgreSQL)
```

## Local setup

Requirements: Python 3.12+ and PostgreSQL 14+.

```bash
cd services/facility-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DATABASE_URL and copy the JWT_* values used by the Identity service.
```

Create a dedicated database and role for this service (example):

```sql
CREATE USER facility_user WITH PASSWORD '<choose-a-local-password>';
CREATE DATABASE facility OWNER facility_user;
```

## Configuration

All settings come from environment variables (or `.env`). The service **fails fast at startup** when configuration
is invalid, and error messages name the setting without printing its value.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | – | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/facility` |
| `JWT_SECRET_KEY` | yes | – | Same secret the Identity service signs with. At least 32 bytes for HS256, 48 for HS384, 64 for HS512. Placeholders are rejected |
| `JWT_ALGORITHM` | no | `HS256` | `HS256`, `HS384` or `HS512`; must match Identity. `none` and every other algorithm is rejected |
| `JWT_KEY_ID` | no | `k1` | `kid` of the active Identity key |
| `JWT_ISSUER` | yes | – | Expected `iss`, e.g. `https://identity.smart-hospital.local` |
| `JWT_AUDIENCE` | yes | – | Expected `aud`, e.g. `smart-hospital-api` |
| `JWT_LEEWAY_SECONDS` | no | `30` | Allowed clock skew, 0–120 |
| `JWT_PREVIOUS_KEYS` | no | `{}` | JSON `{"kid": "secret"}` of retired Identity keys still accepted during rotation |
| `APP_ENV` | no | `development` | `development`, `test` or `production` |
| `LOG_LEVEL` | no | `INFO` | |

## Migrations

```bash
alembic upgrade head        # apply (creates facilities, departments, rooms)
alembic current             # show revision
alembic downgrade base      # roll back everything
alembic check               # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # new migration
```

## Run

```bash
uvicorn app.main:create_app --factory --reload --port 8004 --no-access-log
```

- OpenAPI UI: http://localhost:8004/docs (click **Authorize** and paste an access token from the Identity service
  `POST /api/v1/auth/login`)
- OpenAPI JSON: http://localhost:8004/openapi.json

The service writes its own structured request logs (method, path without query string, status, duration, request ID).
Tokens, request bodies, query strings and contact details are never logged.

## Test

```bash
pytest                       # isolated: in-memory SQLite, tokens minted with a test-only secret, no external services
ruff check . && ruff format --check .

# Optional: run the same suite against a disposable PostgreSQL database
TEST_DATABASE_URL=postgresql+psycopg://facility_user:<pw>@localhost:5432/facility_test pytest
```

> The suite drops and recreates tables in the `TEST_DATABASE_URL` database. Never point it at a database you need.

## API (`/api/v1`)

| Method | Path | Access (permission) | Description |
|--------|------|---------------------|-------------|
| GET | `/health`, `/health/ready` | public | Liveness, and readiness including a database check (no `/api/v1` prefix) |
| POST | `/facilities` | ADMIN (`facilities:manage`) | Create a facility |
| GET | `/facilities?search&type&active&limit&offset` | any authenticated role (`facilities:read`) | Paginated list/search, ordered by `name`, `code` |
| GET | `/facilities/{id}` | any authenticated role (`facilities:read`) | One facility plus `current_local_time` and `utc_offset` computed from its timezone |
| PATCH | `/facilities/{id}` | ADMIN (`facilities:manage`) | Partial update, including `timezone`. `code` and `is_active` cannot be patched |
| POST | `/facilities/{id}/deactivate` | ADMIN (`facilities:manage`) | Set `is_active=false` (idempotent). Facilities are never hard-deleted |
| POST | `/facilities/{id}/activate` | ADMIN (`facilities:manage`) | Set `is_active=true` (idempotent) |
| POST | `/facilities/{id}/departments` | ADMIN (`facilities:manage`) | Create a department in an **active** facility |
| GET | `/facilities/{id}/departments?active&limit&offset` | any authenticated role (`facilities:read`) | Departments of a facility, ordered by `code` |
| GET | `/departments/{id}` | any authenticated role (`facilities:read`) | One department |
| PATCH | `/departments/{id}` | ADMIN (`facilities:manage`) | Update `name`, `floor`, `phone_extension`; set `is_active` to deactivate/re-activate |
| POST | `/departments/{id}/rooms` | ADMIN (`facilities:manage`) | Create a room in an active department of an active facility |
| GET | `/departments/{id}/rooms?active&limit&offset` | any authenticated role (`facilities:read`) | Rooms of a department, ordered by `room_number` |

`limit` is 1–100 (default 20) and `offset` ≥ 0 on every list endpoint. List responses are
`{items, total, limit, offset}`. There are no DELETE endpoints.

Search: `search` (1–100 chars, not blank; whitespace-only returns 422) matches a case-insensitive substring of the facility name, code or city. `type` is
one of `HOSPITAL`, `CLINIC`, `DIAGNOSTIC_CENTER`. `active` filters by status.

Example create request (synthetic data):

```json
{
  "code": "NHG-MAIN",
  "name": "Northwind General Hospital",
  "facility_type": "HOSPITAL",
  "address_line1": "100 Example Avenue",
  "address_line2": "Block B",
  "city": "Sampleton",
  "state_province": "Demo State",
  "postal_code": "560001",
  "country_code": "IN",
  "main_phone": "+91 80 5550 0100",
  "timezone": "Asia/Kolkata"
}
```

`GET /facilities/{id}` adds, for example:

```json
{"timezone": "Asia/Kolkata", "current_local_time": "2026-01-15T12:00:00+05:30", "utc_offset": "+05:30"}
```

### Data model

| Table | Columns | Constraints |
|-------|---------|-------------|
| `facilities` | `id` UUID, `code`, `name`, `facility_type`, `address_line1`, `address_line2?`, `city`, `state_province?`, `postal_code`, `country_code`, `main_phone`, `timezone`, `is_active`, `created_at`, `updated_at` | `code` unique and uppercase; `facility_type` and uppercase `country_code` CHECKs; index on `name` |
| `departments` | `id` UUID, `facility_id` → `facilities.id`, `code`, `name`, `floor?`, `phone_extension?`, `is_active`, `created_at`, `updated_at` | unique (`facility_id`, `code`); `code` uppercase; FK `ON DELETE RESTRICT` |
| `rooms` | `id` UUID, `department_id` → `departments.id`, `room_number`, `room_type`, `is_active`, `created_at`, `updated_at` | unique (`department_id`, `room_number`); `room_type` CHECK; FK `ON DELETE RESTRICT` |

All timestamps are `timestamptz` and stored/returned in UTC.

### Business rules

- Facility and department `code` is 2–32 characters `[A-Za-z0-9_-]`, stored uppercase and **immutable**. Facility
  codes are globally unique; department codes are unique within a facility (409).
- `timezone` must be an exact IANA name known to `zoneinfo` (e.g. `Asia/Kolkata`, `America/New_York`). Unknown or
  wrongly-cased names return 422. `tzdata` is a dependency, so validation does not depend on host timezone files.
- `country_code` is ISO 3166-1 alpha-2, stored uppercase. `main_phone` allows digits, spaces, `()`, `-` and a
  leading `+`. `phone_extension` is 1–10 digits; `floor` is 1–16 characters `[A-Za-z0-9 -]`.
- Creating a department under an **inactive facility returns 409**; so does re-activating a department whose facility
  is inactive.
- Creating a room in an inactive department, or in a department of an inactive facility, returns 409.
- `room_number` is 1–16 characters `[A-Za-z0-9-]`, stored uppercase and unique within a department (409).
  `room_type` is one of `CONSULTATION`, `WARD`, `PROCEDURE`, `OTHER`.
- Deactivating a facility does **not** cascade to its departments or rooms; consumers should check both statuses.
- Timestamps are timezone-aware UTC. The facility timezone is exposed so other services can convert local working
  hours; `current_local_time` is computed on read and never stored.

### Error format

Same envelope as the Identity service:

```json
{"error": {"code": "forbidden", "message": "Insufficient permissions"}}
```

| Status | `code` | When |
|--------|--------|------|
| 401 | `not_authenticated` | Missing, malformed, invalid or expired token. Includes a `WWW-Authenticate: Bearer` header |
| 403 | `forbidden` | Valid token, but no role grants the required permission |
| 404 | `not_found` | Unknown facility or department |
| 409 | `conflict` | Duplicate facility code, department code (per facility) or room number (per department); writes under an inactive parent |
| 422 | `validation_error` | Invalid request (e.g. unknown IANA timezone, bad pagination). Submitted values are never echoed back |

## Authentication

Every `/api/v1` endpoint requires `Authorization: Bearer <access token>` issued by the Identity service. Tokens are
verified **locally** (`app/core/tokens.py`), following the Identity token contract in
[`services/identity-service/README.md`](../identity-service/README.md#jwt-access-token-contract-for-other-services):

1. `alg` must exactly equal `JWT_ALGORITHM` (never `none`); `kid` selects the key from `JWT_KEY_ID` /
   `JWT_PREVIOUS_KEYS` (unknown `kid` → 401).
2. Signature, `exp`, `nbf`, `iat` (with `JWT_LEEWAY_SECONDS`), `iss` and `aud` are verified; `iss, aud, sub, iat, nbf,
   exp, jti` are required.
3. `token_use` must be `access`, `sub` a UUID, and `roles` a non-empty list of known roles.
4. Authorization uses only the verified `roles` claim and this service's own map. Roles or user IDs in headers,
   bodies or query strings are ignored.

| Role | Facility-service permissions |
|------|------------------------------|
| ADMIN | `facilities:read`, `facilities:manage` |
| RECEPTIONIST | `facilities:read` |
| DOCTOR | `facilities:read` |
| READ_ONLY | `facilities:read` |

**Revocation semantics.** Verification is stateless: if an Identity account is disabled or its role changes, its
existing token is accepted here until it expires (15 minutes by default in Identity, 60 at most).

## Limitations

- Development demo only; not a certified clinical system and no regulatory compliance is claimed.
- No room update/deactivation endpoint (not in Phase 4 scope); rooms are created active.
- Facility deactivation does not cascade to departments/rooms.
- No immediate token revocation (see above).
- Searching uses `LIKE`; large datasets would need trigram/full-text indexes.
