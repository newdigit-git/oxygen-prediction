# Oxygen Prediction — Production Readiness & Integration Assessment

**Assessment date:** 2026-09-27  
**Repository:** `newdigit-git/oxygen-prediction`  
**Commit reviewed:** `0a407cf` (`main`)  
**Scope:** API startup, database integration, workers, containerization, security, reliability, and production rollout readiness.

## Executive summary

The repository is a promising prototype, but it is **not ready for production deployment** or a production device integration yet. The primary issue is not missing polish; the API, worker, and database layers currently describe **different application architectures**.

### Release decision

**Do not deploy to a production healthcare or device environment yet.** A controlled development/demo deployment is possible after fixing the startup and Compose configuration, but production telemetry should wait until authentication, idempotency, migrations, observability, and data-contract testing are in place.

### Validated blockers

1. **API startup fails with the documented PostgreSQL stack.** `app/core/database.py` always creates an async engine, but `asyncpg` is absent from `requirements.txt`. Importing `app.main` with a PostgreSQL URL fails with `ModuleNotFoundError: No module named 'asyncpg'`.
2. **Compose does not provide a valid database URL.** `docker-compose.yml` sets `DATABASE_URL: None`; the application expects a SQLAlchemy URL. It also forces `DEBUG=True` and Uvicorn `--reload`.
3. **Celery worker code targets nonexistent modules and models.** `app/workers/tasks.py` imports `app.db.session`, `app.models.telemetry`, `app.models.session`, `app.models.prediction`, and `app.models.forecast`, none of which exist in this repository. The actual models live in `app/models/models.py` and use different field names.
4. **The worker is not integrated into Compose.** Redis is started, but there is no Celery worker service, no queue configuration exposed for deployment, and no task dispatch from the API ingestion path.
5. **There are two divergent service implementations.** `app/api/routes/telemetry.py` contains a large `IngestionService`/engine implementation, while `app/services/ingestion_service.py` contains another. Telemetry routes use the former; session routes use the latter. Behavior, validation, logging, and idempotency are therefore inconsistent.
6. **No automated tests are present.** There is no `tests/` directory or test file, so API contracts, calculations, database behavior, and worker behavior are unverified.

## What was checked

| Check | Result |
|---|---|
| Python compilation (`python -m compileall -q app`) | Passes syntax compilation only |
| Import with `DATABASE_URL=postgresql+psycopg2://...` | Fails: missing `asyncpg` |
| Import with SQLite test URL | Fails: async SQLAlchemy engine cannot use the synchronous SQLite driver |
| Internal worker import targets | Several referenced module paths are absent |
| Declared dependencies vs imports | `structlog`, `tenacity`, and `asyncpg` are imported/required by code paths but not declared |
| Documented endpoint inventory vs route declarations | README claims endpoints that are not implemented |
| Docker/Compose validation in sandbox | Docker CLI unavailable; static inspection identifies configuration blockers |

## Architecture observed

### Working API path (partial)

`FastAPI -> SQLAlchemy sync session -> PostgreSQL -> ORM models in app/models/models.py`

The API currently creates tables at import time using `Base.metadata.create_all(bind=engine)`. This is unsuitable for controlled production schema evolution.

### Intended but currently disconnected async path

`API/device ingestion -> Celery -> Redis -> enrichment/prediction tasks`

The intended worker path references a second schema (`TelemetryRecord`, `OxygenSession`, `DepletionPrediction`, `SurgeForecast`) that is not present. It cannot process records from the actual API models without a deliberate migration or rewrite.

## Findings by priority

### P0 — Must fix before any production deployment

#### 1. Establish one canonical domain model and service layer

Remove the duplicated implementation from `app/api/routes/telemetry.py` and keep business logic in `app/services/`. Routes should validate, authorize, call a service, and translate known exceptions to HTTP responses.

Choose one schema. The lowest-risk path is to adapt the worker to the existing models in `app/models/models.py`, or explicitly replace those models with the worker’s richer schema. Do not mix both.

#### 2. Make the application start deterministically

