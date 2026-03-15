"""
Shared ingestion logic for email + Slack sources.
Converts raw text content into Document records + pgvector chunks,
using the same pipeline as Phase 2 document uploads.
"""
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models import Document, KnowledgeBase
from app.knowledge import deep_merge
from app.embeddings import embed
from app.vector_store import store_chunks
from app.document_processor import chunk_text, _extract_kb_summary

settings = get_settings()


async def ingest_text_as_document(
    db: AsyncSession,
    business_id: uuid.UUID,
    business_name: str,
    text: str,
    source_name: str,   # display name, e.g. "Email: Q3 Report from Alice"
    source_type: str,   # "email" | "slack"
) -> Document:
    """
    Takes raw text (from an email or Slack message dump),
    runs it through the full Phase 2 pipeline, and returns the Document record.
    """
    if not text.strip():
        raise ValueError("Empty content — nothing to ingest")

    # 1. Save text to disk so Document record has a file path
    biz_dir = Path(settings.upload_dir) / str(business_id)
    biz_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}.txt"
    file_path = biz_dir / stored_filename
    file_path.write_text(text, encoding="utf-8")

    # 2. Create Document record
    doc = Document(
        business_id=business_id,
        filename=stored_filename,
        original_name=source_name[:500],
        file_type="txt",
        file_size=len(text.encode("utf-8")),
        status="processing",
        source=source_type,
    )
    db.add(doc)
    await db.flush()

    try:
        # 3. Chunk
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No usable text chunks")

        # 4. Embed
        embeddings = await embed(chunks)

        # 5. Store in pgvector
        count = await store_chunks(db, doc.id, business_id, chunks, embeddings)

        # 6. Extract KB facts and merge
        kb_updates = _extract_kb_summary(text, business_name)
        if kb_updates:
            kb_result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.business_id == business_id)
            )
            kb = kb_result.scalar_one_or_none()
            if kb:
                kb.data = deep_merge(kb.data, kb_updates)

        doc.status       = "ready"
        doc.chunk_count  = count
        doc.processed_at = datetime.now(timezone.utc)

    except Exception as e:
        doc.status        = "failed"
        doc.error_message = str(e)[:500]
        raise

    finally:
        await db.commit()

    return doc
