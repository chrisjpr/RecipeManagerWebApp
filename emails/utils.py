# emails/utils.py

from django.core.mail import send_mail
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string



def custom_send_verification_email(user, request):
    current_site = get_current_site(request)
    domain = current_site.domain
    scheme = 'https' if request.is_secure() else 'http'
    verification_link = f"{scheme}://{domain}/accounts/verify/{user.verification_code}/"

    subject = "Verify your RecipeManager Account"
    message = f"""
Hi {user.username},

Thanks for signing up to RecipeManager!

Please verify your email by clicking the link below:

{verification_link}

If you didn’t register, you can ignore this email.

– Your RecipeManager Team
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def custom_send_password_reset_email(user, reset_url):
    subject = "🔐 Reset Your RecipeManager Password"
    message = render_to_string('registration/custom_password_reset_email.html', {
        'user': user,
        'reset_url': reset_url,
    })
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])