# Identity & Access Service

Phase 1 of the Smart Hospital & Patient Management System (development demo). This service owns **user accounts,
password hashes, demo roles and JWT access-token issuance**. Every other service verifies the tokens it issues using
the contract below. It does not contain clinical logic, and all data is synthetic.

## Responsibilities and data ownership

| Owns | Does not own |
|------|--------------|
| `users` table (staff accounts, Argon2id password hashes, role, active flag, login timestamps) | Patient, provider, facility, scheduling, appointment, encounter or notification data |
| Access-token issuance and the token contract | Authorization decisions inside other services (each one maps roles to its own permissions) |
| Its own Alembic migration history (`migrations/`) | Other services' databases. The identity database must not be shared |

## Layout

```
app/
  api/            # routers (v1/auth.py, v1/users.py, v1/roles.py, health.py), dependencies, error handlers, middleware
  core/           # config (env validation), JWT token service, password hashing, logging, errors
  domain/roles.py # Role / Permission enums and the role -> permission map
  models/         # SQLAlchemy models
  repositories/   # data access
  schemas/        # Pydantic request/response models
  services/       # use cases: auth, user management, demo seeding
  cli.py          # `python -m app.cli seed-demo-users`
  main.py         # application factory (create_app)
migrations/       # Alembic environment + versions
tests/            # pytest suite (SQLite in-memory by default, optional PostgreSQL)
```

## Local setup

Requirements: Python 3.12+ and PostgreSQL 14+.

```bash
cd services/identity-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DATABASE_URL, generate JWT_SECRET_KEY and choose SEED_DEMO_PASSWORD.
python -c "import secrets; print(secrets.token_urlsafe(64))"   # -> JWT_SECRET_KEY
```

Create a dedicated database and role for this service (example):

```sql
CREATE USER identity_user WITH PASSWORD '<choose-a-local-password>';
CREATE DATABASE identity OWNER identity_user;
```

## Configuration

All settings come from environment variables (or `.env`). The service **fails fast at startup** when configuration
is invalid, and error messages name the setting without printing its value.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | – | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/identity` |
| `JWT_SECRET_KEY` | yes | – | Random secret: at least 32 bytes for HS256, 48 for HS384, 64 for HS512. Placeholders are rejected |
| `JWT_ALGORITHM` | no | `HS256` | `HS256`, `HS384` or `HS512`. `none` and every other algorithm is rejected |
| `JWT_KEY_ID` | no | `k1` | Emitted as the `kid` header |
| `JWT_ISSUER` | yes | – | `iss` claim, e.g. `https://identity.smart-hospital.local` |
| `JWT_AUDIENCE` | yes | – | `aud` claim, e.g. `smart-hospital-api` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | no | `15` | 1–60 |
| `JWT_LEEWAY_SECONDS` | no | `30` | Allowed clock skew, 0–120 |
| `JWT_PREVIOUS_KEYS` | no | `{}` | JSON `{"kid": "secret"}` of retired keys still accepted for verification |
| `APP_ENV` | no | `development` | `development`, `test` or `production` (seeding is blocked in production) |
| `LOG_LEVEL` | no | `INFO` | |
| `SEED_DEMO_PASSWORD` | seed only | – | Password for the fictional demo accounts, at least 12 characters |

## Migrations

```bash
alembic upgrade head        # apply
alembic current             # show revision
alembic downgrade base      # roll back everything
alembic check               # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # new migration
```

## Seed demo accounts (development only)

```bash
python -m app.cli seed-demo-users
```

This creates one fictional account per role. Every account uses the password from `SEED_DEMO_PASSWORD`. Running it
again leaves existing accounts unchanged, and it refuses to run when `APP_ENV=production`.

| Email | Role |
|-------|------|
| `admin@demo.smarthospital.example` | ADMIN |
| `reception@demo.smarthospital.example` | RECEPTIONIST |
| `doctor@demo.smarthospital.example` | DOCTOR |
| `readonly@demo.smarthospital.example` | READ_ONLY |

## Run

```bash
uvicorn app.main:create_app --factory --reload --port 8001 --no-access-log
```

- OpenAPI UI: http://localhost:8001/docs (click **Authorize** and paste an access token)
- OpenAPI JSON: http://localhost:8001/openapi.json

`--no-access-log` is recommended because the service writes its own structured request logs (method, path without
query string, status, duration, request ID).

## Test

