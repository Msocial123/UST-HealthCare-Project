# Provider Service

Phase 3 of the Smart Hospital & Patient Management System (development demo). This service owns **provider
(doctor) profiles, specialties, provider–specialty assignments and provider active status**. It contains no
diagnosis, treatment or other clinical logic, and all data is synthetic.

## Responsibilities and data ownership

| Owns | Does not own |
|------|--------------|
| `specialties`, `providers`, `provider_specialties` tables | Users, passwords or token issuance (Identity service) |
| Its own Alembic migration history (`migrations/`) | Facilities and departments. `facility_id` / `department_id` are stored as plain UUID references and are **not** validated (the Facility service does not exist yet) |
| Provider-service authorization (role → permission map) | Any other service's database. The provider database must not be shared |

The service makes **no runtime calls** to other services. Access tokens issued by the Identity service are verified
locally (see [Authentication](#authentication)).

## Layout

```
app/
  api/            # routers (v1/specialties.py, v1/providers.py, health.py), deps (auth), error handlers, middleware
  core/           # config (env validation), JWT verifier, logging, errors, time helpers
  domain/roles.py # Role / Permission enums and the role -> permission map
  models/         # SQLAlchemy models (Specialty, Provider, ProviderSpecialty)
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
cd services/provider-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DATABASE_URL and copy the JWT_* values used by the Identity service.
```

Create a dedicated database and role for this service (example):

```sql
CREATE USER provider_user WITH PASSWORD '<choose-a-local-password>';
CREATE DATABASE provider OWNER provider_user;
```

## Configuration

All settings come from environment variables (or `.env`). The service **fails fast at startup** when configuration
is invalid, and error messages name the setting without printing its value.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | – | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/provider` |
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
alembic upgrade head        # apply (creates specialties, providers, provider_specialties)
alembic current             # show revision
alembic downgrade base      # roll back everything
alembic check               # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # new migration
```

## Run

```bash
uvicorn app.main:create_app --factory --reload --port 8003 --no-access-log
```

- OpenAPI UI: http://localhost:8003/docs (click **Authorize** and paste an access token from the Identity service
  `POST /api/v1/auth/login`)
- OpenAPI JSON: http://localhost:8003/openapi.json

The service writes its own structured request logs (method, path without query string, status, duration, request ID).
Tokens, request bodies, query strings and contact details are never logged.

## Test

```bash
pytest                       # isolated: in-memory SQLite, tokens minted with a test-only secret, no external services
ruff check . && ruff format --check .

# Optional: run the same suite against a disposable PostgreSQL database
TEST_DATABASE_URL=postgresql+psycopg://provider_user:<pw>@localhost:5432/provider_test pytest
```

> The suite drops and recreates tables in the `TEST_DATABASE_URL` database. Never point it at a database you need.

## API (`/api/v1`)

| Method | Path | Access (permission) | Description |
|--------|------|---------------------|-------------|
| GET | `/health`, `/health/ready` | public | Liveness, and readiness including a database check (no `/api/v1` prefix) |
| POST | `/specialties` | ADMIN (`specialties:manage`) | Create a specialty `{code, name, description?, is_active?}` |
| GET | `/specialties?active&limit&offset` | any authenticated role (`specialties:read`) | Paginated list ordered by `code` |
| PATCH | `/specialties/{id}` | ADMIN (`specialties:manage`) | Update `name`, `description` and/or `is_active` (deactivate). `code` is immutable |
| POST | `/providers` | ADMIN (`providers:manage`) | Create a provider with one or more specialties |
| GET | `/providers?search&specialty&active&limit&offset` | RECEPTIONIST, DOCTOR, ADMIN (`providers:read`) | Paginated search, ordered by `last_name`, `first_name`, `id` |
| GET | `/providers/{id}` | RECEPTIONIST, DOCTOR, ADMIN (`providers:read`) | Get one provider with specialties |
| PATCH | `/providers/{id}` | ADMIN (`providers:manage`) | Partial profile update; `specialties`, when sent, replaces the full set |
| POST | `/providers/{id}/deactivate` | ADMIN (`providers:manage`) | Set `is_active=false` (idempotent). Providers are never hard-deleted |
| POST | `/providers/{id}/activate` | ADMIN (`providers:manage`) | Set `is_active=true` (idempotent) |

`limit` is 1–100 (default 20) and `offset` ≥ 0 on every list endpoint. List responses are
`{items, total, limit, offset}`.

Search: `search` (1–100 chars) matches a case-insensitive substring of the provider's full name
(`first last` or `last first`) or provider number, **or** an exact specialty code. `specialty` filters by exact
specialty code (case-insensitive). `active` filters by status.

Example create request (synthetic data):

```json
{
  "title": "Dr",
  "first_name": "Avery",
  "last_name": "Testwell",
  "work_email": "avery.testwell@provider.example",
  "work_phone": "+1 555 0100",
  "license_number": "LIC-DEMO-0001",
  "years_of_experience": 7,
  "facility_id": null,
  "department_id": null,
  "specialties": [
    {"specialty_id": "<specialty uuid>", "is_primary": true}
  ]
}
```

### Business rules

- Specialty `code` is 2–32 characters `[A-Za-z0-9_]`, stored uppercase, unique (409). `name` is unique,
  case-insensitively (409).
- `provider_number` is generated by the server (`PRV-` + 8 hex characters) and is unique; clients cannot set it.
- `license_number` (synthetic) is 4–32 characters `[A-Za-z0-9-]`, stored uppercase and unique (409).
- A provider has 1–20 specialties with **exactly one** `is_primary: true` (422 otherwise); each specialty may appear
  once (422). The database also enforces at most one primary per provider (partial unique index).
- Unknown specialty IDs return **404** (`details.specialty_ids` lists them).
- **Assigning an inactive specialty returns 409 `conflict`** (`details.specialty_ids` lists them). Deactivating a
  specialty does not remove it from providers that already have it; those existing assignments may be kept on
  update, but an inactive specialty cannot be newly added.
- `years_of_experience` is 0–70. `work_phone` allows digits, spaces, `()`, `-` and a leading `+`.
- `is_active` is changed only through `/activate` and `/deactivate`; there is no DELETE endpoint.
- Timestamps are timezone-aware UTC.

### Error format

Same envelope as the Identity service:

```json
{"error": {"code": "forbidden", "message": "Insufficient permissions"}}
```

| Status | `code` | When |
|--------|--------|------|
| 401 | `not_authenticated` | Missing, malformed, invalid or expired token. Includes a `WWW-Authenticate: Bearer` header |
| 403 | `forbidden` | Valid token, but no role grants the required permission |
| 404 | `not_found` | Unknown provider or specialty |
| 409 | `conflict` | Duplicate specialty code/name or license number; assigning an inactive specialty |
| 422 | `validation_error` | Invalid request or business-rule violation (e.g. not exactly one primary specialty). Submitted values are never echoed back |

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

| Role | Provider-service permissions |
|------|------------------------------|
| ADMIN | `specialties:read`, `specialties:manage`, `providers:read`, `providers:manage` |
| RECEPTIONIST | `specialties:read`, `providers:read` |
| DOCTOR | `specialties:read`, `providers:read` |
| READ_ONLY | `specialties:read` |

**Revocation semantics.** Verification is stateless: if an Identity account is disabled or its role changes, its
existing token is accepted here until it expires (15 minutes by default in Identity, 60 at most).

## Limitations

- Development demo only; not a certified clinical system and no regulatory compliance is claimed.
- `facility_id` / `department_id` are unvalidated references until the Facility service exists.
- No immediate token revocation (see above).
- Searching uses `LIKE` on indexed columns; large datasets would need trigram/full-text indexes.
