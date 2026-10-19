# Appointment Service

Phase 6 of the Smart Hospital & Patient Management System (development demo). This service owns the **appointment
booking lifecycle**: booking, rescheduling, cancellation, check-in, completion and no-show, with
**concurrency-safe booking integrity**. It contains no clinical logic, and all data is synthetic.

## Responsibilities and data ownership

| Owns | Does not own |
|------|--------------|
| `appointments`, `outbox_events` tables | Users, passwords or token issuance (Identity service) |
| Its own Alembic migration history (`migrations/`) | Patients, providers or facilities (Patient / Provider / Facility services) |
| Final booking correctness (PostgreSQL exclusion constraint) | Working hours or slots (Scheduling service, advisory only) |
| Appointment-service authorization (role → permission map) | Delivering notifications (Notification service, reads the outbox later) |

`patient_id`, `provider_id` and `facility_id` are opaque UUID references: there are no cross-service foreign keys
and this service never reads another service's database. There are no runtime calls to Identity. The only optional
runtime dependency is the Scheduling advice contract below (off by default).

## Layout

```
app/
  api/            # routers (v1/appointments.py, health.py), deps (auth, feature flag), errors, middleware
  clients/        # SchedulingClient protocol + HTTP implementation (optional, advisory)
  core/           # config (env validation), JWT verifier, logging, errors, time helpers
  domain/         # roles.py (Role / Permission map), appointments.py (statuses, transitions, interval rules)
  models/         # SQLAlchemy models (Appointment, OutboxEvent)
  repositories/   # data access
  schemas/        # Pydantic request/response models
  services/       # use cases (business rules, one transaction per command)
  main.py         # application factory (create_app)
migrations/       # Alembic environment + versions
tests/            # pytest suite (SQLite in-memory by default, PostgreSQL via TEST_DATABASE_URL)
```

## Local setup

Requirements: Python 3.12+ and PostgreSQL 14+ (the migration enables the `btree_gist` extension).

```bash
cd services/appointment-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DATABASE_URL and copy the JWT_* values used by the Identity service.
# Set APPOINTMENTS_ENABLED=true to allow booking, rescheduling and cancelling.
```

Create a dedicated database and role for this service (example):

```sql
CREATE USER appointment_user WITH PASSWORD '<choose-a-local-password>';
CREATE DATABASE appointment OWNER appointment_user;
```

`btree_gist` is a trusted extension (PostgreSQL 13+), so the database owner can create it. On PostgreSQL 12 or
when the role lacks `CREATE` on the database, run `CREATE EXTENSION btree_gist;` once as a superuser.

## Configuration

All settings come from environment variables (or `.env`). The service **fails fast at startup** when configuration
is invalid, and error messages name the setting without printing its value.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | – | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/appointment` |
| `JWT_SECRET_KEY` | yes | – | Same secret the Identity service signs with. At least 32 bytes for HS256, 48 for HS384, 64 for HS512. Placeholders are rejected |
| `JWT_ALGORITHM` | no | `HS256` | `HS256`, `HS384` or `HS512`; must match Identity. `none` and every other algorithm is rejected |
| `JWT_KEY_ID` | no | `k1` | `kid` of the active Identity key |
| `JWT_ISSUER` | yes | – | Expected `iss`, e.g. `https://identity.smart-hospital.local` |
| `JWT_AUDIENCE` | yes | – | Expected `aud`, e.g. `smart-hospital-api` |
| `JWT_LEEWAY_SECONDS` | no | `30` | Allowed clock skew, 0–120 |
| `JWT_PREVIOUS_KEYS` | no | `{}` | JSON `{"kid": "secret"}` of retired Identity keys still accepted during rotation |
| `APPOINTMENTS_ENABLED` | no | `false` | Feature flag for book / reschedule / cancel (see below) |
| `SCHEDULING_ADVICE_ENABLED` | no | `false` | Ask the Scheduling service whether the time is inside advertised slots before booking/rescheduling |
| `SCHEDULING_SERVICE_URL` | when advice enabled | – | Scheduling base URL (`http://` or `https://`), e.g. `http://localhost:8005` |
| `SCHEDULING_TIMEOUT_SECONDS` | no | `3` | Timeout per Scheduling request (0 < value ≤ 30) |
| `APP_ENV` | no | `development` | `development`, `test` or `production` |
| `LOG_LEVEL` | no | `INFO` | |

