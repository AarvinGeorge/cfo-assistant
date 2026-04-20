"""
context.py

Per-request context object that identifies the calling user and the
active workspace. The single spine that every multi-tenant operation
in the backend reads from.

Role in project:
    Core layer. Used as a FastAPI dependency on every route that needs
    to know who is acting and which workspace they are operating in.
    In v1 user_id is hardcoded ("usr_default") and workspace_id is read
    from the optional `X-Workspace-ID` header (defaulting to "wks_default"
    when absent). In v2 (sub-project 3) the body is replaced with JWT
    validation and the header becomes authoritative.

Main parts:
    - RequestContext: immutable dataclass holding (user_id, workspace_id).
    - get_request_context(): FastAPI dependency.
      v1: user_id = "usr_default"; workspace_id from X-Workspace-ID header
      or "wks_default".
      v2: validate auth, resolve user from JWT, verify workspace membership.
"""
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Header


@dataclass(frozen=True)
class RequestContext:
    user_id: str
    workspace_id: str


def get_request_context(
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-ID")] = None,
) -> RequestContext:
    """v1: user_id hardcoded; workspace_id from header, defaults to wks_default."""
    return RequestContext(
        user_id="usr_default",
        workspace_id=x_workspace_id or "wks_default",
    )
