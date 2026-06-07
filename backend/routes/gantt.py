"""
Gantt Chart Routes — standalone tool (no CMP coupling).
"""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from core.auth import get_current_user
from models.gantt_schemas import (
    ConfirmGanttDraftResponse,
    CreateGanttProjectRequest,
    CreateGanttTaskRequest,
    DeleteGanttProjectResponse,
    ExtractGanttRequest,
    ReorderGanttTasksRequest,
    UpdateGanttDraftRequest,
    UpdateGanttProjectRequest,
    UpdateGanttTaskRequest,
)
from services import gantt_extraction_service, gantt_service
from services.gantt_export_service import build_csv_response
from services.gantt_validation import GanttValidationError, get_gantt_config

logger = logging.getLogger(__name__)
router = APIRouter()


def _handle_validation_error(exc: GanttValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.message)


@router.get("/gantt/config")
async def gantt_config(user=Depends(get_current_user)):
    return get_gantt_config()


@router.post("/gantt/projects")
async def create_project(data: CreateGanttProjectRequest, user=Depends(get_current_user)):
    return await gantt_service.create_project(
        owner_user_id=user["user_id"],
        title=data.title,
        description=data.description,
    )


@router.get("/gantt/projects")
async def list_projects(user=Depends(get_current_user)):
    return await gantt_service.list_projects(owner_user_id=user["user_id"])


@router.get("/gantt/projects/{project_id}")
async def get_project(project_id: str, user=Depends(get_current_user)):
    project = await gantt_service.get_project(project_id, user["user_id"])
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


@router.patch("/gantt/projects/{project_id}")
async def update_project(
    project_id: str,
    data: UpdateGanttProjectRequest,
    user=Depends(get_current_user),
):
    updates = data.model_dump(exclude_unset=True)
    project = await gantt_service.update_project(project_id, user["user_id"], updates)
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


@router.delete("/gantt/projects/{project_id}")
async def delete_project(project_id: str, user=Depends(get_current_user)):
    deleted_count = await gantt_service.delete_project(project_id, user["user_id"])
    if deleted_count is None:
        raise HTTPException(status_code=403, detail="Access denied")
    return DeleteGanttProjectResponse(
        message="Gantt project deleted",
        gantt_project_id=project_id,
        deleted_task_count=deleted_count,
    )


@router.post("/gantt/projects/{project_id}/tasks")
async def create_task(
    project_id: str,
    data: CreateGanttTaskRequest,
    user=Depends(get_current_user),
):
    try:
        return await gantt_service.create_task(
            project_id,
            user["user_id"],
            data.model_dump(exclude_none=True),
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)


@router.get("/gantt/projects/{project_id}/tasks")
async def list_tasks(project_id: str, user=Depends(get_current_user)):
    try:
        return await gantt_service.list_tasks(project_id, user["user_id"])
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


@router.patch("/gantt/projects/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: str,
    task_id: str,
    data: UpdateGanttTaskRequest,
    user=Depends(get_current_user),
):
    try:
        updated = await gantt_service.update_task(
            project_id,
            user["user_id"],
            task_id,
            data.model_dump(exclude_unset=True),
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)

    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/gantt/projects/{project_id}/tasks/{task_id}")
async def delete_task(project_id: str, task_id: str, user=Depends(get_current_user)):
    try:
        result = await gantt_service.delete_task(project_id, user["user_id"], task_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")

    if result == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    if isinstance(result, dict) and result.get("status") == "has_dependents":
        dependent_ids = result.get("dependent_task_ids", [])
        count = len(dependent_ids)
        noun = "task" if count == 1 else "tasks"
        return JSONResponse(
            status_code=409,
            content={
                "detail": f"Cannot delete task: {count} other {noun} depend on it.",
                "dependent_task_ids": dependent_ids,
            },
        )
    return {"message": "Task deleted", "task_id": task_id}


@router.post("/gantt/projects/{project_id}/tasks/reorder")
async def reorder_tasks(
    project_id: str,
    data: ReorderGanttTasksRequest,
    user=Depends(get_current_user),
):
    try:
        return await gantt_service.reorder_tasks(
            project_id,
            user["user_id"],
            data.task_ids,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)


@router.get("/gantt/projects/{project_id}/export.csv")
async def export_csv(project_id: str, user=Depends(get_current_user)):
    project = await gantt_service.get_project(project_id, user["user_id"])
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    tasks = await gantt_service.list_tasks(project_id, user["user_id"])
    content, content_type, disposition = build_csv_response(project, tasks)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": disposition},
    )


# ── Phase 3: Upload, extraction, draft confirm flow ──


@router.post("/gantt/upload")
async def upload_gantt_file(
    gantt_project_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    try:
        content = await file.read()
        return await gantt_extraction_service.upload_file(
            owner_user_id=user["user_id"],
            gantt_project_id=gantt_project_id,
            filename=file.filename or "upload",
            content=content,
            content_type=file.content_type,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)


@router.post("/gantt/extract")
async def extract_gantt_draft(data: ExtractGanttRequest, user=Depends(get_current_user)):
    try:
        return await gantt_extraction_service.extract_draft(
            owner_user_id=user["user_id"],
            file_id=data.file_id,
            gantt_project_id=data.gantt_project_id,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)


@router.get("/gantt/drafts/{draft_id}")
async def get_gantt_draft(draft_id: str, user=Depends(get_current_user)):
    draft = await gantt_extraction_service.get_draft(draft_id, user["user_id"])
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.patch("/gantt/drafts/{draft_id}")
async def update_gantt_draft(
    draft_id: str,
    data: UpdateGanttDraftRequest,
    user=Depends(get_current_user),
):
    try:
        draft = await gantt_extraction_service.update_draft(
            draft_id,
            user["user_id"],
            [t.model_dump() for t in data.tasks],
        )
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post("/gantt/drafts/{draft_id}/confirm")
async def confirm_gantt_draft(draft_id: str, user=Depends(get_current_user)):
    try:
        created, summary = await gantt_extraction_service.confirm_draft(
            draft_id, user["user_id"]
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)

    return ConfirmGanttDraftResponse(
        message="Draft confirmed; tasks created",
        draft_id=summary["draft_id"],
        created_task_count=len(created),
        tasks=created,
    )


@router.post("/gantt/drafts/{draft_id}/discard")
async def discard_gantt_draft(draft_id: str, user=Depends(get_current_user)):
    try:
        result = await gantt_extraction_service.discard_draft(draft_id, user["user_id"])
    except GanttValidationError as exc:
        raise _handle_validation_error(exc)

    if not result:
        raise HTTPException(status_code=404, detail="Draft not found")
    return result
