"""
Billing endpoints:
  GET  /billing/status         — current plan + subscription details
  POST /billing/checkout       — create Stripe checkout session
  POST /billing/portal         — create Stripe customer portal session
  POST /billing/webhook        — Stripe webhook (no auth — verified by signature)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import User, Business, Subscription
from app.auth import get_current_user
from app.billing import (
    PLAN_LIMITS, get_plan_for_price,
    create_checkout_session, create_portal_session, construct_webhook_event
)
from app.config import get_settings

settings = get_settings()
router   = APIRouter(prefix="/billing", tags=["billing"])
logger   = logging.getLogger(__name__)


class CheckoutRequest(BaseModel):
    plan: str   # "pro" | "business"


@router.get("/status")
async def billing_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub_result = await db.execute(
        select(Subscription).where(Subscription.business_id == current_user.business_id)
    )
    sub = sub_result.scalar_one_or_none()

    plan   = sub.plan   if sub and sub.status in ("active", "trialing") else "free"
    limits = PLAN_LIMITS[plan]

    return {
        "plan":                plan,
        "status":              sub.status              if sub else "none",
        "cancel_at_period_end": sub.cancel_at_period_end if sub else False,
        "current_period_end":  sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        "limits":              limits,
        "stripe_enabled":      settings.stripe_enabled,
    }


@router.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not configured on this server.")

    price_map = {"pro": settings.stripe_price_pro, "business": settings.stripe_price_business}
    price_id  = price_map.get(body.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    biz_result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    business = biz_result.scalar_one()

    url = await create_checkout_session(
        business_id=str(business.id),
        stripe_customer_id=business.stripe_customer_id,
        price_id=price_id,
        success_url=f"{settings.frontend_url}/settings?billing=success",
        cancel_url=f"{settings.frontend_url}/settings?billing=canceled",
    )
    return {"checkout_url": url}


@router.post("/portal")
async def portal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not configured on this server.")

    biz_result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    business = biz_result.scalar_one()

    if not business.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found. Please subscribe first.")

    url = await create_portal_session(
        stripe_customer_id=business.stripe_customer_id,
        return_url=f"{settings.frontend_url}/settings",
    )
    return {"portal_url": url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handles Stripe events to keep subscription status in sync.
    Stripe calls this directly — no JWT auth, verified by webhook signature.
    """
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except Exception as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        return JSONResponse(status_code=400, content={"detail": "Invalid signature"})

    event_type = event["type"]
    data_obj   = event["data"]["object"]

    # ── checkout.session.completed — first subscription ──────────────────
    if event_type == "checkout.session.completed":
        biz_id      = data_obj.get("metadata", {}).get("business_id")
        customer_id = data_obj.get("customer")
        sub_id      = data_obj.get("subscription")

        if biz_id and customer_id:
            biz_result = await db.execute(
                select(Business).where(Business.id == biz_id)
            )
            business = biz_result.scalar_one_or_none()
            if business:
                business.stripe_customer_id = customer_id

        if sub_id:
            # subscription.updated will fire next and set the plan properly
            pass

    # ── customer.subscription.updated / created ───────────────────────────
    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        import stripe as stripe_lib
        sub_obj     = data_obj
        biz_id      = sub_obj.get("metadata", {}).get("business_id")
        customer_id = sub_obj.get("customer")
        price_id    = sub_obj["items"]["data"][0]["price"]["id"] if sub_obj.get("items") else ""
        plan        = get_plan_for_price(price_id)
        status      = sub_obj.get("status", "active")
        period_end  = sub_obj.get("current_period_end")
        cancel_flag = sub_obj.get("cancel_at_period_end", False)

        # Resolve business_id from customer if not in metadata
        if not biz_id and customer_id:
            biz_result = await db.execute(
                select(Business).where(Business.stripe_customer_id == customer_id)
            )
            biz = biz_result.scalar_one_or_none()
            if biz:
                biz_id = str(biz.id)

        if biz_id:
            sub_result = await db.execute(
                select(Subscription).where(Subscription.business_id == biz_id)
            )
            sub = sub_result.scalar_one_or_none()
            if not sub:
                sub = Subscription(business_id=biz_id)
                db.add(sub)

            sub.stripe_subscription_id = sub_obj["id"]
            sub.plan    = plan
            sub.status  = status
            sub.cancel_at_period_end = cancel_flag
            if period_end:
                from datetime import datetime, timezone
                sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    # ── customer.subscription.deleted ────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        sub_id = data_obj.get("id")
        if sub_id:
            sub_result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
            )
            sub = sub_result.scalar_one_or_none()
            if sub:
                sub.status = "canceled"
                sub.plan   = "free"

    await db.commit()
    return {"received": True}
