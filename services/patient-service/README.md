# Patient Service

Phase 2 of the Smart Hospital & Patient Management System (development demo). This service owns **patient
registration, demographics and patient lookup**. It verifies the Identity service's access tokens locally and never
calls Identity at runtime. It contains no clinical logic, and all data is synthetic.

## Responsibilities and data ownership

| Owns | Does not own |
|------|--------------|
| `patients` table (MRN, demographics, contact and address details, active flag, timestamps) | Users, passwords, roles or token issuance (Identity service) |
| Mapping Identity roles to Patient-service permissions | Provider, facility, scheduling, appointment, encounter or notification data |
| Its own Alembic migration history (`migrations/`) | Other services' databases. The patient database must not be shared |

## Layout

```
app/
  api/                # routers (v1/patients.py, health.py), dependencies (auth/permissions), error handlers, middleware
  core/               # config (env validation), JWT verifier, logging, errors, time helpers
  domain/             # Sex enum, MRN generator, Role / Permission enums and the role -> permission map
  models/             # SQLAlchemy models
  repositories/       # data access
  schemas/            # Pydantic request/response models
  services/           # use cases: register, get, search, update, deactivate
  main.py             # application factory (create_app)
migrations/           # Alembic environment + versions
tests/                # pytest suite (SQLite in-memory by default, optional PostgreSQL)
```

## Local setup

Requirements: Python 3.12+ and PostgreSQL 14+.

```bash
cd services/patient-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DATABASE_URL and copy the identity service's JWT_SECRET_KEY / JWT_ISSUER / JWT_AUDIENCE / JWT_KEY_ID.
```

Create a dedicated database and role for this service (example). Do not reuse the identity database:

```sql
CREATE USER patient_user WITH PASSWORD '<choose-a-local-password>';
CREATE DATABASE patient OWNER patient_user;
```

## Configuration

All settings come from environment variables (or `.env`). The service **fails fast at startup** when configuration
is invalid, and error messages name the setting without printing its value.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | – | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/patient` |
| `JWT_SECRET_KEY` | yes | – | Must equal the identity service's `JWT_SECRET_KEY`. At least 32/48/64 bytes for HS256/HS384/HS512. Placeholders are rejected |
| `JWT_ALGORITHM` | no | `HS256` | `HS256`, `HS384` or `HS512`. Tokens signed with any other algorithm (including `none`) are rejected |
| `JWT_KEY_ID` | no | `k1` | Expected `kid` header for `JWT_SECRET_KEY` |
| `JWT_ISSUER` | yes | – | Expected `iss` claim, e.g. `https://identity.smart-hospital.local` |
| `JWT_AUDIENCE` | yes | – | Expected `aud` claim, e.g. `smart-hospital-api` |
| `JWT_LEEWAY_SECONDS` | no | `30` | Allowed clock skew, 0–120 |
| `JWT_PREVIOUS_KEYS` | no | `{}` | JSON `{"kid": "secret"}` of retired identity keys still accepted during rotation |
| `APP_ENV` | no | `development` | `development`, `test` or `production` |
| `LOG_LEVEL` | no | `INFO` | |

## Migrations

```bash
alembic upgrade head        # apply (creates the patients table)
alembic current             # show revision
alembic downgrade base      # roll back everything
alembic check               # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # new migration
```

## Run

```bash
uvicorn app.main:create_app --factory --reload --port 8002 --no-access-log
```

- OpenAPI UI: http://localhost:8002/docs (click **Authorize** and paste an access token from
  `POST /api/v1/auth/login` on the identity service)
- OpenAPI JSON: http://localhost:8002/openapi.json

`--no-access-log` is **required** outside throwaway local use: uvicorn's access log includes the query string, and
search queries can contain patient names and dates of birth. The service writes its own structured request logs
(method, path without query string, status, duration, request ID).

## Test

```bash
pytest                       # isolated: in-memory SQLite, synthetic fixtures, test-only JWT secret, no external services
ruff check . && ruff format --check .

# Optional: run the same suite against a disposable PostgreSQL database
TEST_DATABASE_URL=postgresql+psycopg://patient_user:<pw>@localhost:5432/patient_test pytest
```

> The suite drops and recreates tables in the `TEST_DATABASE_URL` database. Never point it at a database you need.

## API

| Method | Path | Permission | Roles | Success |
|--------|------|------------|-------|---------|
| GET | `/health` | public | – | 200 `{"status": "ok"}` (liveness) |
| GET | `/health/ready` | public | – | 200 `{"status": "ok", "database": "ok"}`, or 503 `{"status": "unavailable", "database": "error"}` |
| POST | `/api/v1/patients` | `patients:write` | RECEPTIONIST, ADMIN | 201 full patient |
| GET | `/api/v1/patients/{id}` | `patients:read` | RECEPTIONIST, DOCTOR, ADMIN | 200 full patient |
| GET | `/api/v1/patients?search=&limit=&offset=&is_active=` | `patients:read` | RECEPTIONIST, DOCTOR, ADMIN | 200 page of patient summaries |
| PATCH | `/api/v1/patients/{id}` | `patients:write` | RECEPTIONIST, ADMIN | 200 full patient |
| POST | `/api/v1/patients/{id}/deactivate` | `patients:deactivate` | ADMIN | 200 full patient (`is_active: false`) |