### Feature flag `APPOINTMENTS_ENABLED`

Patient-facing behaviour — `POST /appointments`, `POST /appointments/{id}/reschedule` and
`POST /appointments/{id}/cancel` — is **off by default**. While it is `false` those endpoints return:

```http
HTTP/1.1 503 Service Unavailable

{"error": {"code": "feature_disabled", "message": "Appointment booking is currently disabled"}}
```

Authentication and authorization are still checked first (401/403 take precedence). Reads (`GET`) and the
check-in / complete / no-show transitions keep working so existing appointments can still be handled. The flag is
read at startup; change it and restart the service.

## Migrations

```bash
alembic upgrade head        # apply (creates appointments, outbox_events, btree_gist, exclusion constraint)
alembic current             # show revision
alembic downgrade -1        # step back one revision (see the data-loss warning below)
alembic check               # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # new migration
```

> **Data loss warning.** Revision `0001` creates the tables, so its downgrade **drops `appointments` and
> `outbox_events` with all their rows**. Never run it against a database holding real or needed data without a
> verified backup and explicit authorization. The `btree_gist` extension is left installed.

## Run

```bash
uvicorn app.main:create_app --factory --reload --port 8006 --no-access-log
```

- OpenAPI UI: http://localhost:8006/docs (click **Authorize** and paste an access token from the Identity service)
- OpenAPI JSON: http://localhost:8006/openapi.json
- `GET /health` (liveness, no auth) and `GET /health/ready` (checks the database, no auth)

The service writes its own structured request logs (method, matched endpoint name, status, duration, request ID).
Raw URL paths, query strings, tokens, request bodies and patient identifiers are never logged.

## Test

```bash
pytest                       # isolated: in-memory SQLite, tokens minted with a test-only secret, fake SchedulingClient
ruff check . && ruff format --check .

# Run the same suite against a disposable PostgreSQL database; this also runs the concurrency tests,
# which are skipped on SQLite.
TEST_DATABASE_URL=postgresql+psycopg://appointment_user:<pw>@localhost:5432/appointment_test pytest
```

> The suite drops and recreates tables in the `TEST_DATABASE_URL` database. Never point it at a database you need.

## API (`/api/v1`)

| Method | Path | Allowed roles (permission) | Flag | Description |
|--------|------|----------------------------|------|-------------|
| GET | `/health`, `/health/ready` | public | – | Liveness / readiness |
| POST | `/appointments` | RECEPTIONIST, ADMIN (`appointments:book`) | yes | Book (201, status `BOOKED`); 409 if the provider is busy |
| GET | `/appointments/{id}` | RECEPTIONIST, DOCTOR, ADMIN (`appointments:read`) | – | Get one |
| GET | `/appointments?patient_id&provider_id&facility_id&date_from&date_to&status&limit&offset` | RECEPTIONIST, DOCTOR, ADMIN (`appointments:read`) | – | Paginated search, ordered by `starts_at` |
| POST | `/appointments/{id}/reschedule` | RECEPTIONIST, ADMIN (`appointments:book`) | yes | New `starts_at`/`ends_at` + required `version`; same integrity rules |
| POST | `/appointments/{id}/cancel` | RECEPTIONIST, ADMIN (`appointments:book`) | yes | `cancellation_reason` code (+ optional `version`); frees the time |
| POST | `/appointments/{id}/check-in` | RECEPTIONIST, DOCTOR, ADMIN (`appointments:transition`) | – | `BOOKED` → `CHECKED_IN` (optional body `{"version": n}`) |
| POST | `/appointments/{id}/complete` | RECEPTIONIST, DOCTOR, ADMIN (`appointments:transition`) | – | `CHECKED_IN` → `COMPLETED` |
| POST | `/appointments/{id}/no-show` | RECEPTIONIST, DOCTOR, ADMIN (`appointments:transition`) | – | `BOOKED` → `NO_SHOW`; frees the time |

