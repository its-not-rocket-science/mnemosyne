# Mnemosyne — Deployment checklist

Work through every item before exposing the server to real traffic.  Items
marked **[HARD FAIL]** cause an immediate startup error if missed; others are
warnings that log to the console and will create security or reliability gaps
in production.

---

## 1 — Environment variables

Copy `.env.example` to `.env` and change every placeholder value.

### Security-critical (server will not start safely with defaults)

| Variable | Requirement | Default risk |
|---|---|---|
| `DEBUG` | Set to `false` | `true` logs verbose output and allows wildcard CORS |
| `CORS_ORIGINS` | JSON array of exact allowed origins, e.g. `["https://app.example.com"]` | **[HARD FAIL]** — server refuses to start when `DEBUG=false` and value is `["*"]` |
| `JWT_SECRET` | Minimum 32 random bytes — run `python -c "import secrets; print(secrets.token_hex(32))"` | **[WARN]** logged on startup; tokens are trivially forgeable |
| `DATABASE_URL` | Strong password; never `changeme` | **[WARN]** logged on startup |
| `POSTGRES_PASSWORD` | Match `DATABASE_URL`; used by Docker Compose to initialise the database | Same as above |

### Recommended

| Variable | Notes |
|---|---|
| `SENTRY_DSN` | Set to your Sentry project DSN to enable error monitoring. Leave empty to disable. |
| `SENTRY_ENVIRONMENT` | Defaults to `"development"` / `"production"` from `DEBUG`. Set `"staging"` if you run a staging environment. |
| `RATE_LIMIT_PARSE` | Default `20/minute` per user/IP. Raise for trusted clients; lower if you see abuse. |
| `ENABLED_LANGUAGES` | Comma-separated BCP-47 codes. Omit to load all plugins. Set explicitly to reduce cold-start time and memory in single-language deployments. |

---

## 2 — Database

### Run migrations before starting the server

```bash
alembic upgrade head
```

The app will run `alembic upgrade head` automatically on startup, but running
it manually first gives you a chance to inspect the plan and take a backup.

### Existing databases bootstrapped before alembic was introduced

If the database was created with `Base.metadata.create_all()` (pre-alembic),
it has no `alembic_version` table and all migrations appear un-applied.
Stamp the current state as the head revision before running `upgrade head`:

```bash
alembic stamp head
```

This records the current revision without executing any migrations.
Future schema changes will be applied normally from that point forward.

### Take a backup before migrating

```bash
pg_dump -Fc mnemosyne > mnemosyne_$(date +%Y%m%d_%H%M%S).dump
```

---

## 3 — CORS

`CORS_ORIGINS` must list every origin that your frontend is served from — no
wildcards allowed when `DEBUG=false`.

```dotenv
# Single origin:
CORS_ORIGINS=["https://app.example.com"]

# Multiple origins (e.g. www and non-www):
CORS_ORIGINS=["https://app.example.com","https://www.app.example.com"]
```

The `Settings` validator rejects `["*"]` at startup when `DEBUG=false`, so a
misconfigured server simply won't start — preventing silent credential leaks
via CORS.

---

## 4 — HTTPS

The app does not handle TLS itself.  Terminate TLS at your reverse proxy
(nginx, Caddy, AWS ALB, …) and proxy plain HTTP to the app.

Ensure:
- All HTTP traffic redirects to HTTPS (301).
- `Strict-Transport-Security` header is set by the proxy.
- The `CORS_ORIGINS` values use `https://` scheme.

---

## 5 — Rate limiting (multi-worker deployments)

The default in-memory rate-limit storage is **per-process**.  With more than
one Uvicorn worker each worker has its own counter, so the effective limit is
`RATE_LIMIT_PARSE × number_of_workers`.

To share counters across workers, configure Redis as the storage backend by
passing `storage_uri` to the `Limiter` constructor in
`backend/core/limiter.py`:

```python
# backend/core/limiter.py
import os
limiter = Limiter(
    key_func=_user_or_ip_key,
    storage_uri=os.environ.get("SLOWAPI_STORAGE_URI", "memory://"),
)
```

Then set `SLOWAPI_STORAGE_URI=redis://redis:6379/1` in `.env` (use database 1
to keep rate-limit keys separate from the parse cache in database 0).

---

## 6 — Redis availability

The parse cache and (optionally) the rate-limit store both use Redis.  The
app degrades gracefully when Redis is unavailable: cache misses are transparent
and rate limits fall back to in-memory.  In production:

- Monitor Redis memory usage — the cache uses a 1-hour TTL and will fill up
  given long texts.
- Set `maxmemory` and `maxmemory-policy allkeys-lru` in `redis.conf` to
  prevent OOM evictions from crashing Redis.

---

## 7 — Pre-launch smoke test

After deploying, verify:

```bash
# Liveness
curl https://app.example.com/health

# Readiness (plugins loaded, DB reachable)
curl https://app.example.com/ready

# CORS preflight — should return only the expected origin, not *
curl -sI -X OPTIONS https://app.example.com/parse \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  | grep -i "access-control-allow-origin"

# JWT round-trip
TOKEN=$(curl -s -X POST https://app.example.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}' \
  | jq -r .access_token)
curl -s https://app.example.com/dashboard \
  -H "Authorization: Bearer $TOKEN" | jq .total_objects
```

---

## 8 — Post-deploy monitoring checklist

- [ ] Sentry receiving events (send a test error).
- [ ] Request-ID appears in log lines (`[a1b2c3d4]` prefix).
- [ ] `GET /ready` returns `{"status":"ok","plugins":"ok"}`.
- [ ] HTTPS redirect is active.
- [ ] Database backup schedule is running.
- [ ] Redis memory limit is configured.