```bash
pytest                       # isolated: in-memory SQLite, synthetic fixtures, no external services
ruff check . && ruff format --check .

# Optional: run the same suite against a disposable PostgreSQL database
TEST_DATABASE_URL=postgresql+psycopg://identity_user:<pw>@localhost:5432/identity_test pytest
```

> The suite drops and recreates tables in the `TEST_DATABASE_URL` database. Never point it at a database you need.

## API (`/api/v1`)

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| POST | `/auth/login` | public | `{email, password}` returns `{access_token, token_type: "bearer", expires_in}` |
| GET | `/auth/me` | any authenticated user | Current user profile |
| GET | `/roles` | any authenticated user (`roles:read`) | Roles, descriptions and identity permissions |
| GET | `/users?limit&offset&role&is_active` | ADMIN (`users:read`) | Paginated list, ordered by `created_at`, `id`. `limit` 1–100 (default 20) |
| POST | `/users` | ADMIN (`users:manage`) | Create a user (`email`, `full_name`, `role`, `password`, optional `is_active`) |
| GET | `/users/{id}` | ADMIN (`users:read`) | Get a user |
| PATCH | `/users/{id}` | ADMIN (`users:manage`) | Update `full_name`, `role` and/or `is_active` |
| POST | `/users/{id}/password` | ADMIN (`users:manage`) | Set a new password (`new_password`), returns 204 |
| GET | `/health`, `/health/ready` | public | Liveness, and readiness including a database check |

Business rules:
- Emails are stored lowercase and are unique (409 on duplicates).
- Passwords must be 12–128 characters and are hashed with Argon2id. Plaintext passwords are never stored.
- An admin cannot disable their own account or remove their own ADMIN role (409). Any change that would disable or demote
  the last active ADMIN is also rejected (409); admin-status changes lock the active ADMIN rows, so two admins demoting
  each other concurrently cannot leave the system without an admin.
- Accounts are disabled, not deleted, so they can still be audited.

### Error format

Every error uses one envelope:

```json
{"error": {"code": "not_authenticated", "message": "Invalid or expired token"}}
```

| Status | `code` | When |
|--------|--------|------|
| 401 | `not_authenticated` | Missing, malformed, invalid or expired token; failed login. Includes a `WWW-Authenticate: Bearer` header |
| 403 | `forbidden` | Authenticated, but the role lacks the required permission |
| 404 | `not_found` | Unknown resource |
| 409 | `conflict` | Duplicate email, admin self-lockout, removing the last active admin |
| 422 | `validation_error` | Invalid request. `details` lists `loc`/`msg`/`type`; submitted values are never echoed back (messages that could embed input are replaced with `Invalid value`) |

Every failed login (unknown email, wrong password or disabled account) returns the same `401 Invalid credentials`,
so callers cannot tell which accounts exist.

### Roles and permissions

| Role | Identity-service permissions |
|------|------------------------------|
| ADMIN | `roles:read`, `users:read`, `users:manage` |
| RECEPTIONIST | `roles:read` |
| DOCTOR | `roles:read` |
| READ_ONLY | `roles:read` |

Downstream services define their own role-to-permission maps (for example, the Patient service decides what
RECEPTIONIST may do).

Reusable FastAPI dependencies live in `app/api/deps.py`:

```python
from app.api.deps import CurrentUser, require_permission, require_roles


@router.get("/admin-only")
def handler(user: Annotated[User, Depends(require_roles(Role.ADMIN))]): ...


@router.post("/users")
def handler(user: Annotated[User, Depends(require_permission(Permission.USERS_MANAGE))]): ...
```

Inside the identity service, `get_current_user` reloads the account on every request. A disabled account therefore
loses access here immediately, and the database role always overrides the role in the token.

## JWT access-token contract (for other services)

Tokens are compact JWS, signed with an HMAC algorithm (HS256 by default) and sent as `Authorization: Bearer <token>`.

**Header**

| Field | Value |
|-------|-------|
| `alg` | Configured algorithm (`HS256` by default) |
| `typ` | `JWT` |
| `kid` | Signing key ID (`JWT_KEY_ID`) |

**Claims**

| Claim | Type | Meaning |
|-------|------|---------|
| `iss` | string | Must equal the configured `JWT_ISSUER` |
| `aud` | string | Must equal the configured `JWT_AUDIENCE` |
| `sub` | string (UUID) | User ID in the identity service, a stable reference other services may store |
| `iat` | int (epoch seconds) | Issued at |
| `nbf` | int (epoch seconds) | Not before (equals `iat`) |
| `exp` | int (epoch seconds) | Expiry, by default `iat` + 15 minutes |
| `jti` | string (UUID) | Unique token ID (for audit and correlation) |
| `token_use` | string | Always `"access"` |
| `roles` | array of strings | Non-empty subset of `ADMIN`, `RECEPTIONIST`, `DOCTOR`, `READ_ONLY` (one role per user in this phase) |