`READ_ONLY` has no Patient-service permissions. There is no delete endpoint: records are only soft-deactivated.

### Patient fields

| Field | Create | Update | Rules |
|-------|--------|--------|-------|
| `id`, `medical_record_number`, `is_active`, `created_at`, `updated_at` | server | server | Read-only. Sending them returns 422. MRN format `MRN-` + 10 Crockford base32 characters, unique |
| `first_name`, `last_name` | required | optional, not null | 1–100 characters, trimmed |
| `date_of_birth` | required | optional, not null | ISO date, 1900-01-01 to today (UTC) |
| `sex` | required | optional, not null | `FEMALE`, `MALE`, `OTHER`, `UNKNOWN` |
| `phone` | optional | optional, nullable | 7–32 characters: digits, spaces, `()-`, optional leading `+` |
| `email` | optional | optional, nullable | Valid email, stored lowercase |
| `address_line1`, `address_line2` | optional | optional, nullable | Up to 200 characters |
| `city`, `state` | optional | optional, nullable | Up to 100 characters |
| `postal_code` | optional | optional, nullable | 2–20 letters, digits, spaces or `-` |
| `country` | optional | optional, nullable | ISO 3166-1 alpha-2, stored uppercase |

`PATCH` needs at least one field. Setting an optional field to `null` clears it. Updating or deactivating an inactive
patient returns 409.

### Search and pagination

- `search` (optional, 1–100 characters) is split on whitespace (first 5 terms used) and **every** term must match one of: a
  case-insensitive prefix of first or last name, an exact MRN, or an exact date of birth (`YYYY-MM-DD`).
  Example: `search=rivera 1985-03-14`.
- `limit` 1–100 (default 20), `offset` ≥ 0 (default 0), `is_active` optional `true`/`false` filter.
- Results are ordered by last name, first name, creation time and id. The response is
  `{"items": [...], "total": n, "limit": l, "offset": o}`, and each item contains only `id`, `medical_record_number`,
  `first_name`, `last_name`, `date_of_birth`, `sex` and `is_active`.

### Error format

Every error uses the identity service's envelope:

```json
{"error": {"code": "not_found", "message": "Patient not found"}}
```

| Status | Code | When |
|--------|------|------|
| 401 | `not_authenticated` | Missing, malformed, expired or otherwise invalid token (`WWW-Authenticate: Bearer`) |
| 403 | `forbidden` | Valid token, but no role grants the required permission |
| 404 | `not_found` | Unknown patient id |
| 409 | `conflict` | Patient inactive, or no unique MRN could be allocated |
| 422 | `validation_error` | Invalid body, path or query. `details` lists `loc`, `msg` and `type` per error and never echoes submitted values |

## Token verification

Tokens are verified locally against the identity service's
[JWT access-token contract](../identity-service/README.md#jwt-access-token-contract-for-other-services):

- The header `alg` must equal `JWT_ALGORITHM`, and `kid` must be `JWT_KEY_ID` or a key in `JWT_PREVIOUS_KEYS`.
- The signature, `exp`, `nbf` and `iat` (with `JWT_LEEWAY_SECONDS`), `iss` and `aud` are all checked.
- `sub`, `jti`, `iat`, `nbf`, `exp`, `iss` and `aud` are required.
- `token_use` must be `access`, `sub` must be a UUID, and `roles` must be a non-empty list of known roles.
- Roles are mapped to permissions in `app/domain/roles.py`. The client cannot supply its own permissions.

## Security notes

- Logs never include tokens, authorization headers, request bodies, query strings, names, dates of birth or contact
  details. Patient events log only the patient UUID, the actor's `sub` and the names of changed fields.
- Validation errors do not echo submitted values.
- `.env` is git-ignored. Commit `.env.example` with placeholders only.
- This is a development demo and is not a certified clinical system. It makes no HIPAA/GDPR claims.

## Limitations and follow-ups

- Tokens are stateless. A user who is deactivated in Identity keeps access until their token expires (at most 60
  minutes, 15 by default), because this service does not call Identity.
- No duplicate-patient detection (for example on name + date of birth), no merge, and no reactivation endpoint.
- Search is prefix/exact matching only (no fuzzy or phonetic matching). Name matching uses `lower()` indexes.
- No audit-trail table. Changes are only recorded in structured logs.
- `total` uses a separate `COUNT` query, so it can change between pages under concurrent writes.
