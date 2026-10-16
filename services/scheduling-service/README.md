# Scheduling & Availability Service

Phase 5 of the Smart Hospital & Patient Management System (development demo). This service owns **provider weekly
working hours, availability exceptions and advisory slot queries**. It contains no clinical logic, and all data is
synthetic.

> Slots are **advisory only**. This service never reserves, holds or locks a slot. The (future) Appointment service
> owns final booking correctness and must enforce it with its own transactions/constraints.

## Responsibilities and data ownership

| Owns | Does not own |
|------|--------------|
| `working_hours`, `availability_exceptions` tables | Users, passwords or token issuance (Identity service) |
| Its own Alembic migration history (`migrations/`) | Provider profiles (Provider service) or facilities/timezones (Facility service) |
| Scheduling-service authorization (role → permission map) | Appointments, bookings or reservations (Appointment service) |

`provider_id` and `facility_id` are opaque UUID references: there are no cross-service foreign keys and this
service never reads another service's database. The only runtime dependency is the Facility service HTTP contract
below. There are no runtime calls to the Identity, Provider or Appointment services.

### Facility client contract

`app/clients/facility_client.py` defines a `FacilityClient` protocol with one method, implemented by
`HttpFacilityClient`:

- `GET {FACILITY_SERVICE_URL}/api/v1/facilities/{facility_id}`, forwarding the caller's bearer token (every role
  has `facilities:read` in the Facility service). Only `id`, `timezone` (IANA) and `is_active` are used.
- `404` → this service returns `404 not_found` ("Facility not found").
- Timeout, connection error, any other status, redirects or a malformed/invalid response → `503
  service_unavailable` ("Facility service is unavailable; try again later"). The token is never logged.
- An inactive facility → `409 conflict` when creating working hours or `EXTRA_HOURS`, and for slot queries.
- The client is injected through `create_app(settings, facility_client=...)`; tests use an in-memory fake.

The facility is looked up when creating working hours, when creating a facility-specific exception and for every
slot query (no caching, so timezone changes in the Facility service take effect immediately).

## Layout

```
app/
  api/            # routers (v1/working_hours.py, v1/exceptions.py, v1/slots.py, health.py), deps, errors, middleware
  clients/        # FacilityClient protocol + HTTP implementation
  core/           # config (env validation), JWT verifier, logging, errors, time helpers
  domain/         # roles.py (Role / Permission map), scheduling.py (rules), slots.py (DST-aware slot engine)
  models/         # SQLAlchemy models (WorkingHours, AvailabilityException)
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
cd services/scheduling-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DATABASE_URL, copy the JWT_* values used by the Identity service and set FACILITY_SERVICE_URL.
```

Create a dedicated database and role for this service (example):

```sql
CREATE USER scheduling_user WITH PASSWORD '<choose-a-local-password>';
CREATE DATABASE scheduling OWNER scheduling_user;
```

## Configuration

All settings come from environment variables (or `.env`). The service **fails fast at startup** when configuration
is invalid, and error messages name the setting without printing its value.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | – | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/scheduling` |
| `JWT_SECRET_KEY` | yes | – | Same secret the Identity service signs with. At least 32 bytes for HS256, 48 for HS384, 64 for HS512. Placeholders are rejected |
| `JWT_ALGORITHM` | no | `HS256` | `HS256`, `HS384` or `HS512`; must match Identity. `none` and every other algorithm is rejected |
| `JWT_KEY_ID` | no | `k1` | `kid` of the active Identity key |
| `JWT_ISSUER` | yes | – | Expected `iss`, e.g. `https://identity.smart-hospital.local` |
| `JWT_AUDIENCE` | yes | – | Expected `aud`, e.g. `smart-hospital-api` |
| `JWT_LEEWAY_SECONDS` | no | `30` | Allowed clock skew, 0–120 |
| `JWT_PREVIOUS_KEYS` | no | `{}` | JSON `{"kid": "secret"}` of retired Identity keys still accepted during rotation |
| `FACILITY_SERVICE_URL` | yes | – | Facility service base URL (`http://` or `https://`), e.g. `http://localhost:8004` |
| `FACILITY_TIMEOUT_SECONDS` | no | `3` | Timeout per Facility request (0 < value ≤ 30) |
| `EXTRA_HOURS_SLOT_MINUTES` | no | `15` | Slot length for `EXTRA_HOURS` exceptions (5–120) |
| `APP_ENV` | no | `development` | `development`, `test` or `production` |
| `LOG_LEVEL` | no | `INFO` | |

## Migrations

```bash
alembic upgrade head        # apply (creates working_hours, availability_exceptions)
alembic current             # show revision
alembic downgrade base      # roll back everything
alembic check               # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # new migration
```

