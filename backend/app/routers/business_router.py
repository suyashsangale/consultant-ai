from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Business, KnowledgeBase
from app.schemas import BusinessOut, BusinessUpdate, KnowledgeBaseOut, KBUpdate
from app.auth import get_current_user

router = APIRouter(prefix="/business", tags=["business"])


@router.get("", response_model=BusinessOut)
async def get_business(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    return biz


@router.patch("", response_model=BusinessOut)
async def update_business(
    body: BusinessUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    biz = result.scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(biz, field, value)

    await db.commit()
    await db.refresh(biz)
    return biz


@router.get("/knowledge", response_model=KnowledgeBaseOut)
async def get_knowledge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.business_id == current_user.business_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


@router.patch("/knowledge", response_model=KnowledgeBaseOut)
async def update_knowledge(
    body: KBUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually patch the knowledge base (for admin/debug use)."""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.business_id == current_user.business_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    kb.data = body.data
    if body.phase:
        kb.phase = body.phase
    if body.gaps is not None:
        kb.gaps = body.gaps

    await db.commit()
    await db.refresh(kb)
    return kb
