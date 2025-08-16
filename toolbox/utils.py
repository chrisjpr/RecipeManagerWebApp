# emails/utils.py

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
import os

def send_insurer_email(*, police_number, insured_name, birth_date, start_date, end_date, sender_name, to_email=None, template_path=None):
    """
    Renders and sends the insurer email. Returns (subject, body, to_email, sent_at).
    Raises an Exception if send fails.
    """
    subject = f"{police_number}"

    # Where to send:
    to_email = (
        to_email
        or "vertrag@zurich.com"
    )
    if not to_email:
        raise ValueError("No destination email configured (set INSURER_EMAIL or DEFAULT_FROM_EMAIL).")

    # Which template to use:
    # You can keep the template in the emails app OR in the toolbox app.
    # Default below assumes you put it under the emails app.
    template_path = template_path or "emails/insurer_request.txt"

    context = {
        "police_number" : police_number,
        "insured_name": insured_name,
        "birth_date": birth_date,
        "start_date": start_date,
        "end_date": end_date,
        "sender_name" : sender_name

    }
    body = render_to_string(template_path, context)

    sent_count = send_mail(
        subject,
        body,
        os.getenv("DEFAULT_FROM_EMAIL"),  # sender
        [to_email, "agentur.judkins@zuerich.de", "chris@judkins.de"],
        fail_silently=False,
    )
    if sent_count != 1:
        raise RuntimeError("send_mail did not report success")

    return subject, body, to_email, timezone.now()
