# toolbox/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import InsurerEmailForm
from .models import InsurerEmailLog

# ✅ reuse your emails app
from .utils import send_insurer_email



@staff_member_required(login_url="/accounts/login")
def landing(request):
    """
    Toolbox landing page. Add links to tools here.
    """
    tools = [
        {"title": "Send insurer email", "url_name": "toolbox:insurer_email", "description": "Compose & send a prefilled email to your insurer."},
        # Add more tools here as you build them
    ]
    return render(request, "toolbox/landing.html", {"tools": tools})

@staff_member_required(login_url="/accounts/login")
def insurer_email_view(request):
    if request.method == "POST":
        form = InsurerEmailForm(request.POST)
        if form.is_valid():
            insured_name = form.cleaned_data["insured_name"]
            birth_date  = form.cleaned_data["birth_date"]
            start_date  = form.cleaned_data["start_date"]
            end_date    = form.cleaned_data["end_date"]
            sender_name = form.cleaned_data["sender_name"]
            police_number = form.cleaned_data["police_number"]

            # Create log with default failed status; flip to sent on success
            log = InsurerEmailLog.objects.create(
                police_number=police_number,
                insured_name=insured_name,
                birth_date=birth_date,
                start_date=start_date,
                end_date=end_date,
                sender_name=sender_name,
                to_email="",  # filled below
                subject="",
                body="",
                status="failed",
            )

            try:
                # If you kept the template in the emails app, no template_path needed.
                # If you kept it in toolbox, add: template_path="toolbox/emails/insurer_request.txt"
                subject, body, to_email, sent_at = send_insurer_email(
                    insured_name=insured_name,
                    birth_date=birth_date,
                    start_date=start_date,
                    end_date=end_date,
                    sender_name=sender_name,
                    police_number=police_number,
                    to_email=None,  # use default or set in settings
                    template_path="toolbox/emails/insurer_request.txt"  # <- uncomment if you chose Option B
                )

                # Update log
                log.subject = subject
                log.body = body
                log.to_email = to_email
                log.status = "sent"
                log.sent_at = sent_at
                log.save(update_fields=["subject", "body", "to_email", "status", "sent_at"])

                messages.success(request, "Email sent to insurer ✅")
                return redirect("toolbox:insurer_email_sent")

            except Exception as e:
                log.error_message = str(e)
                log.save(update_fields=["error_message"])
                messages.error(request, f"Sending failed: {e}")

    else:
        form = InsurerEmailForm()

    return render(request, "toolbox/insurer_email_form.html", {"form": form})


@staff_member_required(login_url="/accounts/login")
def insurer_email_sent(request):
    return render(request, "toolbox/insurer_email_sent.html")