Example booking (synthetic IDs):

```json
POST /api/v1/appointments
{
  "patient_id": "8f6d1c0e-1111-4c1a-9b7e-000000000001",
  "provider_id": "2b9e7a54-2222-4f0e-8d11-000000000002",
  "facility_id": "c3a1f9d2-3333-4b6c-a2d4-000000000003",
  "starts_at": "2030-03-04T09:00:00Z",
  "ends_at": "2030-03-04T09:30:00Z",
  "reason_code": "FOLLOW_UP"
}
```

The response is the appointment (`id`, the three references, `starts_at`, `ends_at`, `status`, `reason_code`,
`cancellation_reason`, `version`, `created_by`, `created_at`, `updated_at`).

### Data model

| Table | Columns |
|-------|---------|
| `appointments` | `id` UUID, `patient_id` / `provider_id` / `facility_id` UUID refs, `starts_at`, `ends_at` (timestamptz, UTC), `status`, `reason_code`, `cancellation_reason` (nullable), `version` (optimistic lock), `created_by` (token `sub`), `created_at`, `updated_at` |
| `outbox_events` | `id` UUID, `aggregate_type` (`Appointment`), `aggregate_id`, `event_type`, `payload` JSON, `occurred_at`, `published_at` (nullable; set by a future publisher) |

Constraints: `ends_at > starts_at`, allowed statuses, `cancellation_reason` present exactly when `CANCELLED`,
upper-case `reason_code`, `version >= 1`, plus on PostgreSQL:

```sql
EXCLUDE USING gist (provider_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)
  WHERE (status IN ('BOOKED', 'CHECKED_IN', 'COMPLETED'))   -- ex_appointments_provider_overlap
```

### Business rules

- **Times** are timezone-aware ISO-8601 instants (naive values → 422), stored as UTC. Intervals are half-open
  `[starts_at, ends_at)`: 09:00–09:30 and 09:30–10:00 do not overlap. Duration 5 minutes to 8 hours. Booking and
  rescheduling require `starts_at` in the future.
- **Double-booking**: a provider cannot have two overlapping appointments in `BOOKED`, `CHECKED_IN` or `COMPLETED`.
  `CANCELLED` and `NO_SHOW` free the time. The application pre-check gives a friendly 409; the PostgreSQL
  exclusion constraint is the **final authority**, including for simultaneous requests (SQLSTATE `23P01` → 409).
  Overlaps for the same *patient* are not blocked (not in scope).
- **Transitions**: `BOOKED → CHECKED_IN → COMPLETED`, `BOOKED → CANCELLED`, `BOOKED → NO_SHOW`. Anything else →
  409. Only `BOOKED` appointments can be rescheduled.
- **Optimistic locking**: every change increments `version`. Reschedule requires the current `version`; cancel and
  transitions accept an optional one. A stale version → 409 (`details.current_version`), and concurrent updates
  that race past the check are rejected by SQLAlchemy's version counter → 409.
- **Codes, not text**: `reason_code` and `cancellation_reason` are administrative codes (`^[A-Za-z0-9_]{2,32}$`,
  stored upper-case, e.g. `FOLLOW_UP`, `PATIENT_REQUEST`). There is no free-text or clinical field.

### Outbox events

`AppointmentCreated`, `AppointmentRescheduled` and `AppointmentCancelled` rows are inserted into `outbox_events` in
the **same transaction** as the appointment change: if either write fails, neither is committed. Status transitions
(check-in, complete, no-show) do not emit events. There is no broker yet; a future publisher reads rows where
`published_at IS NULL`. Payload (IDs, times and status only — no reason codes, names or contact details):

