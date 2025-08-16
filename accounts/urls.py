from django.urls import path
from . import views



app_name = 'accounts'

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path('friend_dashboard/', views.friend_dashboard, name='friend_dashboard'),
    path('friends/send/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('friends/accept/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('friends/decline/<int:request_id>/', views.decline_friend_request, name='decline_friend_request'),
    path('friend_search/', views.friend_search, name='friend_search'),  # ✅ Add this line
    path('friends/delete/<int:user_id>/', views.delete_friend, name='delete_friend'),
    path('verify/<uuid:code>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path("password-reset/", views.password_reset_request, name="password_reset"),
    path("reset/<uidb64>/<token>/", views.password_reset_confirm, name="custom_password_reset_confirm"),
    path("settings/", views.account_settings, name="settings"),
]
