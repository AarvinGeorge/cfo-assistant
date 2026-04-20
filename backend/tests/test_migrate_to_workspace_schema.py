"""
test_migrate_to_workspace_schema.py

Unit tests for the migration script's pure functions (Pinecone and disk
operations are mocked; seed_sqlite tested end-to-end against in-memory SQLite).
"""
from pathlib import Path
from unittest.mock import MagicMock
from backend.scripts.migrate_to_workspace_schema import seed_sqlite


def test_seed_sqlite_inserts_default_records(tmp_path):
    from backend.db.engine import create_engine_for_url, make_session_factory
    from backend.db.models import Base, User, Workspace, Document, ChatSession, WorkspaceMember

    engine = create_engine_for_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    # Create a fake source file for hashing
    src_file = tmp_path / "EOG.pdf"
    src_file.write_bytes(b"fake pdf bytes")

    with SessionLocal() as session:
        result = seed_sqlite(
            session,
            src_file,
            {
                "doc_id": "doc_test1234",
                "doc_name": "EOG.pdf",
                "doc_type": "10-K",
                "fiscal_year": "2025",
                "chunk_count": 1220,
            },
            "usr_default",
            "wks_default",
        )

    assert result["doc_id"] == "doc_test1234"
    assert result["file_hash"] is not None
    assert len(result["file_hash"]) == 64  # SHA-256 hex

    # Verify all records inserted
    with SessionLocal() as session:
        assert session.get(User, "usr_default") is not None
        assert session.get(Workspace, "wks_default") is not None
        assert session.get(WorkspaceMember, ("wks_default", "usr_default")) is not None
        assert session.get(ChatSession, "ses_default") is not None
        doc = session.get(Document, "doc_test1234")
        assert doc is not None
        assert doc.chunk_count == 1220
        assert doc.workspace_id == "wks_default"
        assert doc.user_id == "usr_default"
        assert doc.doc_type == "10-K"
