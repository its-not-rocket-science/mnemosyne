"""One-off script: delete corpus SourceDocumentRows whose source_url no longer
appears in corpora/manifest.yaml.

These were created during a period when 9 manifest entries pointed to wrong
Project Gutenberg IDs (English/Italian books ingested under French/Spanish/
Portuguese/Latin/Arabic source documents).  After the manifest was corrected
and correct content re-ingested, the old documents became orphans.

Usage
-----
    # dry run (default) — prints what would be deleted
    poetry run python scripts/cleanup_orphaned_corpus.py

    # actually delete
    poetry run python scripts/cleanup_orphaned_corpus.py --execute
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure project root is on path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.config import get_settings
from backend.corpus.manifest import load_manifest
from backend.models import ParsedText, SourceChunkRow, SourceDocumentRow, SourceProgressionRow


MANIFEST_PATH = Path("corpora/manifest.yaml")
CORPUS_CONTENT_TYPE = "corpus"


async def run(execute: bool) -> None:
    manifest = load_manifest(MANIFEST_PATH)
    valid_urls: set[str] = {e.source_url for e in manifest.entries}

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with factory() as db:
            # Find corpus SourceDocumentRows whose URL is not in the manifest.
            result = await db.execute(
                select(SourceDocumentRow).where(
                    SourceDocumentRow.content_type == CORPUS_CONTENT_TYPE,
                )
            )
            all_corpus_docs = result.scalars().all()

            orphans = [d for d in all_corpus_docs if d.source_url not in valid_urls]

            if not orphans:
                print("No orphaned corpus documents found.")
                return

            print(f"{'DRY RUN — ' if not execute else ''}Found {len(orphans)} orphaned corpus document(s):\n")
            for doc in orphans:
                print(f"  [{doc.language}] {doc.title!r}  url={doc.source_url}")

            if not execute:
                print("\nRe-run with --execute to delete.")
                return

            # Collect ParsedText IDs before deleting SourceDocumentRows.
            orphan_ids = [d.id for d in orphans]

            chunk_result = await db.execute(
                select(SourceChunkRow.parsed_text_id).where(
                    SourceChunkRow.source_document_id.in_(orphan_ids)
                )
            )
            parsed_text_ids = [row[0] for row in chunk_result.all()]

            # 1. Delete SourceProgressionRow (no ORM cascade from SourceDocumentRow).
            prog_result = await db.execute(
                delete(SourceProgressionRow).where(
                    SourceProgressionRow.source_document_id.in_(orphan_ids)
                )
            )
            print(f"\nDeleted {prog_result.rowcount} SourceProgressionRow(s).")

            # 2. Delete SourceDocumentRows (ORM cascade deletes SourceChunkRows).
            for doc in orphans:
                await db.delete(doc)
            await db.flush()
            print(f"Deleted {len(orphans)} SourceDocumentRow(s) (+ their SourceChunkRows).")

            # 3. Delete ParsedTexts (ORM cascade deletes Sentences → SentenceObjectRows).
            pt_result = await db.execute(
                select(ParsedText).where(ParsedText.id.in_(parsed_text_ids))
            )
            parsed_texts = pt_result.scalars().all()
            for pt in parsed_texts:
                await db.delete(pt)
            await db.flush()
            print(f"Deleted {len(parsed_texts)} ParsedText(s) (+ their Sentences/SentenceObjects).")

            await db.commit()
            print("\nDone.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Actually delete (default is dry run)")
    args = parser.parse_args()
    asyncio.run(run(execute=args.execute))


if __name__ == "__main__":
    main()
