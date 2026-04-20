"""
test_context.py

Verifies the RequestContext dependency yields the v1 hardcoded defaults
and is overridable for v2 auth integration.
"""
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from backend.core.context import RequestContext, get_request_context


def test_default_request_context_has_default_user_and_workspace():
    ctx = get_request_context()
    assert ctx.user_id == "usr_default"
    assert ctx.workspace_id == "wks_default"


def test_request_context_is_immutable():
    import dataclasses
    ctx = RequestContext(user_id="usr_x", workspace_id="wks_y")
    assert dataclasses.is_dataclass(ctx)
    try:
        ctx.user_id = "modified"
        assert False, "should be frozen"
    except dataclasses.FrozenInstanceError:
        pass


def test_request_context_works_as_fastapi_dependency():
    app = FastAPI()

    @app.get("/whoami")
    def whoami(ctx: RequestContext = Depends(get_request_context)):
        return {"user": ctx.user_id, "workspace": ctx.workspace_id}

    client = TestClient(app)
    r = client.get("/whoami")
    assert r.status_code == 200
    assert r.json() == {"user": "usr_default", "workspace": "wks_default"}