- Add `asyncpg` only if async database support is retained; otherwise remove the unused async engine and async session setup.
- Add every imported runtime dependency to `requirements.txt`, including at minimum the currently imported `structlog` and `tenacity`.
- Fail fast with a clear configuration error when `DATABASE_URL` is missing or invalid.
- Do not create an async engine for a sync-only URL or a sync engine for an async-only URL.
- Add a startup smoke test that imports the app with a production-like PostgreSQL URL.

#### 3. Replace `create_all()` with migrations

- Add an Alembic environment and an initial migration for all seven tables.
- Run migrations as a release/deployment step, not during web process import.
- Add explicit indexes and constraints for telemetry timestamps, device IDs, session IDs, and prediction lookup paths.
- Decide and document the telemetry partitioning strategy; the README claims partitioning but the schema does not implement it.

#### 4. Repair the production container stack

The current Compose file is development-only:

- `DATABASE_URL: None` is unusable.
- Database and Redis ports are exposed publicly to the host by default.
- Database credentials are hard-coded.
- API runs with `DEBUG=True`, bind-mounted source, and `--reload`.
- No Celery worker or beat/scheduler service exists.
- No API container healthcheck exists.
- `depends_on` health ordering does not replace application-level retry/readiness.

Use environment interpolation and separate development/production Compose files or a production orchestrator. The production API command should use multiple workers (or a managed process model) without reload.

#### 5. Add device/API authentication and tenant authorization

The telemetry endpoint currently accepts unauthenticated writes and the CORS policy is `allow_origins=["*"]` with credentials enabled. For production:

- Use per-device credentials or signed ingestion tokens, with rotation and revocation.
- Add operator authentication (OIDC/OAuth2 or an existing identity provider).
- Enforce facility/tenant scoping on every read and write.
- Restrict CORS to known frontend origins; never combine wildcard origins with credentials.
- Add rate limits and payload size limits to ingestion endpoints.

#### 6. Define ingestion idempotency and replay behavior

Telemetry rows have no device event ID or uniqueness key. Network retries can create duplicates. Add a device-generated event ID (or deterministic compound key) and a unique constraint. Document behavior for delayed, out-of-order, duplicated, and future-dated readings.

Session ingestion has inconsistent idempotency: one service checks existing `sid`, the other inserts directly and can fail on duplicate keys.

### P1 — Required before pilot rollout

#### API contract and validation

- Add bounds and types in Pydantic models: battery 0–100, signal range, finite non-negative pressure/flow, bounded string lengths, valid latitude/longitude, and timezone-aware timestamps.
- Use `datetime` for telemetry timestamps or clearly document Unix seconds and validate the allowed clock skew.
- Return a stable error schema; do not expose raw exception strings or database details to clients.
- Add the missing README endpoints or update the README. Currently documented but absent: `GET /`, `GET /api/v1/telemetry/device/{device_id}`.
- Validate and bound `limit` query parameters; currently they can be negative or unreasonably large.
- Return `202 Accepted` for asynchronous enrichment if processing is moved to Celery, with an ingestion/event ID for status tracking.

#### Worker integration

- Rewrite worker imports against the canonical schema.
- Add a real `celery` worker service to deployment.
- Dispatch a task after successful ingestion, preferably using an outbox/event table so database commit and task publication cannot diverge.
- Make tasks idempotent and use deterministic prediction keys to avoid duplicate predictions on retries.
- Set retry policies for transient external APIs, with dead-letter handling and alerting.
- Do not send raw clinical or device-sensitive data to an LLM or external service without an explicit data-processing, retention, and contractual review.

#### Reliability and observability

- Add `/health/live` and `/health/ready`; readiness must check PostgreSQL and Redis where applicable.
- Add structured logs with request ID, device ID, tenant/facility ID, event ID, latency, and outcome. Avoid logging sensitive payloads.
- Add metrics for ingestion rate, rejection rate, duplicate rate, queue lag, task failures, prediction age, database pool exhaustion, and external API latency.
- Add OpenTelemetry or equivalent tracing across API, database, Redis, and external APIs.
- Configure connection pool size, overflow, timeout, and recycle values explicitly for expected load.
- Add graceful shutdown and bounded request timeouts.

