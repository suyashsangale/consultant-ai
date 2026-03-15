"""
Document upload and management endpoints.
Upload returns immediately (202) — processing runs as a BackgroundTask.
"""
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import aiofiles

from app.database import get_db
from app.models import User, Document
from app.auth import get_current_user
from app.plan_guard import require_can_add_document
from app.config import get_settings
from app.document_processor import process_document

settings = get_settings()
router  = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf":          "pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":   "docx",
    "application/msword":       "doc",
    "text/plain":               "txt",
}

ALLOWED_EXTENSIONS = {"pdf", "pptx", "ppt", "docx", "doc", "txt"}
MAX_BYTES = settings.max_upload_mb * 1024 * 1024


def _resolve_type(file: UploadFile) -> str:
    """Determine file type from content-type + extension."""
    ct = (file.content_type or "").lower()
    if ct in ALLOWED_TYPES:
        return ALLOWED_TYPES[ct]
    ext = Path(file.filename or "").suffix.lstrip(".").lower()
    if ext in ALLOWED_EXTENSIONS:
        return ext
    raise HTTPException(
        status_code=415,
        detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
    )


@router.post("", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(require_can_add_document),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document for processing.
    Returns 202 Accepted immediately; processing happens in the background.
    Poll GET /documents/{id} to check status.
    """
    file_type = _resolve_type(file)

    # Read file contents (limit size)
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_mb} MB.",
        )

    # Save to disk under uploads/{business_id}/
    biz_dir = Path(settings.upload_dir) / str(current_user.business_id)
    biz_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4()}.{file_type}"
    file_path = biz_dir / stored_filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create DB record
    doc = Document(
        business_id=current_user.business_id,
        filename=stored_filename,
        original_name=file.filename or stored_filename,
        file_type=file_type,
        file_size=len(content),
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Kick off background processing (non-blocking)
    # We create a new DB session for the background task to avoid sharing state
    async def _run_processing(document_id: uuid.UUID):
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            await process_document(document_id, bg_db)

    background_tasks.add_task(_run_processing, doc.id)

    return {
        "id":            str(doc.id),
        "original_name": doc.original_name,
        "file_type":     doc.file_type,
        "file_size":     doc.file_size,
        "status":        doc.status,
        "created_at":    doc.created_at.isoformat(),
    }


@router.get("")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.business_id == current_user.business_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id":            str(d.id),
            "original_name": d.original_name,
            "file_type":     d.file_type,
            "file_size":     d.file_size,
            "status":        d.status,
            "chunk_count":   d.chunk_count,
            "error_message": d.error_message,
            "created_at":    d.created_at.isoformat(),
            "processed_at":  d.processed_at.isoformat() if d.processed_at else None,
        }
        for d in docs
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.business_id == current_user.business_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id":            str(doc.id),
        "original_name": doc.original_name,
        "file_type":     doc.file_type,
        "file_size":     doc.file_size,
        "status":        doc.status,
        "chunk_count":   doc.chunk_count,
        "error_message": doc.error_message,
        "created_at":    doc.created_at.isoformat(),
        "processed_at":  doc.processed_at.isoformat() if doc.processed_at else None,
    }


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.business_id == current_user.business_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file from disk
    file_path = Path(settings.upload_dir) / str(current_user.business_id) / doc.filename
    if file_path.exists():
        file_path.unlink()

    # Chunks are deleted via ON DELETE CASCADE on the documents table
    await db.delete(doc)
    await db.commit()
