# Phase 2 Route Map — Old to New

## Activity Routes

| Old (activities.py) | New (activities_v2.py) | Change |
|---|---|---|
| `POST /activities` | `POST /activities` | Thin route, delegates to `activity_service.create_and_distribute_activity` |
| `GET /activities` | `GET /activities` | Thin route, delegates to `activity_service.list_activities` |
| `POST /activities/mark-seen` | `POST /activities/mark-seen` | Thin route, delegates to `activity_service.mark_seen` |
| `GET /activities/unread-count` | `GET /activities/unread-count` | Thin route, delegates to `activity_service.get_unread_count` |
| `GET /activities/files/*` | `GET /activities/files/*` | File serving (stays in route) |
| `GET /activities/{id}` | `GET /activities/{id}` | Thin route, delegates to `activity_service.get_activity_detail` |
| `POST /activities/{id}/send` | `POST /activities/{id}/send` | Thin route, delegates to `activity_service.send_draft_activity` |
| `POST /activities/{id}/reply` | `POST /activities/{id}/reply` | Thin route, delegates to `activity_service.create_reply` |
| `POST /activities/{id}/request-change` | `POST /activities/{id}/request-change` | Thin route, delegates to `activity_service.request_change` |
| `DELETE /activities/{id}` | `DELETE /activities/{id}` | Thin route, delegates to `activity_service.delete_activity` |
| `PUT /activities/{id}` | `PUT /activities/{id}` | Thin route, delegates to `activity_service.update_activity` |

## Document Routes

| Old (documents.py) | New (documents_v2.py) | Change |
|---|---|---|
| `POST /documents/upload` | `POST /documents/upload` | AI extraction is assistive only |
| `POST /documents/create` | `POST /documents/create` | Via `document_service.create_document` |
| `GET /documents` | `GET /documents` | Via `document_service.list_documents` |
| `GET /documents/{id}` | `GET /documents/{id}` | Via `document_service.get_document` |
| `PUT /documents/{id}` | `PUT /documents/{id}` | Via `document_service.update_document` |
| `DELETE /documents/{id}` | `DELETE /documents/{id}` | Via `document_service.delete_document` |
| `POST /documents/{id}/send` | `POST /documents/{id}/send` | Via `document_service.send_document` |
| `POST /documents/{id}/action` | `POST /documents/{id}/action` | Via `document_service.document_action` |
| `POST /documents/{id}/reupload` | `POST /documents/{id}/reupload` | Via `document_service.reupload_document` |
| `POST /documents/{id}/revert-to-draft` | `POST /documents/{id}/revert-to-draft` | Via `document_service.revert_to_draft` |
| `GET /documents/{id}/source-pdf` | `GET /documents/{id}/source-pdf` | File serving (route) |
| `POST /documents/{id}/hero-image` | `POST /documents/{id}/hero-image` | File I/O (route) |
| `GET /documents/{id}/hero-image` | `GET /documents/{id}/hero-image` | File serving (route) |
| `DELETE /documents/{id}/hero-image` | `DELETE /documents/{id}/hero-image` | File I/O (route) |
| `GET /documents/{id}/qr-code` | `GET /documents/{id}/qr-code` | Utility (route) |
| `GET /documents/{id}/pdf` | `GET /documents/{id}/pdf` | Utility (route) |
| `GET /timeline` | `GET /timeline` | Via `document_service.get_document_timeline` |

## VaultDocument Routes

| Old (vault.py) | New (vault_v2.py) | Change |
|---|---|---|
| `POST /vault/upload` | `POST /vault/upload` | Via `vault_service.create_vault_document` |
| `GET /vault/documents` | `GET /vault/documents` | Via `vault_service.list_vault_documents` |
| `GET /vault/categories` | `GET /vault/categories` | Via `vault_service.get_categories` |
| `GET /vault/documents/{id}` | `GET /vault/documents/{id}` | Via `vault_service.get_vault_document` |
| `PUT /vault/documents/{id}` | `PUT /vault/documents/{id}` | Via `vault_service.update_vault_document` |
| `DELETE /vault/documents/{id}` | `DELETE /vault/documents/{id}` | Via `vault_service.delete_vault_document` |
| `GET /vault/documents/{id}/download` | `GET /vault/documents/{id}/download` | File serving (route) |

## Notification Routes

| Old (notifications.py) | New (notifications_v2.py) | Change |
|---|---|---|
| `GET /notifications` | `GET /notifications` | Via `notification_service.list_notifications` |
| `PATCH /notifications/{id}/read` | `PATCH /notifications/{id}/read` | Via `notification_service.mark_read` |
| `PATCH /notifications/read-all` | `PATCH /notifications/read-all` | Via `notification_service.mark_all_read` |

## Removed

| Removed Route | Reason |
|---|---|
| `GET /timeline` from `timeline_view.py` | Replaced by `documents_v2.py` |

## Notification Bridge

`/app/backend/services/notification_bridge.py` wraps legacy `create_notification(is_demo=False)`.
To be removed when Notification module bridge cleanup is done.
