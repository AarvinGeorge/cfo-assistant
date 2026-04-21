"""
workspaces.py

FastAPI router for workspace CRUD — create, list, partial update.

Role in project:
    HTTP layer for workspace management. Called by the frontend
    WorkspaceSwitcher component. Every route goes through the
    RequestContext dependency so the caller is identified (v1:
    hardcoded usr_default).

Main parts:
    - POST /workspaces/: create a workspace owned by the requesting user.
    - GET /workspaces/: list workspaces the user owns (non-archived).
    - PATCH /workspaces/{id}: update name / description / status.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.context import RequestContext, get_request_context
from backend.db.engine import get_session_factory
from backend.db.models import Workspace, WorkspaceMember


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(..., description="User-given workspace name")
    description: Optional[str] = Field(None, description="Optional description")


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # "active" | "archived"


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


def _new_workspace_id() -> str:
    return f"wks_{uuid.uuid4().hex[:8]}"


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceResponse:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="Workspace name must be 80 characters or less")

    description = (payload.description or "").strip() or None
    if description and len(description) > 500:
        raise HTTPException(status_code=400, detail="Description must be 500 characters or less")

    SessionLocal = get_session_factory()
    workspace_id = _new_workspace_id()
    with SessionLocal() as session:
        w = Workspace(
            id=workspace_id,
            owner_id=ctx.user_id,
            name=name,
            description=description,
            status="active",
        )
        m = WorkspaceMember(workspace_id=workspace_id, user_id=ctx.user_id, role="owner")
        session.add_all([w, m])
        session.commit()
        session.refresh(w)
        return WorkspaceResponse(
            id=w.id, name=w.name, description=w.description,
            status=w.status, created_at=w.created_at, updated_at=w.updated_at,
        )


@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(
    ctx: RequestContext = Depends(get_request_context),
) -> list[WorkspaceResponse]:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        rows = session.execute(
            select(Workspace)
            .where(Workspace.owner_id == ctx.user_id)
            .where(Workspace.status != "archived")
            .order_by(Workspace.created_at.asc())
        ).scalars().all()
        return [
            WorkspaceResponse(
                id=w.id, name=w.name, description=w.description,
                status=w.status, created_at=w.created_at, updated_at=w.updated_at,
            )
            for w in rows
        ]


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceResponse:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        w = session.execute(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .where(Workspace.owner_id == ctx.user_id)
        ).scalar_one_or_none()
        if w is None:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="Workspace name cannot be empty")
            if len(name) > 80:
                raise HTTPException(status_code=400, detail="Workspace name must be 80 characters or less")
            w.name = name

        if payload.description is not None:
            desc = payload.description.strip() or None
            if desc and len(desc) > 500:
                raise HTTPException(status_code=400, detail="Description must be 500 characters or less")
            w.description = desc

        if payload.status is not None:
            if payload.status not in ("active", "archived"):
                raise HTTPException(status_code=400, detail="status must be 'active' or 'archived'")
            w.status = payload.status

        w.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(w)
        return WorkspaceResponse(
            id=w.id, name=w.name, description=w.description,
            status=w.status, created_at=w.created_at, updated_at=w.updated_at,
        )