## Run

```bash
uvicorn app.main:create_app --factory --reload --port 8005 --no-access-log
```

- OpenAPI UI: http://localhost:8005/docs (click **Authorize** and paste an access token from the Identity service)
- OpenAPI JSON: http://localhost:8005/openapi.json
- `GET /health` (liveness, no auth) and `GET /health/ready` (checks the database, no auth)

The service writes its own structured request logs (method, path without query string, status, duration, request ID).
Tokens, request bodies and query strings are never logged.

## Test

```bash
pytest                       # isolated: in-memory SQLite, fake FacilityClient, tokens minted with a test-only secret
ruff check . && ruff format --check .

# Optional: run the same suite against a disposable PostgreSQL database
TEST_DATABASE_URL=postgresql+psycopg://scheduling_user:<pw>@localhost:5432/scheduling_test pytest
```

> The suite drops and recreates tables in the `TEST_DATABASE_URL` database. Never point it at a database you need.

## API (`/api/v1`)

| Method | Path | Allowed roles (permission) | Description |
|--------|------|----------------------------|-------------|
| GET | `/health`, `/health/ready` | public | Liveness / readiness |
| POST | `/providers/{provider_id}/working-hours` | ADMIN (`working_hours:manage`) | Add a weekly rule (201) |
| GET | `/providers/{provider_id}/working-hours` | any role (`schedule:read`) | List rules; filters `facility_id`, `weekday`, `active`; `limit`/`offset` |
| PATCH | `/working-hours/{id}` | ADMIN (`working_hours:manage`) | Partial update; `is_active: true` re-activates |
| DELETE | `/working-hours/{id}` | ADMIN (`working_hours:manage`) | Deactivate (soft delete, 204, idempotent) |
| POST | `/providers/{provider_id}/exceptions` | ADMIN, RECEPTIONIST (`exceptions:manage`) | Add LEAVE / HOLIDAY / BLOCKED / EXTRA_HOURS (201) |
| GET | `/providers/{provider_id}/exceptions?from&to` | any role (`schedule:read`) | Exceptions overlapping `[from, to)`; optional `facility_id`, `active` (default `true`); `limit`/`offset` |
| PATCH | `/exceptions/{id}` | ADMIN, RECEPTIONIST (`exceptions:manage`) | Partial update; `is_active: true` re-activates |
| DELETE | `/exceptions/{id}` | ADMIN, RECEPTIONIST (`exceptions:manage`) | Deactivate (soft delete, 204, idempotent) |
| GET | `/providers/{provider_id}/slots?facility_id&date_from&date_to` | ADMIN, RECEPTIONIST, DOCTOR (`slots:read`) | Advisory free slots, max 14-day range |

Example slot response (`Asia/Kolkata`, Monday 09:00–10:00, 30-minute slots):

```json
{
  "provider_id": "…", "facility_id": "…", "timezone": "Asia/Kolkata",
  "date_from": "2026-04-06", "date_to": "2026-04-06", "advisory": true,
  "slots": [
    {"start_utc": "2026-04-06T03:30:00Z", "end_utc": "2026-04-06T04:00:00Z",
     "start_local": "2026-04-06T09:00:00+05:30", "end_local": "2026-04-06T09:30:00+05:30", "source": "WORKING_HOURS"}
  ]
}
```

### Data model

| Table | Columns |
|-------|---------|
| `working_hours` | `id` UUID, `provider_id` UUID ref, `facility_id` UUID ref, `weekday` 0–6, `start_local_time`, `end_local_time`, `slot_minutes` 5–120, `valid_from`, `valid_to` (nullable), `is_active`, `created_at`, `updated_at` |
| `availability_exceptions` | `id` UUID, `provider_id` UUID ref, `facility_id` UUID ref (nullable = all facilities), `starts_at`, `ends_at` (timestamptz, UTC), `type` (`LEAVE`, `HOLIDAY`, `BLOCKED`, `EXTRA_HOURS`), `reason_code`, `is_active`, `created_at`, `updated_at` |

Database CHECK constraints mirror the API rules (weekday range, slot range, end after start, validity range, allowed
types, `EXTRA_HOURS` requires a facility, upper-case reason code).

### Business rules

- **Weekday** uses ISO/Python numbering: `0` = Monday … `6` = Sunday.
- **Working hours** are facility-local wall-clock times (`HH:MM`, no offset, no seconds), within a single day:
  `end_local_time > start_local_time`, the window must fit at least one slot, `slot_minutes` 5–120,
  `valid_to ≥ valid_from` (inclusive local dates; `valid_to` null = open-ended).
