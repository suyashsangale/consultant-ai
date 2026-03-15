"""
Team management endpoints:
  GET    /team/members           — list all active members
  POST   /team/invite            — create + send invite
  GET    /team/invite/{token}    — look up invite (public — for accept page)
  POST   /team/invite/{token}/accept — accept invite (creates or joins account)
  DELETE /team/members/{user_id} — remove a member (owner/admin only)
"""
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import User, Invite, Business, KnowledgeBase, Subscription
from app.auth import get_current_user, hash_password, create_access_token
from app.email_service import send_invite_email
from app.plan_guard import require_can_add_member
from app.config import get_settings

settings = get_settings()
router   = APIRouter(prefix="/team", tags=["team"])


def _require_owner_or_admin(user: User):
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner or admin access required")


# ── List members ──────────────────────────────────────────────────────────────

@router.get("/members")
async def list_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(User.business_id == current_user.business_id, User.is_active == True)
        .order_by(User.created_at)
    )
    members = result.scalars().all()
    return [
        {
            "id":         str(m.id),
            "email":      m.email,
            "full_name":  m.full_name,
            "role":       m.role,
            "created_at": m.created_at.isoformat(),
            "is_self":    m.id == current_user.id,
        }
        for m in members
    ]


# ── Pending invites ───────────────────────────────────────────────────────────

@router.get("/invites")
async def list_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(current_user)
    result = await db.execute(
        select(Invite).where(
            Invite.business_id == current_user.business_id,
            Invite.accepted == False,
            Invite.expires_at > datetime.now(timezone.utc),
        ).order_by(Invite.created_at.desc())
    )
    invites = result.scalars().all()
    return [
        {
            "id":         str(i.id),
            "email":      i.email,
            "role":       i.role,
            "expires_at": i.expires_at.isoformat(),
            "invite_url": f"{settings.frontend_url}/invite/{i.token}",
        }
        for i in invites
    ]


# ── Create invite ─────────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"   # member | admin


@router.post("/invite", status_code=201)
async def create_invite(
    body: InviteRequest,
    current_user: User = Depends(require_can_add_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(current_user)

    if body.role not in ("member", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'member' or 'admin'")

    # Check email not already a member
    existing = await db.execute(
        select(User).where(
            User.email == body.email,
            User.business_id == current_user.business_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This email is already a team member")

    # Expire old pending invite for same email
    old = await db.execute(
        select(Invite).where(
            Invite.email == body.email,
            Invite.business_id == current_user.business_id,
            Invite.accepted == False,
        )
    )
    for old_inv in old.scalars().all():
        await db.delete(old_inv)

    # Create new invite
    token  = secrets.token_urlsafe(32)
    invite = Invite(
        business_id=current_user.business_id,
        email=body.email,
        role=body.role,
        token=token,
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()

    invite_url = f"{settings.frontend_url}/invite/{token}"

    # Load business name for email
    biz = await db.execute(select(Business).where(Business.id == current_user.business_id))
    business = biz.scalar_one()

    await send_invite_email(body.email, business.name, invite_url)

    return {
        "token":      token,
        "invite_url": invite_url,
        "email":      body.email,
        "role":       body.role,
    }


# ── Look up invite (public) ───────────────────────────────────────────────────

@router.get("/invite/{token}")
async def get_invite(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invite).where(Invite.token == token, Invite.accepted == False)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This invite has expired")

    biz = await db.execute(select(Business).where(Business.id == invite.business_id))
    business = biz.scalar_one()

    return {
        "email":         invite.email,
        "role":          invite.role,
        "business_name": business.name,
        "expires_at":    invite.expires_at.isoformat(),
    }


# ── Accept invite ─────────────────────────────────────────────────────────────

class AcceptInviteRequest(BaseModel):
    password: str
    full_name: str | None = None


@router.post("/invite/{token}/accept")
async def accept_invite(
    token: str,
    body: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invite).where(Invite.token == token, Invite.accepted == False)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This invite has expired")

    # Check if user already exists globally (could be joining a second workspace)
    existing = await db.execute(select(User).where(User.email == invite.email))
    user = existing.scalar_one_or_none()

    if user:
        # User exists but might be in a different business — update their business
        user.business_id = invite.business_id
        user.role        = invite.role
        user.is_active   = True
    else:
        if len(body.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        user = User(
            email=invite.email,
            hashed_password=hash_password(body.password),
            full_name=body.full_name,
            role=invite.role,
            business_id=invite.business_id,
        )
        db.add(user)

    invite.accepted = True
    await db.commit()
    await db.refresh(user)

    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer"}


# ── Remove member ─────────────────────────────────────────────────────────────

@router.delete("/members/{user_id}", status_code=204)
async def remove_member(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(current_user)

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.business_id == current_user.business_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    if target.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove the business owner")

    target.is_active = False
    await db.commit()
