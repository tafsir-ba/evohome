# Caribbean RE-Connect (Carib)

Unified monorepo for **Caribbean Regional Connectivity** and related tools.

## What's in this repo

| Surface | URL | Code |
|---------|-----|------|
| CRC marketing site | [carib-recon.org](https://carib-recon.org) | `frontend/src/pages/CaribLanding.jsx` |
| Gantt planning tool | [app.carib-recon.org/gantt](https://app.carib-recon.org/gantt) | `frontend/src/pages/tools/` |
| Live vessel map | [app.carib-recon.org/map](https://app.carib-recon.org/map) | `frontend/src/pages/tools/CaribbeanMapPage.js` |
| Evohome CMP | evohome domains | `frontend/src/pages/agent/`, `buyer/` |

Hostname routing: `caribSiteUtils.js`, `ganttHostUtils.js`.

## Deploy

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for DigitalOcean App Platform (`.do/app.yaml` + `.do/app-gantt.yaml`).

## Stack

- **Frontend:** React, Tailwind, shadcn/ui
- **Backend:** FastAPI, MongoDB
- **Hosting:** DigitalOcean App Platform (migrated from Emergent)
