"""
Stripe billing helpers.
All Stripe calls are wrapped here so the rest of the app stays decoupled.

Plans:
  free     — 1 user, 5 documents, no integrations
  pro      — 5 users, 100 documents, email + slack integrations
  business — unlimited users, unlimited documents, all integrations
"""
import stripe
from app.config import get_settings

settings = get_settings()

# Plan limits — enforced at API layer
PLAN_LIMITS = {
    "free":     {"users": 1,   "documents": 5,   "integrations": False},
    "pro":      {"users": 5,   "documents": 100,  "integrations": True},
    "business": {"users": 999, "documents": 9999, "integrations": True},
}


def get_client() -> stripe.StripeClient:
    if not settings.stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    return stripe.StripeClient(settings.stripe_secret_key)


def get_plan_for_price(price_id: str) -> str:
    if price_id == settings.stripe_price_pro:
        return "pro"
    if price_id == settings.stripe_price_business:
        return "business"
    return "free"


async def create_checkout_session(
    business_id: str,
    stripe_customer_id: str | None,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the URL."""
    client = get_client()
    params: dict = {
        "mode":       "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url":  cancel_url,
        "metadata":    {"business_id": business_id},
        "subscription_data": {"metadata": {"business_id": business_id}},
    }
    if stripe_customer_id:
        params["customer"] = stripe_customer_id
    session = client.checkout.sessions.create(**params)
    return session.url


async def create_portal_session(stripe_customer_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session and return the URL."""
    client = get_client()
    session = client.billing_portal.sessions.create(
        customer=stripe_customer_id,
        return_url=return_url,
    )
    return session.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    client = get_client()
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )
