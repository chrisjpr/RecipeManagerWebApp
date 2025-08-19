

from django.http import HttpResponse

from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .forms import RegisterForm, CustomLoginForm
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import FriendRequest, Friendship, CustomUser
from django.contrib.auth.models import User
from django.db.models import Q
from emails.utils import custom_send_verification_email
from django.contrib.auth import get_user_model
import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from emails.utils import custom_send_password_reset_email


User = get_user_model()

# Create your views here.

#region REGISTRATION
####################### REGISTRATION #####################
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Optional: prevent login before verification
            if not user.verification_code:
                user.verification_code = uuid.uuid4()
            user.save()

            custom_send_verification_email(user, request)
            messages.success(request, "✅ Registration successful! Please check your email to verify your account.")
            return redirect('accounts:login')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

def verify_email(request, code):
    try:
        user = User.objects.get(verification_code=code)
        user.is_verified = True
        user.is_active = True
        user.verification_code = uuid.uuid4()  # refresh code
        user.save()
        messages.success(request, "🎉 Email verified! You can now log in.")
        return redirect('accounts:login')
    except User.DoesNotExist:
        return HttpResponse("❌ Invalid or expired verification code.", status=400)
    
@login_required
def resend_verification(request):
    if request.user.is_verified:
        messages.info(request, "✅ Your email is already verified.")
    else:
        request.user.verification_code = uuid.uuid4()
        request.user.save()
        custom_send_verification_email(request.user)
        messages.success(request, "📧 A new verification email has been sent.")
    return redirect('home')
def unverified_view(request):
    user_id = request.session.get('unverified_user_id')
    user = User.objects.filter(id=user_id).first()

    if request.method == 'POST' and user:
        custom_send_verification_email(user)
        messages.success(request, f"A new verification link was sent to {user.email}.")

    return render(request, 'registration/unverified.html', {'user': user})

    
####################### /REGISTRATION #####################
#endregion

#region LOGIN/LOGOUT
####################### LOGIN/LOGOUT #####################

def login_view(request):
    form = CustomLoginForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()

            if not user.is_verified:
                if not user.verification_code:
                    user.verification_code = uuid.uuid4()
                    user.save()

                custom_send_verification_email(user, request)
                return render(request, 'registration/custom_unverified.html', {'email': user.email})

            # Log in verified users
            login(request, user)
            return redirect('recipes:home')

        else:
            username = request.POST.get('username')
            try:
                user = CustomUser.objects.get(username=username)
                if not user.is_verified:
                    # Resend verification email
                    if not user.verification_code:
                        user.verification_code = uuid.uuid4()
                        user.save()

                    custom_send_verification_email(user, request)
                    return render(request, 'registration/custom_unverified.html', {'email': user.email})
            except CustomUser.DoesNotExist:
                pass  # fall through to invalid login message

            messages.error(request, "❌ Invalid username or password.")

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return render(request, 'registration/logout.html')
####################### /LOGIN/LOGOUT #####################


#region FRIEND MANAGEMENT
###################### FRIEND MANAGEMENT #####################
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def send_friend_request(request, user_id):
    to_user = get_object_or_404(User, id=user_id)
    if request.user == to_user:
        messages.error(request, "You cannot send a friend request to yourself.")
    elif FriendRequest.objects.filter(from_user=request.user, to_user=to_user).exists():
        messages.info(request, "Friend request already sent.")
    elif Friendship.objects.filter(user=request.user, friend=to_user).exists():
        messages.info(request, "You are already friends.")
    else:
        FriendRequest.objects.create(from_user=request.user, to_user=to_user)
        messages.success(request, "Friend request sent!")
    return redirect('accounts:friend_dashboard')

@login_required
def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(FriendRequest, id=request_id, to_user=request.user)
    Friendship.objects.create(user=request.user, friend=friend_request.from_user)
    Friendship.objects.create(user=friend_request.from_user, friend=request.user)
    friend_request.delete()
    messages.success(request, "Friend request accepted!")
    return redirect('accounts:friend_dashboard')

