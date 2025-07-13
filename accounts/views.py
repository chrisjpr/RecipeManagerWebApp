

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
from emails.utils import send_verification_email
from django.contrib.auth import get_user_model
import uuid
from django.contrib.auth import authenticate


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

            send_verification_email(user, request)
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
        send_verification_email(request.user)
        messages.success(request, "📧 A new verification email has been sent.")
    return redirect('home')
def unverified_view(request):
    user_id = request.session.get('unverified_user_id')
    user = User.objects.filter(id=user_id).first()

    if request.method == 'POST' and user:
        send_verification_email(user)
        messages.success(request, f"A new verification link was sent to {user.email}.")

    return render(request, 'registration/unverified.html', {'user': user})

    
####################### /REGISTRATION #####################
#endregion

#region LOGIN/LOGOUT
####################### LOGIN/LOGOUT #####################

def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Log in the user if verified
            login(request, user)
            return redirect('home')
        else:
            # If the form raised our custom unverified error, resend the email
            username = request.POST.get('username')
            try:
                user = CustomUser.objects.get(username=username)
                if not user.is_verified:
                    from emails.utils import send_verification_email
                    send_verification_email(user, request)
                    messages.success(request, f"📧 Your account is not yetverified. A new verification link has been sent to {user.email}.")

            except CustomUser.DoesNotExist:
                pass  # do nothing for non-existent users
    else:
        form = CustomLoginForm()

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