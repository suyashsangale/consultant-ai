"""
Integration management endpoints (email + Slack).
Requires Pro or Business plan (enforced via require_integrations dependency).

  GET    /integrations           — list all integrations
  POST   /integrations/email     — connect email (IMAP)
  POST   /integrations/slack     — connect Slack
  POST   /integrations/{id}/sync — trigger manual sync
  DELETE /integrations/{id}      — disconnect integration
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import User, Integration
from app.auth import get_current_user
from app.plan_guard import require_integrations

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _serialize(i: Integration) -> dict:
    config_safe = {k: v for k, v in i.config.items()
                   if k not in ("password", "bot_token")}   # never expose secrets
    return {
        "id":             str(i.id),
        "type":           i.type,
        "name":           i.name,
        "status":         i.status,
        "last_synced_at": i.last_synced_at.isoformat() if i.last_synced_at else None,
        "last_error":     i.last_error,
        "created_at":     i.created_at.isoformat(),
        "config_preview": config_safe,
    }


@router.get("")
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration)
        .where(Integration.business_id == current_user.business_id)
        .order_by(Integration.created_at)
    )
    return [_serialize(i) for i in result.scalars().all()]


# ── Email (IMAP) ──────────────────────────────────────────────────────────────

class EmailIntegrationRequest(BaseModel):
    imap_host:  str = "imap.gmail.com"
    imap_port:  int = 993
    email:      str
    password:   str         # App Password for Gmail; regular password for others
    folder:     str = "INBOX"
    max_emails: int = 50
    name:       str = ""    # display name; defaults to email address


@router.post("/email", status_code=201)
async def connect_email(
    body: EmailIntegrationRequest,
    current_user: User = Depends(require_integrations),
    db: AsyncSession = Depends(get_db),
):
    # Test connection before saving
    import asyncio, imaplib
    def _test():
        conn = imaplib.IMAP4_SSL(body.imap_host, body.imap_port)
        conn.login(body.email, body.password)
        conn.logout()
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _test)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IMAP connection failed: {e}")

    integration = Integration(
        business_id=current_user.business_id,
        type="email",
        name=body.name or body.email,
        config={
            "imap_host":  body.imap_host,
            "imap_port":  body.imap_port,
            "email":      body.email,
            "password":   body.password,
            "folder":     body.folder,
            "max_emails": body.max_emails,
            "last_uid":   0,
        },
        status="active",
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return _serialize(integration)


# ── Slack ─────────────────────────────────────────────────────────────────────

class SlackIntegrationRequest(BaseModel):
    bot_token:    str
    channel_ids:  list[str]
    max_messages: int = 200
    name:         str = "Slack workspace"


@router.post("/slack", status_code=201)
async def connect_slack(
    body: SlackIntegrationRequest,
    current_user: User = Depends(require_integrations),
    db: AsyncSession = Depends(get_db),
):
    if not body.channel_ids:
        raise HTTPException(status_code=400, detail="At least one channel_id is required")

    # Test token
    try:
        from slack_sdk.web.async_client import AsyncWebClient
        client = AsyncWebClient(token=body.bot_token)
        await client.auth_test()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Slack authentication failed: {e}")

    integration = Integration(
        business_id=current_user.business_id,
        type="slack",
        name=body.name,
        config={
            "bot_token":    body.bot_token,
            "channel_ids":  body.channel_ids,
            "max_messages": body.max_messages,
            "last_ts":      "0",
        },
        status="active",
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return _serialize(integration)


# ── Manual sync ───────────────────────────────────────────────────────────────

@router.post("/{integration_id}/sync")
async def sync_integration(
    integration_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_integrations),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.business_id == current_user.business_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    async def _run_sync(int_id: uuid.UUID):
        from app.database import AsyncSessionLocal
        from app.ingestion.email_ingestion import sync_email_integration
        from app.ingestion.slack_ingestion import sync_slack_integration

        async with AsyncSessionLocal() as bg_db:
            int_result = await bg_db.execute(select(Integration).where(Integration.id == int_id))
            bg_int = int_result.scalar_one_or_none()
            if not bg_int:
                return
            if bg_int.type == "email":
                await sync_email_integration(bg_int, bg_db)
            elif bg_int.type == "slack":
                await sync_slack_integration(bg_int, bg_db)

    background_tasks.add_task(_run_sync, integration.id)
    return {"status": "sync started", "integration_id": str(integration_id)}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.business_id == current_user.business_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    await db.delete(integration)
    await db.commit()
