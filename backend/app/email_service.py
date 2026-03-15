"""
Transactional email via SMTP (invite emails).
Falls back to console logging if SMTP is not configured — safe for local dev.
"""
import logging
from app.config import get_settings

settings = get_settings()
logger   = logging.getLogger(__name__)


async def send_invite_email(to_email: str, business_name: str, invite_url: str) -> None:
    subject = f"You've been invited to join {business_name} on Business Buddy"
    body    = f"""Hi,

You've been invited to join {business_name}'s Business Buddy workspace.

Click the link below to accept your invitation:
{invite_url}

This link expires in 7 days.

— The Business Buddy team
"""
    if not settings.smtp_enabled:
        logger.info("SMTP not configured. Invite email would send to %s:\n%s", to_email, body)
        return

    try:
        import aiosmtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"]    = settings.smtp_from
        msg["To"]      = to_email

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        logger.info("Invite email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send invite email to %s: %s", to_email, e)
        # Non-fatal — invite link is also shown in the UI
