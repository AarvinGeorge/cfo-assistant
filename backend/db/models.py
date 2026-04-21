"""
models.py

SQLAlchemy ORM model definitions for the FinSight control plane.

Role in project:
    Infrastructure layer. Defines the relational schema mirrored in the
    Alembic migration in backend/db/migrations/versions/. These classes
    are the single source of truth for table structure, foreign keys,
    indexes, and cascade behavior.

Main parts:
    - Base: declarative base shared by all models.
    - User: a person who can log in (v1: just one row, "usr_default").
    - Workspace: a labeled container owned by a user (e.g. "Acme Corp").
    - WorkspaceMember: workspace_id <-> user_id with a role (owner|editor|viewer).
    - Document: a registered uploaded file inside a workspace.
    - ChatSession: a single conversation thread inside a workspace.
    - WorkspaceKpiCache: 24-hour SQLite cache for the 6 KPI dashboard values,
      keyed by (workspace_id, kpi_key). Invalidated on document upload/delete.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    members = relationship(
        "WorkspaceMember", cascade="all, delete-orphan", backref="workspace"
    )
    documents = relationship(
        "Document", cascade="all, delete-orphan", backref="workspace"
    )
    chat_sessions = relationship(
        "ChatSession", cascade="all, delete-orphan", backref="workspace"
    )


Index("idx_workspaces_owner_status", Workspace.owner_id, Workspace.status)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False, default="owner")
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String, nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="indexed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "file_hash", name="idx_workspace_file_hash"),
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


Index(
    "idx_chat_sessions_workspace_recent",
    ChatSession.workspace_id, ChatSession.last_message_at.desc(),
)


class WorkspaceKpiCache(Base):
    """24-hour cache for the 6 KPI dashboard values per workspace.

    Composite primary key (workspace_id, kpi_key) ensures at most one row
    per KPI per workspace. Invalidated on document upload or delete via
    invalidate_workspace_cache() in backend/api/routes/kpis.py.
    """

    __tablename__ = "workspace_kpi_cache"

    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    kpi_key: Mapped[str] = mapped_column(String, primary_key=True)
    response: Mapped[str] = mapped_column(String, nullable=False)
    citations: Mapped[str] = mapped_column(String, nullable=False)  # JSON-encoded list
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
