"""
Dependency helpers that enforce plan limits.
Raise 403 with a clear message when a business exceeds their tier.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, Subscription, Document, Integration
from app.auth import get_current_user
from app.billing import PLAN_LIMITS


async def get_plan(business_id, db: AsyncSession) -> str:
    result = await db.execute(
        select(Subscription).where(Subscription.business_id == business_id)
    )
    sub = result.scalar_one_or_none()
    if not sub or sub.status not in ("active", "trialing"):
        return "free"
    return sub.plan


async def require_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Raises 403 if the business is on the free plan (no integrations)."""
    plan = await get_plan(current_user.business_id, db)
    if not PLAN_LIMITS[plan]["integrations"]:
        raise HTTPException(
            status_code=403,
            detail="Email and Slack integrations require a Pro or Business plan.",
        )
    return current_user


async def require_can_add_member(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Raises 403 if the business has reached their user limit."""
    plan = await get_plan(current_user.business_id, db)
    limit = PLAN_LIMITS[plan]["users"]

    count_result = await db.execute(
        select(func.count()).select_from(User)
        .where(User.business_id == current_user.business_id, User.is_active == True)
    )
    count = count_result.scalar_one()
    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan} plan allows up to {limit} team member(s). Upgrade to add more.",
        )
    return current_user


async def require_can_add_document(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Raises 403 if the business has reached their document limit."""
    plan = await get_plan(current_user.business_id, db)
    limit = PLAN_LIMITS[plan]["documents"]

    count_result = await db.execute(
        select(func.count()).select_from(Document)
        .where(Document.business_id == current_user.business_id)
    )
    count = count_result.scalar_one()
    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan} plan allows up to {limit} document(s). Upgrade to add more.",
        )
    return current_user
