from django.urls import path
from . import views

app_name = "toolbox"

urlpatterns = [
    path("insurer-email/", views.insurer_email_view, name="insurer_email"),
    path("insurer-email/sent/", views.insurer_email_sent, name="insurer_email_sent"),
    path("", views.landing, name="home"),

]