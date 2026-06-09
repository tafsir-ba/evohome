# Caribbean RE-Connect — single-site deployment

**One repo** (`tafsir-ba/Carib`) · **one DO app** (`squid-app`) · **one domain** (`carib-recon.org`)

## Routes (same origin)

| URL | Page |
|-----|------|
| `/` | Marketing landing |
| `/login` | Sign in (invite-only) |
| `/gantt` | Planning tool |
| `/map` | Live vessel map (MarineTraffic embed) |

API: `https://carib-recon.org/api/...`

## Database migration (evohome → crc)

squid-app uses **`DB_NAME=crc`** on the **`MONGO_URL`** secret. **`crc`** is the live database (existing Carib data). Gantt projects, tasks, and users from Emergent / legacy live in **`evohome`** on the same cluster — copy them **into** `crc` without wiping what is already there.

**You do not need a Droplet or SSH.** App Platform only runs your containers; MongoDB is a separate managed database. Either trigger migration **through the live backend** (below) or run the Python script **on your Mac** with the same `MONGO_URL` from DO settings.

### Migrate via App Platform (recommended)

The backend already connects to MongoDB from inside DigitalOcean’s network.

1. Deploy the latest `main` (includes `/api/internal/migrate-evohome-to-crc`).
2. In DO → squid-app → **carib-backend** → **Environment variables**, add:
   - `MIGRATION_SECRET` = a long random string (e.g. `openssl rand -hex 32`)
3. **Redeploy** the backend so the secret is loaded.
4. **Dry run** (counts only — safe):

```bash
curl -s "https://carib-recon.org/api/internal/migrate-evohome-to-crc?dry_run=true" \
  -H "X-Migration-Secret: YOUR_SECRET_HERE" | python3 -m json.tool
```

5. **Merge** evohome → crc (keeps existing crc rows):

```bash
curl -s -X POST "https://carib-recon.org/api/internal/migrate-evohome-to-crc?dry_run=false" \
  -H "X-Migration-Secret: YOUR_SECRET_HERE" | python3 -m json.tool
```

6. **Remove** `MIGRATION_SECRET` from env and redeploy (disables the endpoint).
7. Confirm `DB_NAME=crc`, then test `/login` and `/gantt`.

Optional: `MIGRATION_SOURCE_DB=evohome` (default if unset). Target is always `DB_NAME` (`crc`). **Never** use `drop_target=true` if crc already has data you need.

### What to copy (CRC site)

| Collection | Purpose |
|------------|---------|
| `users` | Login accounts (invite allowlist users) |
| `gantt_projects` | Planning charts |
| `gantt_tasks` | Tasks / phases |
| `gantt_audit_logs` | Audit trail |
| `gantt_extraction_drafts` | Import drafts |
| `gantt_uploaded_files` | Upload metadata |

### Option A — merge evohome → crc from your Mac (optional)

Same cluster as squid-app (`MONGO_URL`). **Do not** use `--drop-target` — that would erase existing `crc` data.

```bash
export MONGO_URL='mongodb+srv://...'   # squid-app secret
export SOURCE_MONGO_URL="$MONGO_URL"
export TARGET_MONGO_URL="$MONGO_URL"
export SOURCE_DB_NAME='evohome'
export TARGET_DB_NAME='crc'

# Preview counts
python3 backend/scripts/migrate_mongo.py --profile crc --dry-run

# Merge (skips rows already in crc by user_id / project_id / task_id)
export CONFIRM_TARGET='yes'
python3 backend/scripts/migrate_mongo.py --profile crc
```

Or use the helper (dry run + confirmation prompt):

```bash
export MONGO_URL='mongodb+srv://...'
./scripts/migrate_evohome_to_crc.sh
```

If source and target are on **different** clusters, set `SOURCE_MONGO_URL` and `TARGET_MONGO_URL` separately.

`--profile full` copies every collection (only if you need full Evohome CMP data in `crc`).

### Option B — mongodump / mongorestore (full database)

```bash
export SOURCE_MONGO_URL='...' SOURCE_DB_NAME='evohome'
export TARGET_MONGO_URL='...' TARGET_DB_NAME='crc'
export CONFIRM_TARGET='yes'
chmod +x scripts/mongo_migrate.sh
./scripts/mongo_migrate.sh
```

### After migration

1. In DO → squid-app → **carib-backend** → confirm `DB_NAME=crc`.
2. Remove unused `DB_NAME2` if present (the app only reads `DB_NAME`).
3. **Redeploy** the backend component.
4. Test `https://carib-recon.org/login` and open Gantt projects from both sources.

### Where to find URLs

| Database | Where |
|----------|--------|
| `evohome` (source) | Same `MONGO_URL` cluster; legacy Emergent data |
| `crc` (target) | Same `MONGO_URL` cluster; live Carib app data |
| Connection string | DO → squid-app → Settings → `MONGO_URL` secret |

**Never commit connection strings to git.**

---

## DigitalOcean (squid-app)

1. **Settings → App** → GitHub: `tafsir-ba/Carib`, branch `main`, deploy on push.
2. **Secrets** → set `MONGO_URL` (MongoDB Atlas connection string).
3. **Build env** (frontend component) — should match [`.do/app.yaml`](.do/app.yaml):
   - `REACT_APP_CRC_SITE=true`
   - `REACT_APP_BACKEND_URL=` (empty = same-origin `/api`)
4. **Runtime env** (backend):
   - `DB_NAME=crc` (live database after evohome → crc merge)
   - `FRONTEND_URL=https://carib-recon.org`
   - `GANTT_REGISTRATION_CLOSED=true`
5. **Domain**: `carib-recon.org` (+ optional `www`)
6. Redeploy after env changes.

## If deploy failed

Common fixes (already in this repo):

- **Frontend `no such file ... frontend/Dockerfile`**: In DO → carib-frontend → set **Dockerfile path** to `Dockerfile` (not `frontend/Dockerfile`) because **Source directory** is already `frontend/`. The file lives at `frontend/Dockerfile` in git.
- **Backend build**: Dockerfile installs `gcc` for Python native deps; instance `basic-xs`.
- **Health check**: `/api/` with 60s initial delay (pip install + cold start).
- **Database**: use `DB_NAME=crc`. Run evohome → crc migration if Gantt data is still only in `evohome`.
- **Frontend build**: `CI=true` + `GENERATE_SOURCEMAP=false` for faster CRA build.

Check **Activity → failed deployment → Build logs** in DO for the exact error.

## Local dev

```bash
# Terminal 1 — backend
cd backend && uvicorn server:app --reload --port 8001

# Terminal 2 — frontend as CRC site
cd frontend
REACT_APP_CRC_SITE=true REACT_APP_BACKEND_URL=http://localhost:8001 yarn start
```

Open http://localhost:3000 → marketing · http://localhost:3000/login · /gantt · /map

## Legacy

`app.carib-recon.org` is no longer used. Remove that subdomain from DNS or redirect it to `https://carib-recon.org` in Cloudflare.
