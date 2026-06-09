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

## Database migration (Emergent / legacy → DigitalOcean)

squid-app expects **`DB_NAME=evohome`** on the **`MONGO_URL`** secret. The old Carib stub used `crc` (near-empty). Gantt projects, tasks, and login users live in **`evohome`**.

### What to copy (CRC site)

| Collection | Purpose |
|------------|---------|
| `users` | Login accounts (invite allowlist users) |
| `gantt_projects` | Planning charts |
| `gantt_tasks` | Tasks / phases |
| `gantt_audit_logs` | Audit trail |
| `gantt_extraction_drafts` | Import drafts |
| `gantt_uploaded_files` | Upload metadata |

### Option A — Python script (no mongodump required)

From repo root, with connection strings from **Emergent** (Save to GitHub source env) and **Atlas / DO MongoDB** (squid-app `MONGO_URL`):

```bash
export SOURCE_MONGO_URL='mongodb+srv://...'   # Emergent or legacy cluster
export SOURCE_DB_NAME='evohome'
export TARGET_MONGO_URL='mongodb+srv://...'   # same as squid-app MONGO_URL
export TARGET_DB_NAME='evohome'
export CONFIRM_TARGET='yes'

# Preview counts
python3 backend/scripts/migrate_mongo.py --profile crc --dry-run

# Copy (drops target collections first)
python3 backend/scripts/migrate_mongo.py --profile crc --drop-target
```

`--profile full` copies every collection (only if you need full Evohome CMP data on the same cluster).

### Option B — mongodump / mongorestore (full database)

```bash
export SOURCE_MONGO_URL='...' SOURCE_DB_NAME='evohome'
export TARGET_MONGO_URL='...' TARGET_DB_NAME='evohome'
export CONFIRM_TARGET='yes'
chmod +x scripts/mongo_migrate.sh
./scripts/mongo_migrate.sh
```

### After migration

1. In DO → squid-app → **carib-backend** → confirm `DB_NAME=evohome` (not `crc`).
2. **Redeploy** the backend component.
3. Test `https://carib-recon.org/login` and open an existing Gantt project.

### Where to find URLs

| Source | Where |
|--------|--------|
| Emergent (old) | Emergent project → Environment → `MONGO_URL`, `DB_NAME` |
| Legacy DO `crc` | Usually empty; skip unless you stored data there |
| Target (DO) | DO → squid-app → Settings → `MONGO_URL` secret |

**Never commit connection strings to git.**

---

## DigitalOcean (squid-app)

1. **Settings → App** → GitHub: `tafsir-ba/Carib`, branch `main`, deploy on push.
2. **Secrets** → set `MONGO_URL` (MongoDB Atlas connection string).
3. **Build env** (frontend component) — should match [`.do/app.yaml`](.do/app.yaml):
   - `REACT_APP_CRC_SITE=true`
   - `REACT_APP_BACKEND_URL=` (empty = same-origin `/api`)
4. **Runtime env** (backend):
   - `DB_NAME=evohome` (Gantt data database)
   - `FRONTEND_URL=https://carib-recon.org`
   - `GANTT_REGISTRATION_CLOSED=true`
5. **Domain**: `carib-recon.org` (+ optional `www`)
6. Redeploy after env changes.

## If deploy failed

Common fixes (already in this repo):

- **Frontend `no such file ... frontend/Dockerfile`**: In DO → carib-frontend → set **Dockerfile path** to `Dockerfile` (not `frontend/Dockerfile`) because **Source directory** is already `frontend/`. The file lives at `frontend/Dockerfile` in git.
- **Backend build**: Dockerfile installs `gcc` for Python native deps; instance `basic-xs`.
- **Health check**: `/api/` with 60s initial delay (pip install + cold start).
- **Database**: use `DB_NAME=evohome`, not `crc` (minimal Emergent stub used `crc`).
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
