"""
Email ingestion via IMAP.
Fetches unseen emails from the configured mailbox, converts each
email to text, and ingests it through the shared pipeline.

Config keys stored in Integration.config:
  {
    "imap_host":     "imap.gmail.com",
    "imap_port":     993,
    "email":         "you@gmail.com",
    "password":      "app-password",
    "folder":        "INBOX",
    "max_emails":    50,
    "last_uid":      0         # updated after each sync
  }

For Gmail: enable IMAP + create an App Password (not your main password).
"""
import imaplib
import email as email_lib
import logging
from datetime import datetime, timezone
from email.header import decode_header, make_header

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Integration, Business
from app.ingestion.base import ingest_text_as_document

logger = logging.getLogger(__name__)


def _decode_header_str(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value or ""


def _extract_email_text(msg) -> str:
    """Extract plain text from an email message (handles multipart)."""
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ct == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))
    return "\n\n".join(parts)


def _fetch_emails(config: dict) -> list[dict]:
    """
    Connect to IMAP, fetch emails with UID > last_uid, return list of dicts.
    Synchronous — runs in a thread pool via the caller.
    """
    host        = config.get("imap_host", "imap.gmail.com")
    port        = int(config.get("imap_port", 993))
    user        = config["email"]
    password    = config["password"]
    folder      = config.get("folder", "INBOX")
    max_emails  = int(config.get("max_emails", 50))
    last_uid    = int(config.get("last_uid", 0))

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select(folder, readonly=True)

        # Search for emails newer than last seen UID
        search_criteria = f"UID {last_uid + 1}:*" if last_uid > 0 else "ALL"
        _, data = conn.uid("SEARCH", None, search_criteria)
        uids = data[0].split() if data[0] else []

        # Limit to most recent
        uids = uids[-max_emails:]

        emails = []
        for uid in uids:
            try:
                _, msg_data = conn.uid("FETCH", uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)

                subject = _decode_header_str(msg.get("Subject", "(no subject)"))
                sender  = _decode_header_str(msg.get("From", "unknown"))
                date    = msg.get("Date", "")
                body    = _extract_email_text(msg)

                if not body.strip():
                    continue

                emails.append({
                    "uid":     int(uid),
                    "subject": subject,
                    "sender":  sender,
                    "date":    date,
                    "body":    body,
                })
            except Exception as e:
                logger.warning("Failed to parse email UID %s: %s", uid, e)

        conn.logout()
        return emails

    except Exception as e:
        raise RuntimeError(f"IMAP connection failed: {e}") from e


async def sync_email_integration(
    integration: Integration,
    db: AsyncSession,
) -> tuple[int, str | None]:
    """
    Run a full email sync for one integration.
    Returns (emails_ingested, error_message_or_None).
    """
    import asyncio

    # Load business name
    biz_result = await db.execute(
        select(Business).where(Business.id == integration.business_id)
    )
    business = biz_result.scalar_one()

    try:
        loop   = asyncio.get_event_loop()
        emails = await loop.run_in_executor(None, _fetch_emails, integration.config)
    except Exception as e:
        return 0, str(e)

    ingested   = 0
    max_uid    = int(integration.config.get("last_uid", 0))

    for em in emails:
        try:
            text = (
                f"Subject: {em['subject']}\n"
                f"From: {em['sender']}\n"
                f"Date: {em['date']}\n\n"
                f"{em['body']}"
            )
            source_name = f"Email: {em['subject'][:80]} (from {em['sender'][:40]})"

            await ingest_text_as_document(
                db=db,
                business_id=integration.business_id,
                business_name=business.name,
                text=text,
                source_name=source_name,
                source_type="email",
            )
            ingested += 1
            if em["uid"] > max_uid:
                max_uid = em["uid"]
        except Exception as e:
            logger.warning("Failed to ingest email '%s': %s", em.get("subject"), e)

    # Update last_uid so we don't re-fetch on next sync
    if max_uid > int(integration.config.get("last_uid", 0)):
        new_config = dict(integration.config)
        new_config["last_uid"] = max_uid
        integration.config = new_config

    integration.last_synced_at = datetime.now(timezone.utc)
    integration.last_error     = None
    integration.status         = "active"
    await db.commit()

    return ingested, None