#### Data and clinical safety

- Store units explicitly and normalize pressure/flow units at ingestion.
- Record model version, input window, calibration metadata, and confidence for every prediction.
- Treat `float('inf')` as a domain state, not a value to serialize into JSON or store blindly.
- Separate decision support from clinical decision-making; predictions and LLM narratives require review, validation, and fail-safe behavior.
- Define retention, deletion, access audit, encryption at rest/in transit, backup, and restore procedures.

### P2 — Recommended for scale and maintainability

- Use a typed settings object with secrets supplied by the runtime secret manager.
- Add CI for formatting, linting, type checking, dependency audit, unit tests, integration tests, and container vulnerability scanning.
- Add a staging environment with synthetic device traffic and failure injection.
- Add load tests for the expected telemetry rate and database growth.
- Partition or archive telemetry based on measured volume.
- Add API versioning and an OpenAPI contract consumed by the device gateway/frontend.
- Add a runbook for migration, rollback, worker drain, key rotation, and incident response.

## Recommended target production integration

```text
Smart regulators
      |
      | TLS + per-device credential + event_id
      v
Ingress/API gateway (rate limiting, WAF, request IDs)
      |
      v
FastAPI ingestion service ----> PostgreSQL (canonical schema + Alembic)
      |                                  |
      | outbox/event record               | read models / audit trail
      v                                  v
Redis broker -> Celery workers      Analytics API / dashboard
      |                                  |
      +--> validation/enrichment         +--> facility-scoped auth
      +--> depletion predictions         +--> readiness/metrics
      +--> optional climate adapters
      +--> notifications
```

External climate APIs and LLMs should be adapters behind interfaces, with explicit timeouts, retries, caching policy, circuit breakers, and a deterministic fallback. They should not be required for basic telemetry ingestion or safety-critical depletion calculations.

## Suggested implementation sequence

1. **Stabilize the API:** canonicalize models/services, fix dependencies and database engine selection, add settings validation, and make the app import/start with PostgreSQL.
2. **Make deployment reproducible:** add Alembic, production Compose/manifests, secret interpolation, API/worker healthchecks, and a worker service.
3. **Secure the boundary:** device authentication, operator authentication, tenant isolation, CORS restriction, rate limits, and stable errors.
4. **Make ingestion reliable:** event IDs, uniqueness constraints, outbox/task dispatch, retry semantics, and telemetry timestamp/unit validation.
5. **Add verification:** unit tests for calculations, API contract tests, PostgreSQL integration tests, worker tests, and a synthetic end-to-end device replay.
6. **Pilot in staging:** run representative load, external API outages, Redis outages, duplicate/reordered readings, database failover, and rollback drills.
7. **Production release:** only after monitoring dashboards, alert thresholds, backups/restore, security review, and an operational owner are in place.

## Minimum acceptance criteria for a production pilot

- API and worker start from clean environments using only declared dependencies.
- Alembic migration creates the schema; no `create_all()` in the web process.
- All documented live endpoints have contract tests.
- Duplicate and out-of-order device messages have deterministic behavior.
- Unauthorized device, cross-facility read, malformed payload, and rate-limit tests pass.
- PostgreSQL, Redis, worker, and external API failure modes are observable and recover safely.
- Prediction output includes units, model version, confidence, input window, and freshness.
- Secrets are not in source, Compose, logs, or error responses.
- Staging replay sustains the expected peak telemetry rate with an agreed latency/error budget.

## Bottom line

Treat the current repository as a **prototype with a partially implemented enrichment branch**, not as an integrated production service. The fastest safe path is to first make the existing synchronous FastAPI/PostgreSQL API coherent and deployable, then integrate Celery against the same models through a tested outbox workflow. Do not expose the current Compose stack or unauthenticated telemetry endpoint to real facilities or devices.
