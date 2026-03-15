"""
Document pipeline:
  1. Extract raw text from PDF / PPTX / DOCX / TXT
  2. Split into overlapping chunks
  3. Embed each chunk with fastembed
  4. Store chunks in pgvector
  5. Ask Claude (Haiku) to extract a KB summary from the document
  6. Deep-merge the summary into the knowledge base
"""
import os
import re
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.llm import call_llm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models import Document, KnowledgeBase
from app.knowledge import deep_merge
from app.embeddings import embed
from app.vector_store import store_chunks

settings = get_settings()

# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_pdf(path: str) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text.strip())
    doc.close()
    return "\n\n".join(pages)


def extract_text_pptx(path: str) -> str:
    from pptx import Presentation
    prs = Presentation(path)
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        parts = [f"[Slide {i}]"]
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                parts.append(shape.text.strip())
        if len(parts) > 1:
            slides.append("\n".join(parts))
    return "\n\n".join(slides)


def extract_text_docx(path: str) -> str:
    from docx import Document as DocxDoc
    doc = DocxDoc(path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paras)


def extract_text_txt(path: str) -> str:
    with open(path, "r", errors="replace") as f:
        return f.read()


def extract_text(path: str, file_type: str) -> str:
    extractors = {
        "pdf":  extract_text_pdf,
        "pptx": extract_text_pptx,
        "ppt":  extract_text_pptx,
        "docx": extract_text_docx,
        "doc":  extract_text_docx,
        "txt":  extract_text_txt,
    }
    fn = extractors.get(file_type.lower())
    if not fn:
        raise ValueError(f"Unsupported file type: {file_type}")
    return fn(path)


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 1400,   # characters (~350 tokens)
    overlap: int = 200,
) -> list[str]:
    """
    Split text into overlapping chunks.
    Tries to break on paragraph boundaries first, falls back to character splits.
    """
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    # Split by paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Para itself too long — hard-split it
            if len(para) > chunk_size:
                for start in range(0, len(para), chunk_size - overlap):
                    piece = para[start : start + chunk_size].strip()
                    if piece:
                        chunks.append(piece)
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c) > 50]  # drop micro-chunks


# ── KB summary extraction ─────────────────────────────────────────────────────

def _extract_kb_summary(text: str, business_name: str) -> dict:
    """
    Ask the configured LLM to read the document and return structured KB facts.
    Uses the doc model (cheaper/faster) — this is a batch operation.
    """
    prompt = f"""You are extracting business knowledge from a document for {business_name}.

Read this document and extract ONLY concrete, specific facts about the business.
Return ONLY valid JSON (no markdown fences, no explanation) using this structure:
{{
  "overview":    {{}},
  "products":    {{}},
  "customers":   {{}},
  "revenue":     {{}},
  "team":        {{}},
  "competition": {{}},
  "history":     {{}},
  "now":         {{}},
  "future":      {{}},
  "ops":         {{}}
}}

Rules:
- Only include categories with actual content from this document
- Use short factual string values (not paragraphs)
- If nothing relevant for a category, leave it as {{}}
- Prefer specifics ("ARR: $2M", "team_size: 12") over generics

DOCUMENT (first 6000 chars):
{text[:6000]}"""

    try:
        raw = call_llm(
            system=None,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            use_doc_model=True,
        ).strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw).strip()
        return json.loads(raw)
    except Exception:
        return {}


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def process_document(
    document_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Full document pipeline — called as a BackgroundTask after upload.
    Updates document.status to 'ready' or 'failed' when done.
    """
    # Load document record
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return

    # Load business name for KB summary prompt
    from app.models import Business
    biz_result = await db.execute(select(Business).where(Business.id == doc.business_id))
    business = biz_result.scalar_one()

    try:
        # 1. Extract text
        file_path = os.path.join(settings.upload_dir, str(doc.business_id), doc.filename)
        raw_text = extract_text(file_path, doc.file_type)

        if not raw_text.strip():
            raise ValueError("No text could be extracted from this document")

        # 2. Chunk
        chunks = chunk_text(raw_text)
        if not chunks:
            raise ValueError("Document produced no usable text chunks")

        # 3. Embed all chunks
        embeddings = await embed(chunks)

        # 4. Store in pgvector
        count = await store_chunks(db, doc.id, doc.business_id, chunks, embeddings)

        # 5. Extract KB summary (sync call — runs in event loop, Haiku is fast)
        kb_updates = _extract_kb_summary(raw_text, business.name)

        # 6. Merge into knowledge base
        if kb_updates:
            kb_result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.business_id == doc.business_id)
            )
            kb = kb_result.scalar_one_or_none()
            if kb:
                kb.data = deep_merge(kb.data, kb_updates)

        # 7. Mark document as ready
        doc.status = "ready"
        doc.chunk_count = count
        doc.processed_at = datetime.now(timezone.utc)
        await db.commit()

    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        await db.commit()
        raise
