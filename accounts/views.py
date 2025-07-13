


from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .forms import RegisterForm
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import FriendRequest, Friendship, CustomUser
from django.contrib.auth.models import User
from django.db.models import Q


# Create your views here.


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')  # Redirect to login after successful registration
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})



def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return render(request, 'registration/logout.html')


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