Tokens contain no email, name or patient data. If a service needs profile data, it should call `GET /api/v1/auth/me`
with the caller's token.

**Verification steps every service must perform** (all of them, server-side):

1. Read the token from `Authorization: Bearer`. If it is missing, respond 401.
2. Read the header **without trusting it**. Reject the token unless `alg` exactly equals the configured algorithm
   (never accept `none`), and pick the key by `kid` from the configured key set. An unknown `kid` means reject.
3. Verify the signature, `exp`, `nbf` and `iat` (allowing up to 30 s of clock skew), plus `iss` and `aud` against
   configuration. Require all of `iss, aud, sub, iat, nbf, exp, jti` to be present.
4. Require `token_use == "access"`, require `sub` to be a valid UUID, and require `roles` to be a non-empty list
   containing only known roles.
5. Authorize from `roles` using the service's own permission map. Insufficient permission means 403. Never trust
   roles or user IDs supplied in request bodies or query strings.
6. Never log the token.

Reference implementation: `TokenService.decode_access_token` in `app/core/tokens.py`. A minimal PyJWT equivalent:

```python
header = jwt.get_unverified_header(token)
if header.get("alg") != EXPECTED_ALG or header.get("kid") not in KEYS:
    raise Unauthorized
claims = jwt.decode(
    token,
    KEYS[header["kid"]],
    algorithms=[EXPECTED_ALG],
    audience=AUDIENCE,
    issuer=ISSUER,
    leeway=30,
    options={"require": ["iss", "aud", "sub", "iat", "nbf", "exp", "jti"]},
)
if claims.get("token_use") != "access":
    raise Unauthorized
```

**Revocation semantics.** Verification is stateless. If an account is disabled or its role changes, other services
keep accepting the existing token until it expires (15 minutes by default, 60 at most). Keep lifetimes short. Any
endpoint that needs immediate revocation can call `GET /api/v1/auth/me`, which re-checks the account.

### Key rotation

1. Generate a new secret and give it a new `JWT_KEY_ID` (for example `k2`).
2. Move the old key into `JWT_PREVIOUS_KEYS` (`{"k1": "<old secret>"}`) and set the new key as `JWT_SECRET_KEY`.
   Deploy the identity service and every verifying service with the updated key set. New tokens are signed with
   `k2`, while tokens signed with `k1` still verify.
3. Once the maximum token lifetime plus leeway has passed, remove `k1` from `JWT_PREVIOUS_KEYS` everywhere.
4. If a key is compromised, remove it immediately. All tokens signed with it become invalid.

**Important limitation of HMAC.** With HS256, every verifying service holds the same secret and could therefore mint
tokens. That is acceptable for this demo, but before any real deployment switch to an asymmetric algorithm (RS256 or
ES256). The identity service would then keep the private key, publish public keys through a JWKS endpoint, and other
services would verify with the public key only. The `kid` header and key-set design already support this change.

## Security notes

- Passwords are hashed with Argon2id (`argon2-cffi`, RFC 9106 defaults). Hashes are upgraded on login when the
  parameters change. Login for an unknown user runs a dummy verification so its response time matches a real one.
- Logs are JSON. They never contain passwords, tokens, emails, request bodies or headers. Login and token events
  record only the event name, reason and user ID.
- Configuration validation rejects missing, short or placeholder secrets and unsupported algorithms. Error messages
  never include secret values.
- Validation errors never echo submitted values. Request models reject unknown fields (`extra="forbid"`).

## Limitations and follow-ups

- No refresh tokens, SSO/OIDC, MFA, self-service password change or password-reset email flow. These are out of scope
  for this phase.
- Login has no rate limiting or account lockout yet. Add it at the gateway or in this service before any real
  exposure.
- HMAC signing means verifiers share the secret. Move to RS256/ES256 with JWKS (see above).
- Stateless tokens cannot be revoked before they expire (there is no denylist).
- One role per user. Multiple roles would need a join table, but the `roles` claim is already an array.
- No audit-log table yet. Admin actions appear only in the structured logs.
- `starlette.testclient` currently emits a deprecation warning recommending `httpx2`. It is harmless; revisit when
  upgrading FastAPI/Starlette.
