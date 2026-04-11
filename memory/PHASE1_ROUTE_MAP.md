# Phase 1 Route Map — Old to New

## Project Routes

| Old Route (projects.py) | New Route (projects_v2.py) | Change |
|---|---|---|
| `GET /projects` | `GET /projects` | Thin route via `project_service.list_projects_by_agent` / `list_projects_for_buyer` |
| `POST /projects` | `POST /projects` | Thin route via `project_service.create_project`, subscription check via `billing_service` |
| `PUT /projects/{id}` | `PUT /projects/{id}` | Thin route via `project_service.update_project`, access via `can_access_project` |
| `DELETE /projects/{id}` | `DELETE /projects/{id}` | Thin route via `project_service.delete_project`, client guard |
| `GET /projects/{id}/team` | **STAYS** in projects.py | Not Phase 1 scope |
| `POST /projects/{id}/team` | **STAYS** in projects.py | Not Phase 1 scope |
| `PUT /projects/{id}/team/{mid}` | **STAYS** in projects.py | Not Phase 1 scope |
| `DELETE /projects/{id}/team/{mid}` | **STAYS** in projects.py | Not Phase 1 scope |
| `GET /team/directory` | **STAYS** in projects.py | Not Phase 1 scope |
| `POST /team/extract-contacts` | **STAYS** in projects.py | Not Phase 1 scope |
| `POST /projects/{id}/team/bulk` | **STAYS** in projects.py | Not Phase 1 scope |

## Timeline Routes

| Old Route (timelines.py) | New Route (timelines_v2.py) | Change |
|---|---|---|
| `POST /timeline/create` | `POST /timeline/create` | Canonical via `timeline_service.create_timeline_with_steps` |
| `GET /project-timeline` | `GET /project-timeline` | Canonical via `timeline_service.get_enriched_timeline` |
| `DELETE /timeline/{id}` | `DELETE /timeline/{id}` | Cascade via `timeline_service.delete_timeline_cascade` |
| `PATCH /timeline/steps/{id}` | `PATCH /timeline/steps/{id}` | Via `step_service.update_step` |
| `POST /timeline/{id}/steps` | `POST /timeline/{id}/steps` | Via `step_service.add_step_to_timeline` |
| `DELETE /timeline/steps/{id}` | `DELETE /timeline/steps/{id}` | Via `step_service.delete_step` |
| `POST /timeline/steps/{id}/documents` | `POST /timeline/steps/{id}/documents` | Via `step_service.link_document` |
| `DELETE /timeline/steps/{id}/documents/{aid}` | `DELETE /timeline/steps/{id}/documents/{aid}` | Via `step_service.unlink_document` |
| `POST /timeline/steps/{id}/notes` | `POST /timeline/steps/{id}/notes` | Via `step_service.add_note` |
| `GET /timeline/templates` | `GET /timeline/templates` | Via `timeline_service.list_templates` |
| `POST /timeline/templates` | `POST /timeline/templates` | Via `timeline_service.create_template` |
| `DELETE /timeline/templates/{id}` | `DELETE /timeline/templates/{id}` | Via `timeline_service.delete_template` |
| `POST /timeline/templates/{id}/apply` | `POST /timeline/templates/{id}/apply` | Via `timeline_service.apply_template` |

## Intentionally Removed Endpoints

| Removed Route | Reason |
|---|---|
| `POST /timeline/extract` | AI timeline extraction killed per user directive |
| `GET /timeline/extractions` | AI timeline extraction killed |
| `GET /timeline/extractions/{id}` | AI timeline extraction killed |
| `POST /timeline/extractions/{id}/approve` | AI timeline extraction killed |
| `DELETE /timeline/extractions/{id}` | AI timeline extraction killed |

## Endpoint Parity Check

- All project CRUD endpoints: **PARITY MAINTAINED**
- All team endpoints: **UNCHANGED** (stay in projects.py)
- All timeline CRUD endpoints: **PARITY MAINTAINED**
- All step management endpoints: **PARITY MAINTAINED**
- All template endpoints: **PARITY MAINTAINED**
- Timeline extraction: **INTENTIONALLY REMOVED**

## Behavioral Changes

1. **No `is_demo` in queries** — All Phase 1 services use `agent_id`/`project_id` ownership
2. **No `is_demo` in responses** — Excluded via MongoDB projection `{"is_demo": 0}`
3. **No `is_demo` in new documents** — Services don't write it
4. **Subscription checks** — Always enforced (no demo skip)
5. **Access control** — Via canonical `can_access_project` (no `is_demo` branching)