```json
{"event_type": "AppointmentCreated", "appointment_id": "…", "patient_id": "…", "provider_id": "…",
 "facility_id": "…", "starts_at": "2030-03-04T09:00:00+00:00", "ends_at": "2030-03-04T09:30:00+00:00",
 "status": "BOOKED", "version": 1, "occurred_at": "…"}
```

### Scheduling advice (optional)

With `SCHEDULING_ADVICE_ENABLED=true`, booking and rescheduling call
`GET {SCHEDULING_SERVICE_URL}/api/v1/providers/{provider_id}/slots?facility_id&date_from&date_to` (forwarding the
caller's token, never logged). If the advertised slots do not cover the requested interval → 409. Scheduling 404 →
404, 409 → 409, unreachable or malformed → 503 `service_unavailable`. This is advice only: the exclusion constraint
still decides. The client is injected through `create_app(settings, scheduling_client=...)`; tests use a fake.

### Error format

Same envelope as the Identity service:

```json
{"error": {"code": "forbidden", "message": "Insufficient permissions"}}
```

| Status | `code` | When |
|--------|--------|------|
| 401 | `not_authenticated` | Missing, malformed, invalid or expired token. Includes a `WWW-Authenticate: Bearer` header |
| 403 | `forbidden` | Valid token, but no role grants the required permission |
| 404 | `not_found` | Unknown appointment |
| 409 | `conflict` | Provider already booked, invalid status transition, stale `version`, time outside Scheduling advice |
| 422 | `validation_error` | Invalid request (end before start, naive datetime, past start, bad duration, free-text reason, unknown field, …). Submitted values are never echoed back |
| 503 | `feature_disabled` | `APPOINTMENTS_ENABLED=false` on book / reschedule / cancel |
| 503 | `service_unavailable` | Scheduling advice enabled but the Scheduling service is unusable |

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
   strings are ignored. `created_by` is always the token `sub`.

| Role | Appointment-service permissions |
|------|---------------------------------|
| ADMIN | `appointments:read`, `appointments:book`, `appointments:transition` |
| RECEPTIONIST | `appointments:read`, `appointments:book`, `appointments:transition` |
| DOCTOR | `appointments:read`, `appointments:transition` |
| READ_ONLY | – |

**Revocation semantics.** Verification is stateless: a disabled account's existing token is accepted until it expires.

## Rollback

Booking, rescheduling and cancelling affect patients directly. Roll back immediately on any double booking, lost
appointment, or patient data shown to the wrong role or written to logs; also on a failed smoke test or an error
rate on appointment endpoints above the agreed threshold.

1. **Feature flag** — set `APPOINTMENTS_ENABLED=false` and restart. Book/reschedule/cancel return the 503
   `feature_disabled` error above; reads and transitions keep working; no data changes.
2. **Code revert** — `git revert -m 1 <merge-commit>` on a new branch → PR → CI → approval → merge. Never
   force-push `main`.
3. **Migration step-back** — `alembic downgrade -1` only if the schema breaks the previous code. For `0001` this
   **drops all appointment and outbox data**: take a backup and get explicit authorization first.
4. **Data repair** — bad records written while live are fixed by a reviewed script in its own PR.
5. **Close-out** — Jira incident ticket, affected records noted, regression test added.

## Limitations

- Development demo only; not a certified clinical system and no regulatory compliance is claimed.
- `patient_id`, `provider_id` and `facility_id` are not validated against their owning services (no contracts in
  Phase 6 scope); Scheduling advice is optional and off by default.
- DOCTOR can read and transition every appointment: the token does not link a user to a provider.
- Overlapping appointments for the same patient are allowed (only provider overlaps are blocked).
- Status transitions have no time-of-day guard (e.g. check-in before the start time is allowed).
- On SQLite (tests only) overlap protection relies on the pre-check; the exclusion constraint exists only on
  PostgreSQL.
- Outbox rows are written but not published (no broker yet).
- No immediate token revocation (see above).
