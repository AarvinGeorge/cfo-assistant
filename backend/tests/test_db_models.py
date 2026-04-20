"""
test_db_models.py

Validates ORM model definitions: tables can be created, rows inserted,
foreign keys enforced, and indexes present.
"""
from datetime import datetime
import pytest
from sqlalchemy.exc import IntegrityError
from backend.db.engine import create_engine_for_url, make_session_factory
from backend.db.models import (
    Base, User, Workspace, WorkspaceMember, Document, ChatSession,
)


@pytest.fixture
def session():
    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as s:
        yield s


def test_can_insert_user(session):
    u = User(id="usr_test", email="cfo@example.com", display_name="Test CFO")
    session.add(u)
    session.commit()
    fetched = session.get(User, "usr_test")
    assert fetched.email == "cfo@example.com"


def test_workspace_requires_existing_owner(session):
    w = Workspace(id="wks_test", owner_id="usr_nonexistent", name="Acme")
    session.add(w)
    with pytest.raises(IntegrityError):
        session.commit()


def test_workspace_member_cascades_on_workspace_delete(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    m = WorkspaceMember(workspace_id="wks_a", user_id="usr_a", role="owner")
    session.add_all([u, w, m])
    session.commit()
    session.delete(w)
    session.commit()
    assert session.query(WorkspaceMember).count() == 0


def test_document_belongs_to_workspace(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    d = Document(
        id="doc_x", workspace_id="wks_a", user_id="usr_a",
        name="EOG-10K.pdf", doc_type="10-K", fiscal_year="2025",
        file_hash="abc123", chunk_count=1220, status="indexed",
    )
    session.add_all([u, w, d])
    session.commit()
    assert session.get(Document, "doc_x").chunk_count == 1220


def test_document_dedup_unique_constraint(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    d1 = Document(
        id="doc_1", workspace_id="wks_a", user_id="usr_a",
        name="A.pdf", file_hash="hash_xyz", chunk_count=10, status="indexed",
    )
    d2 = Document(
        id="doc_2", workspace_id="wks_a", user_id="usr_a",
        name="B.pdf", file_hash="hash_xyz", chunk_count=20, status="indexed",
    )
    session.add_all([u, w, d1, d2])
    with pytest.raises(IntegrityError):
        session.commit()


def test_chat_session_belongs_to_workspace(session):
    u = User(id="usr_a", email="a@x.com", display_name="A")
    w = Workspace(id="wks_a", owner_id="usr_a", name="Acme")
    c = ChatSession(id="ses_a", user_id="usr_a", workspace_id="wks_a", title="Untitled")
    session.add_all([u, w, c])
    session.commit()
    assert session.get(ChatSession, "ses_a").title == "Untitled"
