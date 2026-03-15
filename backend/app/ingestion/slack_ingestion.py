"""
Slack ingestion via Slack Web API.
Fetches messages from specified channels and ingests them as documents.

Config keys stored in Integration.config:
  {
    "bot_token":       "xoxb-...",
    "channel_ids":     ["C123ABC", "C456DEF"],
    "max_messages":    200,
    "last_ts":         "0"   # Slack timestamp — updated after each sync
  }

Setup: Create a Slack app, add bot scopes (channels:history, channels:read,
groups:history), install to workspace, copy the Bot User OAuth Token.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Integration, Business
from app.ingestion.base import ingest_text_as_document

logger = logging.getLogger(__name__)


async def _fetch_slack_messages(config: dict) -> list[dict]:
    """Fetch messages from all configured channels using the Slack SDK."""
    from slack_sdk.web.async_client import AsyncWebClient
    from slack_sdk.errors import SlackApiError

    token       = config["bot_token"]
    channel_ids = config.get("channel_ids", [])
    max_msgs    = int(config.get("max_messages", 200))
    last_ts     = config.get("last_ts", "0")

    client   = AsyncWebClient(token=token)
    all_msgs = []

    for channel_id in channel_ids:
        try:
            # Get channel name for display
            info_resp = await client.conversations_info(channel=channel_id)
            channel_name = info_resp["channel"].get("name", channel_id)

            params = {
                "channel": channel_id,
                "limit":   min(max_msgs, 200),
            }
            if last_ts != "0":
                params["oldest"] = last_ts

            resp = await client.conversations_history(**params)
            messages = resp.get("messages", [])

            # Handle pagination
            while resp.get("has_more") and len(all_msgs) < max_msgs:
                cursor = resp["response_metadata"]["next_cursor"]
                resp   = await client.conversations_history(**params, cursor=cursor)
                messages.extend(resp.get("messages", []))

            for msg in messages:
                if msg.get("type") != "message" or msg.get("subtype"):
                    continue  # skip joins, leaves, bot messages
                text = msg.get("text", "").strip()
                if not text:
                    continue
                all_msgs.append({
                    "channel_name": channel_name,
                    "channel_id":   channel_id,
                    "text":         text,
                    "ts":           msg["ts"],
                    "user":         msg.get("user", "unknown"),
                })

        except SlackApiError as e:
            logger.warning("Slack API error for channel %s: %s", channel_id, e.response["error"])

    return all_msgs


def _group_messages_by_channel(messages: list[dict], max_chars: int = 6000) -> list[dict]:
    """
    Group messages by channel into batches of max_chars each.
    Returns list of {channel_name, channel_id, text, latest_ts}.
    """
    from collections import defaultdict
    by_channel = defaultdict(list)
    for msg in messages:
        by_channel[msg["channel_id"]].append(msg)

    batches = []
    for channel_id, msgs in by_channel.items():
        msgs.sort(key=lambda m: float(m["ts"]))
        current_text  = ""
        latest_ts     = "0"
        channel_name  = msgs[0]["channel_name"]

        for msg in msgs:
            line = f"[{msg['user']}]: {msg['text']}\n"
            if len(current_text) + len(line) > max_chars and current_text:
                batches.append({
                    "channel_name": channel_name,
                    "channel_id":   channel_id,
                    "text":         current_text,
                    "latest_ts":    latest_ts,
                })
                current_text = ""
            current_text += line
            if float(msg["ts"]) > float(latest_ts):
                latest_ts = msg["ts"]

        if current_text:
            batches.append({
                "channel_name": channel_name,
                "channel_id":   channel_id,
                "text":         current_text,
                "latest_ts":    latest_ts,
            })
    return batches


async def sync_slack_integration(
    integration: Integration,
    db: AsyncSession,
) -> tuple[int, str | None]:
    """
    Run a full Slack sync for one integration.
    Returns (batches_ingested, error_message_or_None).
    """
    biz_result = await db.execute(
        select(Business).where(Business.id == integration.business_id)
    )
    business = biz_result.scalar_one()

    try:
        messages = await _fetch_slack_messages(integration.config)
    except Exception as e:
        integration.status     = "error"
        integration.last_error = str(e)[:500]
        await db.commit()
        return 0, str(e)

    if not messages:
        integration.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        return 0, None

    batches    = _group_messages_by_channel(messages)
    ingested   = 0
    latest_ts  = integration.config.get("last_ts", "0")

    for batch in batches:
        try:
            source_name = f"Slack #{batch['channel_name']}"
            await ingest_text_as_document(
                db=db,
                business_id=integration.business_id,
                business_name=business.name,
                text=batch["text"],
                source_name=source_name,
                source_type="slack",
            )
            ingested += 1
            if float(batch["latest_ts"]) > float(latest_ts):
                latest_ts = batch["latest_ts"]
        except Exception as e:
            logger.warning("Failed to ingest Slack batch from #%s: %s", batch["channel_name"], e)

    # Update last_ts
    new_config = dict(integration.config)
    new_config["last_ts"] = latest_ts
    integration.config = new_config

    integration.last_synced_at = datetime.now(timezone.utc)
    integration.last_error     = None
    integration.status         = "active"
    await db.commit()

    return ingested, None
