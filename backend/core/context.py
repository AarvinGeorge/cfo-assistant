"""
context.py

Per-request context object that identifies the calling user and the
active workspace. The single spine that every multi-tenant operation
in the backend reads from.

Role in project:
    Core layer. Used as a FastAPI dependency on every route that needs
    to know who is acting and which workspace they are operating in.
    In v1 it returns hardcoded defaults; in v2 (sub-project 3) the
    `get_request_context` body is replaced with JWT validation.

Main parts:
    - RequestContext: immutable dataclass holding (user_id, workspace_id).
    - get_request_context(): FastAPI dependency. v1: returns defaults.
      v2: validate auth header, look up user, resolve workspace.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    user_id: str
    workspace_id: str


def get_request_context() -> RequestContext:
    """v1: hardcoded defaults. v2: replaced with auth-based resolver."""
    return RequestContext(user_id="usr_default", workspace_id="wks_default")
