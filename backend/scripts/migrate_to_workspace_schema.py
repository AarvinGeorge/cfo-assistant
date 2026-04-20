"""
migrate_to_workspace_schema.py

One-shot script that ports surviving data into the new multi-tenant
schema after PR #1 cleanup has run.

Role in project:
    Operational tooling. Run once, after `make cleanup-orphans APPLY=1`
    has removed orphans, to:
      1. Move surviving Pinecone vectors from namespace=default to
         namespace=wks_default, enriching metadata with user_id and
         workspace_id. Vector IDs preserved (legacy random UUIDs stay).
      2. Seed SQLite with the default user, workspace, member, chat
         session, and Document row for the surviving file.
      3. Reorganize files on disk into data/uploads/wks_default/.
      4. Verify all stores are aligned and exit non-zero if not.

Main parts:
    - migrate_pinecone(): copies vectors to new namespace with enriched
      metadata, then drops the old namespace.
    - seed_sqlite(): inserts default user, workspace, member, default
      chat session, and Document row for surviving file.
    - reorganize_disk(): moves the surviving uploaded file into the
      workspace-scoped directory; archives unrelated files.
    - main(): CLI entry point with --apply gate (dry-run by default).
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
from pathlib import Path

DEFAULT_USER_ID = "usr_default"
DEFAULT_WORKSPACE_ID = "wks_default"
DEFAULT_CHAT_SESSION_ID = "ses_default"


def migrate_pinecone(
    store,
    source_ns: str,
    target_ns: str,
    user_id: str,
    workspace_id: str,
) -> int:
    """Copy all vectors from source_ns to target_ns; enrich metadata; drop source_ns.

    Returns the number of vectors moved.
    """
    print(f"  Migrating Pinecone {source_ns} -> {target_ns}...")
    all_ids: list[str] = []
    for page in store.index.list(namespace=source_ns):
        all_ids.extend(page)

    if not all_ids:
        print("  No vectors to migrate.")
        return 0

    BATCH = 100
    moved = 0
    for i in range(0, len(all_ids), BATCH):
        batch_ids = all_ids[i:i + BATCH]
        res = store.index.fetch(ids=batch_ids, namespace=source_ns)
        vectors = res.vectors if hasattr(res, "vectors") else res.get("vectors", {})
        new_records = []
        for vid, v in vectors.items():
            md = v.metadata if hasattr(v, "metadata") else v.get("metadata", {})
            values = v.values if hasattr(v, "values") else v.get("values")
            new_md = dict(md)
            new_md["user_id"] = user_id
            new_md["workspace_id"] = workspace_id
            new_records.append({"id": vid, "values": values, "metadata": new_md})
        store.index.upsert(vectors=new_records, namespace=target_ns)
        moved += len(new_records)

    time.sleep(2)  # let Pinecone catch up before verification

    stats = store.index.describe_index_stats()
    ns_entry = stats.namespaces.get(target_ns) if hasattr(stats.namespaces, "get") else None
    if ns_entry is None:
        ns_entry = stats.namespaces[target_ns] if target_ns in stats.namespaces else None
    target_count = getattr(ns_entry, "vector_count", None)
    if target_count is None and isinstance(ns_entry, dict):
        target_count = ns_entry.get("vector_count", 0)
    if target_count != len(all_ids):
        raise RuntimeError(
            f"Verification failed: target ns has {target_count}, expected {len(all_ids)}"
        )

    print(f"  OK {moved} vectors moved to {target_ns}. Dropping {source_ns}...")
    store.index.delete(delete_all=True, namespace=source_ns)
    return moved


def seed_sqlite(
    session,
    file_path: Path,
    doc_metadata_from_pinecone: dict,
    user_id: str,
    workspace_id: str,
) -> dict:
    """Insert default user, workspace, member, chat session, and the surviving document."""
    from backend.db.models import User, Workspace, WorkspaceMember, Document, ChatSession

    print("  Seeding SQLite with default records...")
    session.merge(User(id=user_id, email=None, display_name="Local User"))
    session.merge(Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Default Workspace",
        description="Created during migration from single-tenant schema",
        status="active",
    ))
    session.merge(WorkspaceMember(
        workspace_id=workspace_id, user_id=user_id, role="owner"
    ))
    session.merge(ChatSession(
        id=DEFAULT_CHAT_SESSION_ID,
        user_id=user_id,
        workspace_id=workspace_id,
        title="Untitled Chat",
    ))

    file_hash = (
        hashlib.sha256(file_path.read_bytes()).hexdigest()
        if file_path.exists()
        else None
    )

    doc_id = doc_metadata_from_pinecone.get("doc_id")
    session.merge(Document(
        id=doc_id,
        workspace_id=workspace_id,
        user_id=user_id,
        name=doc_metadata_from_pinecone.get("doc_name", file_path.name),
        doc_type=doc_metadata_from_pinecone.get("doc_type"),
        fiscal_year=doc_metadata_from_pinecone.get("fiscal_year"),
        file_hash=file_hash,
        chunk_count=doc_metadata_from_pinecone.get("chunk_count", 0),
        status="indexed",
    ))
    session.commit()
    print(f"  OK Seeded user, workspace, chat session, and document {doc_id}.")
    return {"doc_id": doc_id, "file_hash": file_hash}


def reorganize_disk(
    uploads_dir: Path,
    workspace_id: str,
    surviving_filename: str,
    surviving_doc_id: str,
    surviving_ext: str,
) -> Path:
    """Move surviving file to data/uploads/{workspace_id}/{doc_id}.{ext}; archive others."""
    print(f"  Reorganizing {uploads_dir}...")
    target_dir = uploads_dir / workspace_id
    archive_dir = uploads_dir / "_pre_migration"
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    surviving_src = uploads_dir / surviving_filename
    surviving_dst = target_dir / f"{surviving_doc_id}{surviving_ext}"

    if not surviving_src.exists():
        raise FileNotFoundError(f"Surviving file not found at {surviving_src}")

    shutil.move(str(surviving_src), str(surviving_dst))
    print(f"  Surviving file -> {surviving_dst}")

    # Move all OTHER files in uploads_dir (not in subdirs) to archive
    for entry in uploads_dir.iterdir():
        if entry.is_file():
            shutil.move(str(entry), str(archive_dir / entry.name))
            print(f"  Archived: {entry.name}")

    return surviving_dst


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate single-tenant data into the multi-tenant schema."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute (default is dry-run plan only).",
    )
    parser.add_argument(
        "--surviving-file",
        required=True,
        help="Filename of the document that should survive migration.",
    )
    args = parser.parse_args()

    print("=== Migrate to Workspace Schema ===")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Surviving file: {args.surviving_file}")
    print()

    if not args.apply:
        print("Dry-run plan:")
        print(f"  1. Move all vectors from Pinecone 'default' -> '{DEFAULT_WORKSPACE_ID}' with enriched metadata")
        print(f"  2. Drop Pinecone namespace 'default'")
        print(f"  3. Insert SQLite rows: user {DEFAULT_USER_ID}, workspace {DEFAULT_WORKSPACE_ID}, member, chat {DEFAULT_CHAT_SESSION_ID}, document")
        print(f"  4. Move data/uploads/{args.surviving_file} -> data/uploads/{DEFAULT_WORKSPACE_ID}/<doc_id>.<ext>")
        print(f"  5. Archive other files in data/uploads/ to data/uploads/_pre_migration/")
        print()
        print("Re-run with --apply to execute.")
        return 0

    # APPLY path
    from backend.core.pinecone_store import get_pinecone_store
    from backend.db.engine import get_session_factory

    store = get_pinecone_store()
    SessionLocal = get_session_factory()

    # Identify the surviving doc_id by reading one vector's metadata from Pinecone
    print("Identifying surviving doc_id from Pinecone (namespace=default)...")
    sample_ids: list[str] = []
    for page in store.index.list(namespace="default"):
        sample_ids.extend(page)
        if len(sample_ids) >= 1:
            break
    if not sample_ids:
        print("ERROR: No vectors in namespace=default. Migration aborted.")
        return 1

    res = store.index.fetch(ids=sample_ids[:1], namespace="default")
    vectors = res.vectors if hasattr(res, "vectors") else res.get("vectors", {})
    first_v = next(iter(vectors.values()))
    md = first_v.metadata if hasattr(first_v, "metadata") else first_v.get("metadata", {})
    surviving_doc_id = md["doc_id"]
    surviving_doc_name = md.get("doc_name", args.surviving_file)
    surviving_doc_type = md.get("doc_type")
    surviving_fy = md.get("fiscal_year")
    surviving_ext = Path(args.surviving_file).suffix.lower()
    print(f"  Surviving doc_id: {surviving_doc_id}")

    # 1+2. Pinecone migration
    moved = migrate_pinecone(
        store,
        source_ns="default",
        target_ns=DEFAULT_WORKSPACE_ID,
        user_id=DEFAULT_USER_ID,
        workspace_id=DEFAULT_WORKSPACE_ID,
    )

    # 3. SQLite seed
    uploads_dir = Path("data/uploads")
    surviving_src = uploads_dir / args.surviving_file
    with SessionLocal() as session:
        seed_sqlite(
            session,
            surviving_src,
            {
                "doc_id": surviving_doc_id,
                "doc_name": surviving_doc_name,
                "doc_type": surviving_doc_type,
                "fiscal_year": surviving_fy,
                "chunk_count": moved,
            },
            DEFAULT_USER_ID,
            DEFAULT_WORKSPACE_ID,
        )

    # 4. Disk reorg
    reorganize_disk(
        uploads_dir,
        DEFAULT_WORKSPACE_ID,
        args.surviving_file,
        surviving_doc_id,
        surviving_ext,
    )

    print()
    print("OK Migration complete. Run `make stats` to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