@login_required
def decline_friend_request(request, request_id):
    friend_request = get_object_or_404(FriendRequest, id=request_id, to_user=request.user)
    friend_request.delete()
    messages.info(request, "Friend request declined.")
    return redirect('accounts:friend_dashboard')

@login_required
def friend_dashboard(request):
    friends = Friendship.objects.filter(user=request.user).select_related('friend')
    received_requests = FriendRequest.objects.filter(to_user=request.user)
    sent_requests = FriendRequest.objects.filter(from_user=request.user)
    context = {
        'friends': [f.friend for f in friends],
        'received_requests': received_requests,
        'sent_requests': sent_requests,
    }
    return render(request, 'friends/friend_dashboard.html', context)


@login_required
def delete_friend(request, user_id):
    friend = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        # Delete both directions of the friendship
        Friendship.objects.filter(user=request.user, friend=friend).delete()
        Friendship.objects.filter(user=friend, friend=request.user).delete()

        messages.success(request, f"{friend.username} has been removed from your friends.")
    
    return redirect('accounts:friend_dashboard')


@login_required
def friend_search(request):
    query = request.GET.get('q')
    results = []
    if query:
        results = User.objects.filter(Q(username__icontains=query)).exclude(id=request.user.id)
    
    friends = Friendship.objects.filter(user=request.user).select_related('friend')
    received_requests = FriendRequest.objects.filter(to_user=request.user)
    sent_requests = FriendRequest.objects.filter(from_user=request.user)

    context = {
        'friends': [f.friend for f in friends],
        'received_requests': received_requests,
        'sent_requests': sent_requests,
        'results': results,
        'query': query,
    }
    return render(request, 'friends/friend_dashboard.html', context)

###################### FRIEND MANAGEMENT #####################
#endregion



#region PASSWORD RESET
###################### PASSWORD RESET #####################


User = get_user_model()

def password_reset_request(request):
    print("DEBUG 1: IS THIS VIEW REACHED1?")
    if request.method == 'POST':
        print("DEBUG 2: IS THIS VIEW REACHED2?")
        email = request.POST.get('email')
        associated_users = User.objects.filter(email=email)
        if associated_users.exists():
            for user in associated_users:
                print(f"User found: {user.username} with email {user.email}")
                # Generate password reset link
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    reverse('accounts:custom_password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )

                custom_send_password_reset_email(user, reset_url)
            messages.success(request, "✅ If an account with that email exists, a reset link was sent.")
            return redirect('accounts:login')
        else:
            messages.success(request, "✅ If an account with that email exists, a reset link was sent.")
    return render(request, 'registration/custom_password_reset_form.html')

def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            if password == confirm_password:
                user.set_password(password)
                user.save()
                messages.success(request, "✅ Your password has been reset. You can log in now.")
                return redirect('accounts:login')
            else:
                messages.error(request, "❌ Passwords do not match.")
        return render(request, 'registration/custom_password_reset_confirm.html', {'validlink': True})
    else:
        return render(request, 'registration/custom_password_reset_confirm.html', {'validlink': False})

#region ACCOUNT SETTINGS
###################### ACCOUNT SETTINGS #####################

# accounts/views.py  (add these imports near the top with your others)
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import AccountProfileForm, ICON_CHOICES

from django.contrib.auth.decorators import login_required
from django.contrib import messages


from .forms import AccountProfileForm, ICON_CHOICES


@login_required
def account_settings(request):
    user = request.user
    profile_form = AccountProfileForm(instance=user)
    password_form = PasswordChangeForm(user=user)

    if request.method == "POST":
        if "save_profile" in request.POST:
            profile_form = AccountProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "✅ Profile updated.")
                return redirect("accounts:settings")
            else:
                messages.error(request, "❌ Please fix the highlighted errors.")
        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "🔒 Password changed successfully.")
                return redirect("accounts:settings")
            else:
                messages.error(request, "❌ Please correct the password form.")

    # Send emoji strings (not tuples) to the template
    icon_strings = [k for k, _ in ICON_CHOICES]

    return render(request, "accounts/settings.html", {
        "profile_form": profile_form,
        "password_form": password_form,
        "icon_choices": icon_strings,   # <— used by the radio grid in template
    })

###################### /ACCOUNT SETTINGS #####################
#endregion