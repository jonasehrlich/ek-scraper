from __future__ import annotations

import asyncio
import logging
import typing as ty
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ek_scraper.config import EmailConfig

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result



_logger = logging.getLogger(__name__)


async def send_notification(session, config: EmailConfig, result: Result) -> None:
    # session is ignored here, kept for interface compatibility
    await asyncio.to_thread(_send_email, config, result)

def _send_email(config: EmailConfig, result: Result) -> None:
    try:
        msg = MIMEMultipart()
        msg["From"] = config.sender
        msg["To"] = ", ".join(config.recipient)
        msg["Subject"] = f"Scraper result: {result.get_title()}"

        body = f"""
        Title: {result.get_title()}
        Message: {result.get_message()}
        URL: {result.get_url()}
        """

        body_lines = []
        for ad in result.ad_items:   # <-- iterate over ad_items
            body_lines.append(
            f"Title: {ad.title}\n"
            f"Price: {ad.price}\n"
            f"Location: {ad.location}\n"
            f"Link: {ad.url}\n"
            f"Description: {ad.description}\n"
        )

        email_body = "\n\n".join(body_lines)

        msg.attach(MIMEText(email_body, "plain"))

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.username, config.password)
            server.sendmail(config.sender, config.recipient, msg.as_string())

        _logger.info("Sent email notification for '%s'", result.get_title())
    except Exception as exc:
        raise NotificationError(f"Failed to send email: {exc}") from exc


async def send_notifications(results: ty.Sequence[Result], config: EmailConfig) -> None:
    """Send email notifications for all results."""
    tasks: list[ty.Awaitable[ty.Any]] = []
    for result in results:
        if not result.ad_items:
            continue
        tasks.append(send_notification(None, config=config, result=result))

    await asyncio.gather(*tasks)
