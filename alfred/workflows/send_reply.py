"""Send a notification or reply email via SMTP when a message matches.

Config keys:

* ``to``       – recipient(s); string or list. Defaults to the original sender
  (so it acts as an auto-reply). Placeholders are substituted.
* ``subject``  – subject line (templated). Defaults to ``Re: {subject}``.
* ``body``     – message body (templated).
* ``smtp_host``/``smtp_port`` – default ``smtp.office365.com`` / ``587``.
* ``smtp_user``/``smtp_password`` – credentials (use ``${ENV}`` in config).
* ``from_addr`` – envelope From; defaults to ``smtp_user``.

For Microsoft 365, SMTP AUTH must be enabled for the mailbox and the tenant.
If it is disabled, use the ``call_webhook`` workflow to notify via Teams/Slack
instead.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..models import Message
from .base import Workflow

log = logging.getLogger("alfred.send_reply")


class SendReply(Workflow):
    def run(self, message: Message) -> None:
        to = self.spec.get("to", message.from_addr)
        recipients = [to] if isinstance(to, str) else list(to)
        recipients = [self.render(r, message) for r in recipients]

        subject = self.render(self.spec.get("subject", "Re: {subject}"), message)
        body = self.render(self.spec.get("body", ""), message)

        host = self.spec.get("smtp_host", "smtp.office365.com")
        port = int(self.spec.get("smtp_port", 587))
        user = self.spec.get("smtp_user")
        password = self.spec.get("smtp_password")
        from_addr = self.spec.get("from_addr", user)

        if not user or not password:
            raise ValueError("send_reply requires 'smtp_user' and 'smtp_password'")

        mail = EmailMessage()
        mail["From"] = from_addr
        mail["To"] = ", ".join(recipients)
        mail["Subject"] = subject
        mail.set_content(body)

        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(mail)
        log.info("Sent reply to %s (%s)", recipients, message.uid)