- **Overlap (409)**: two *active* rules for the same provider, facility and weekday whose time ranges and validity
  date ranges overlap. Adjacent rules (09:00–12:00 and 12:00–15:00) are allowed. Checked on create, update and
  re-activation; on PostgreSQL a per-provider transaction advisory lock serialises concurrent writes.
- **Exceptions** are timezone-aware instants stored as UTC, `ends_at > starts_at`, at most 366 days. `reason_code`
  is a structured code (`^[A-Za-z0-9_]{2,32}$`, stored upper-case, e.g. `ANNUAL_LEAVE`) — there is no free-text
  field. `EXTRA_HOURS` requires a `facility_id`; other types without one apply at every facility.
- **Slots** (`date_from`/`date_to` are inclusive facility-local dates, at most 14 days, else 422):
  1. Each active rule valid on a local date produces consecutive `slot_minutes` slots in local wall-clock time,
     converted to UTC with the facility's IANA timezone (so 09:00 Europe/London is 09:00Z in winter and 08:00Z in
     summer).
  2. Active `EXTRA_HOURS` for that facility add slots of `EXTRA_HOURS_SLOT_MINUTES`, stepped from the exception
     start and limited to the queried local dates.
  3. Any slot overlapping an active `LEAVE`, `HOLIDAY` or `BLOCKED` exception (for that facility or for all
     facilities) is removed — including extra-hours slots.
  4. Identical intervals are de-duplicated; results are sorted by start time.
- **DST**: slots touching a local time that does not exist (spring-forward gap) are skipped; ambiguous local times
  (autumn fall-back) use their first occurrence, and slots whose real length would differ from `slot_minutes`
  because they straddle the change are skipped.

### Error format

Same envelope as the Identity service:

```json
{"error": {"code": "forbidden", "message": "Insufficient permissions"}}
```

| Status | `code` | When |
|--------|--------|------|
| 401 | `not_authenticated` | Missing, malformed, invalid or expired token. Includes a `WWW-Authenticate: Bearer` header |
| 403 | `forbidden` | Valid token, but no role grants the required permission |
| 404 | `not_found` | Unknown working-hours rule, exception, or facility (per the Facility service) |
| 409 | `conflict` | Overlapping working-hours rule (`details.conflicting_id`), inactive facility |
| 422 | `validation_error` | Invalid request (end before start, slot length, >14-day slot range, naive datetimes, …). Submitted values are never echoed back |
| 503 | `service_unavailable` | Facility service unreachable, timed out or returned an unusable response |

## Authentication

Every `/api/v1` endpoint requires `Authorization: Bearer <access token>` issued by the Identity service. Tokens are
verified **locally** (`app/core/tokens.py`), following the Identity token contract in
[`services/identity-service/README.md`](../identity-service/README.md#jwt-access-token-contract-for-other-services):

1. `alg` must exactly equal `JWT_ALGORITHM` (never `none`); `kid` selects the key from `JWT_KEY_ID` /
   `JWT_PREVIOUS_KEYS` (unknown `kid` → 401).
2. Signature, `exp`, `nbf`, `iat` (with `JWT_LEEWAY_SECONDS`), `iss` and `aud` are verified; `iss, aud, sub, iat, nbf,
   exp, jti` are required.
3. `token_use` must be `access`, `sub` a UUID, and `roles` a non-empty list of known roles.
4. Authorization uses only the verified `roles` claim and this service's own map. Roles in headers, bodies or query
   strings are ignored.

| Role | Scheduling-service permissions |
|------|--------------------------------|
| ADMIN | `schedule:read`, `working_hours:manage`, `exceptions:manage`, `slots:read` |
| RECEPTIONIST | `schedule:read`, `exceptions:manage`, `slots:read` |
| DOCTOR | `schedule:read`, `slots:read` |
| READ_ONLY | `schedule:read` |

**Revocation semantics.** Verification is stateless: a disabled account's existing token is accepted until it expires.

## Limitations

- Development demo only; not a certified clinical system and no regulatory compliance is claimed.
- Slots are advisory: no reservation, hold or locking, and existing appointments are not subtracted (Appointment
  service scope).
- `provider_id` is not validated against the Provider service (no Provider contract is in Phase 5 scope).
- Working hours cannot span midnight; split overnight hours into two rules.
- The overlap rule is per facility (as specified); the same provider may have overlapping hours at different
  facilities.
- `EXTRA_HOURS` slot length is a single service-wide setting.
- The Facility service is called on every slot query (no caching); the caller's token is forwarded, so callers need
  `facilities:read` there.
- Exception update/deactivate endpoints (`PATCH`/`DELETE /exceptions/{id}`) were added beyond the issue's endpoint
  table to support the required update/deactivate tests.
- No immediate token revocation (see above).
