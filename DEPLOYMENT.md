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

- **Backend build**: Dockerfile installs `gcc` for Python native deps; instance `basic-xs`.
- **Health check**: `/api/` with 60s initial delay (pip install + cold start).
- **Database**: use `DB_NAME=evohome`, not `crc` (minimal Emergent stub used `crc`).
- **Frontend**: `CI=true` + `GENERATE_SOURCEMAP=false` for faster CRA build.

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
