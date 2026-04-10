# Database Isolation Migration Plan

## Current Status: Phase 0 + Phase 1 Implemented

### What Was Done

#### 1. Config-Based Database Selection (Phase 1)

**File: `/app/backend/core/config.py`**

Added environment variables:
- `DB_NAME` - Production database name (e.g., `evohome`)
- `DB_NAME_DEMO` - Demo database name (e.g., `evohome_demo`)
- `DEMO_MODE` - Set to `true` for demo deployment, `false` for production

```python
# In config.py
def get_database_name(self) -> str:
    if self.DEMO_MODE:
        return self.DB_NAME_DEMO
    return self.DB_NAME
```

#### 2. Database Connection at Boot

**File: `/app/backend/server.py`**

Database selection happens once at startup, not per-query:

```python
db_name = app_config.get_database_name()
db = client[db_name]
```

#### 3. Containment Helper Functions (Temporary)

**File: `/app/backend/server.py`**

Added helper functions for backward compatibility during migration:

```python
def get_demo_filter(user: dict) -> dict:
    """Get is_demo filter during migration period."""
    if app_config.DEMO_MODE:
        return {}  # Demo DB - no filter needed
    return {"is_demo": user.get('is_demo', False)}

def build_query(user: dict, **filters) -> dict:
    """Build query with ownership and demo isolation."""
    query = {**filters}
    if user.get('role') == 'agent':
        query['agent_id'] = user['user_id']
    query.update(get_demo_filter(user))
    return query
```

#### 4. Patched Endpoints (Phase 0 Containment)

| Endpoint | Status |
|----------|--------|
| `GET /projects` | ✅ Patched |
| `POST /projects` | ✅ Patched |
| `PUT /projects/{id}` | ✅ Patched |
| `DELETE /projects/{id}` | ✅ Patched |
| `GET /projects/{id}/units` | ✅ Patched |
| `POST /projects/{id}/units` | ✅ Patched |
| `POST /projects/{id}/stages` | ✅ Patched (earlier) |

---

## Deployment Instructions

### Production Deployment

Set these environment variables in DigitalOcean:

```env
MONGO_URL=mongodb+srv://...
DB_NAME=evohome
DB_NAME_DEMO=evohome_demo
DEMO_MODE=false
JWT_SECRET=your-secret
CORS_ORIGINS=https://app.evo-home.ch
```

### Demo Deployment (Separate App)

Create a separate DigitalOcean app for demo, with:

```env
MONGO_URL=mongodb+srv://...
DB_NAME=evohome
DB_NAME_DEMO=evohome_demo
DEMO_MODE=true
JWT_SECRET=your-secret
CORS_ORIGINS=https://demo.evo-home.ch
```

---

## Migration Steps

### Step 1: Create Demo Database

In MongoDB Atlas:
1. The same cluster can host both databases
2. Demo data goes to `evohome_demo`
3. Production data stays in `evohome`

### Step 2: Deploy Production

1. Set `DEMO_MODE=false` in production app
2. Deploy - app uses `evohome` database

### Step 3: Create Demo Deployment

1. Create new DigitalOcean app (or component)
2. Set `DEMO_MODE=true`
3. Deploy - app uses `evohome_demo` database
4. Call `/api/demo/seed` to populate demo data

### Step 4: Cleanup (After Migration Complete)

After demo is fully migrated:
1. Remove `is_demo` field from all queries
2. Remove `get_demo_filter()` helper
3. Remove `is_demo` from data models
4. Simplify query logic

---

## Remaining Work (P1)

### Endpoints Still Needing Patches

These endpoints still use raw `is_demo` checks and need updating:

1. **Clients** (`/clients/*`)
2. **Documents** (`/documents/*`)
3. **Activities** (`/activities/*`)
4. **Timeline** (`/timeline/*`)
5. **Vault** (`/vault/*`)
6. **Notifications** (`/notifications/*`)
7. **Dashboard/Analytics** (`/agent/dashboard`)

### How to Patch

Replace:
```python
is_demo = user.get('is_demo', False)
query = {"agent_id": user['user_id'], "is_demo": is_demo}
```

With:
```python
demo_filter = get_demo_filter(user)
query = {"agent_id": user['user_id'], **demo_filter}
```

---

## Benefits of New Architecture

| Aspect | Before | After |
|--------|--------|-------|
| **Isolation** | Query-level (fragile) | Database-level (robust) |
| **Risk** | Every query must remember filter | Config determines DB at boot |
| **Maintenance** | 400+ queries to maintain | Single config setting |
| **Testing** | Complex (same DB) | Simple (separate DBs) |
| **Security** | Leakage possible | Physical separation |

---

*Migration started: January 2026*
