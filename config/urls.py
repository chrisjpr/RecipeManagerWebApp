"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include

# for mail sending
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

# Import Own Templates / Views
from recipes.views import home







#region TEST FUNCTIONS
##################### TEST FUNCTIONS #####################

def test_email_view(request):
    subject = "✅ Test Email from RecipeManager"
    message = "This is a test message to confirm your email setup works."
    from_email = None
    recipient_list = ["chris@judkins.de"]

    try:
        send_mail(subject, message, from_email, recipient_list)
        return HttpResponse("✅ Email sent successfully!")
    except Exception as e:
        return HttpResponse(f"❌ Error sending email: {e}")



##################### /TEST FUNCTIONS #####################
#endregion


## URL PATTERNS (CONNECTS WEBPAGE URLS TO BACKEND FUNCTIONS)
urlpatterns = [

    # FAVICON – browsers always request /favicon.ico at the root
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),

    # REIDRECT ROOT URL TO RECIPES APP
    path('', RedirectView.as_view(url='/recipemanager/', permanent=False)),
    # ADMIN PAGE
    path("admin/", admin.site.urls),
    path("django-rq/", include("django_rq.urls")),

    # EMAIL SENDING TEST
    path("test-email/", test_email_view),
    
    # API and App URLs

    path("recipemanager/", include(("recipes.urls", 'recipes')), name='recipes'),  # ✅ THIS LINE
    path("toolbox/", include("toolbox.urls"), name='toolbox'),  # ✅ THIS LINE

    # Authentication
    path('accounts/', include(('accounts.urls', 'accounts')), name = 'accounts'),  # ✅ THIS LINE
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)