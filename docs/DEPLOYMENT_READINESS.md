# Track D Isolated Deployment Readiness

This is a preparation runbook. It does not authorize deployment and must never
be applied to `alexstudies.com`, its repository, or its database.

## Verified topology

- **Frontend:** a separate Vercel project rooted at `next-app`.
- **Backend:** a separate free Render Docker web service built from the repository root.
- **Database:** a new PostgreSQL database used only by the hackathon instance.
- **Identity boundary:** a fresh session secret and separate hostname. The frontend
  and backend share only this isolated database because the Next.js auth routes and
  Track D API use the same local account/session records.

`render.yaml` and `next-app/vercel.json` are reviewed configuration templates.
They do not create resources or deploy anything. Render auto-deploy is disabled.

## Fresh database bootstrap

The complete migration chain is:

1. `20261013_00` conditionally creates the legacy `localuser`,
   `localauthsession`, `userprofile`, `usermemory`, and `auththrottle` tables.
2. `20261013_01` creates the source knowledge-base tables.
3. `20261013_02` creates the assessment/mastery tables.
4. `20261013_03` adds the source visual-analysis fields.

Run from the repository root with only the isolated database URL loaded:

```bash
python -m alembic upgrade head
python -m alembic current
```

Expected head: `20261013_03`. Backend startup performs the same idempotent
upgrade through `start.sh` when `RUN_DATABASE_MIGRATIONS=true`.

This process was verified against a disposable PostgreSQL database on
`127.0.0.1:55432/alexstudies_hackathon`. A second upgrade was a no-op, seeded
account/profile/session rows remained present, importing the complete Reflex
model registry did not cause duplicate-table errors, and real local HTTP
register, onboarding, and login requests succeeded. The baseline deliberately
does not reshape pre-existing legacy tables; it supplies a deterministic fresh
database path without copying production data.

## Environment variables

Backend service:

- `DATABASE_URL` — isolated hosted PostgreSQL URL
- `DATABASE_SSL_MODE=require`
- `RUN_DATABASE_MIGRATIONS=true`
- `SESSION_SECRET` — fresh generated value
- `APP_BASE_URL` — separate Vercel origin
- `REFLEX_API_URL` — public isolated backend origin
- `PRODUCTION=true`
- `ENFORCE_HTTPS=true`
- `ALEX_DEMO_FREE_MODE=true`
- `ALEX_TEXT_PROVIDER=groq`
- `GROQ_API_KEY` — separate development/hackathon key
- `GROQ_BASE_URL=https://api.groq.com/openai/v1`
- `GROQ_TEXT_MODEL=openai/gpt-oss-20b`
- `GROQ_STT_MODEL=whisper-large-v3-turbo`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` only if
  isolated-host Google sign-in is intentionally enabled
- `SUPADATA_API_KEY` only if its optional caption fallback is intentionally enabled

Next.js service:

- `DATABASE_URL` — the same isolated database
- `DATABASE_SSL_MODE=require`
- `REFLEX_BACKEND_URL` — isolated Render origin
- Google OAuth values only if that path is enabled

Provider secrets remain server-side and must never use a `NEXT_PUBLIC_` prefix.

## Exact deployment procedure after approval

1. Create a separate free PostgreSQL database. Neon is the preferred long-lived
   demo option; a Render free PostgreSQL database expires after 30 days.
2. Save the isolated connection string privately on both services with
   `DATABASE_SSL_MODE=require`.
3. In Render, create a Blueprint from this repository, inspect the proposed
   `alexstudies-track-d-api` free service, and provide the `sync: false` values.
   Keep auto-deploy disabled.
4. Wait for the Docker health check at `/health`. Startup applies migrations;
   verify logs reach Alembic head without printing the database URL.
5. Create a separate Vercel Hobby project with root directory `next-app`.
   Configure the isolated database and backend URL, then deploy.
6. Register a disposable account, complete onboarding, and verify owner-isolated
   PDF, PPTX, and YouTube ingestion plus tutor/refusal/adaptive flows.

## Commands and compatibility

- Backend build: root `Dockerfile`; startup: `./start.sh`.
- Frontend install/build: `npm ci && npm run build` from `next-app`.
- PostgreSQL 15+ is required because retrieval uses PostgreSQL full-text search.
- Linux hosting needs Tesseract for OCR. If no supported local OCR engine exists,
  the visual result is recorded as unavailable rather than invented.

## Expected costs and free-tier constraints

- Vercel Hobby has no subscription charge for eligible personal/non-commercial
  use, but it has usage and function-duration limits.
- Render's free web service has no instance charge, sleeps after inactivity, and
  can introduce a cold-start delay. The workspace receives a finite monthly pool.
- Render free PostgreSQL is unsuitable for a lasting public demo because it
  expires after 30 days and has no backups. A separate Neon free project avoids
  that expiry but still has storage and compute limits.
- Groq is configured without paid-provider fallback. Free-tier rate limits and
  event-day availability are external constraints and must be checked before the demo.

No paid resource is required by this topology. Do not attach a payment method or
upgrade a plan as part of the deployment workflow.

## Remaining risks

- Render cold starts can make the first request slow.
- Groq quota or provider downtime can block live generation; deterministic
  assessment logic still works, but provider failures must be reported honestly.
- YouTube may reject transcript requests from hosting-provider IP ranges.
- The Next proxy uses a 120-second ingestion window; large files remain a poor demo choice.
- PDF/PPTX image bytes consume database storage; use the small generated fixtures.
- Browser/OAuth callback origins must exactly match the new hosts.

## Deployment gate

Before any public deployment, require all of the following:

1. full local test/build matrix passes;
2. disposable database migration reaches `20261013_03` twice without data loss;
3. local register/login/onboarding succeeds against that database;
4. the planned service/database names are visibly separate from production;
5. secrets exist only in the hosting dashboards;
6. the user gives explicit approval to create external resources.
