# Caribbean RE-Connect — unified deployment (DigitalOcean)

Single GitHub repo **`tafsir-ba/Carib`** hosts:

| Host | Purpose |
|------|---------|
| `carib-recon.org` | CRC marketing site |
| `app.carib-recon.org` | Gantt tool, auth, `/map` (MarineTraffic embed) |
| `app.evo-home.ch` | Evohome CMP (optional; legacy redirects to Gantt) |

The **same React build** uses hostname routing (`caribSiteUtils`, `ganttHostUtils`) to show the right UI.

## Architecture

```
tafsir-ba/Carib (monorepo)
├── frontend/     React — marketing + Gantt + Evohome CMP
├── backend/      FastAPI — shared API (Gantt, auth, CMP, …)
└── .do/
    ├── app.yaml        → DO app for carib-recon.org
    └── app-gantt.yaml  → DO app for app.carib-recon.org
```

## Prerequisites

1. **MongoDB Atlas** (or DO Managed MongoDB) — two databases recommended:
   - `crc` — marketing / light use (optional)
   - `evohome` — Gantt + CMP data
2. **GitHub** repo connected to DigitalOcean App Platform.
3. **Domains** DNS pointed at each DO app (or one app with multiple domains).

## Deploy marketing (`carib-recon.org`)

Uses [`.do/app.yaml`](.do/app.yaml) — matches your **squid-app** on DO.

1. DO → Apps → **squid-app** → Settings → confirm GitHub repo is **`tafsir-ba/Carib`**, branch **`main`**, deploy on push.
2. Ensure build env vars:
   - `REACT_APP_BACKEND_URL=""` (same-origin `/api`)
   - `REACT_APP_LOGIN_URL=https://app.carib-recon.org/login`
3. Runtime secret: **`MONGO_URL`**
4. Domain: `carib-recon.org` (+ `www`)

## Deploy Gantt app (`app.carib-recon.org`)

Uses [`.do/app-gantt.yaml`](.do/app-gantt.yaml).

1. Create or update the **app.carib-recon.org** DO app to use **`tafsir-ba/Carib`** (was `tafsir-ba/evohome`).
2. Set `DB_NAME=evohome` and the same `MONGO_URL` (or a dedicated cluster).
3. Build env: `REACT_APP_GANTT_HOSTS=app.carib-recon.org`
4. Attach domain `app.carib-recon.org`

## After merging from Emergent / evohome

- [ ] Point **both** DO apps at `tafsir-ba/Carib` (not `evohome`).
- [ ] Redeploy both apps.
- [ ] Verify `https://carib-recon.org` → marketing landing.
- [ ] Verify `https://app.carib-recon.org/gantt` → Gantt tool.
- [ ] Verify `https://app.carib-recon.org/map` → vessel map embed.
- [ ] Login on marketing navbar → `app.carib-recon.org/login`.

## Local development

```bash
# Marketing UI
REACT_APP_CARIB_MARKETING_HOSTS=localhost yarn --cwd frontend start
# Open http://localhost:3000 (add hosts file entry or use env override)

# Gantt UI
REACT_APP_GANTT_HOSTS=localhost yarn --cwd frontend start
```

Backend: `uvicorn server:app --reload --port 8001` from `backend/` with `.env` set.

## Docker (optional)

See [`docker-compose.yml`](docker-compose.yml) for a single-server setup.
