from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import CustomUser
from django.contrib.auth import authenticate


CustomUser = get_user_model()

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email



# having a custom login form allows us to add custom validation
# like checking if the user is verified before allowing login
# and then sending a new verification email if not verified
class CustomLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        if not user.is_verified:
            raise forms.ValidationError(
                f"⛔ Your account is not verified. A new verification email has been sent to: {user.email}",
                code='unverified'
            )



#region ACCOUNT SETTINGS
# ------------------------------------------------------------

# --- Account Settings (username + icon) ---

# 30 Material Symbols names (no images needed)
ICON_CHOICES = [
    "restaurant","local_pizza","icecream","ramen_dining","bakery_dining",
    "sushi","emoji_food_beverage","coffee","brunch_dining","dinner_dining",
    "fastfood","takeout_dining","kitchen","set_meal","soup_kitchen",
    "cake","cookie","nutrition","rice_bowl","egg_alt",
    "espresso","flatware","breakfast_dining","wine_bar","liquor",
    "emoji_people","face","sentiment_satisfied","person","restaurant_menu"
]

class AccountProfileForm(forms.ModelForm):
    profile_icon = forms.ChoiceField(
        choices=[(i, i) for i in ICON_CHOICES],
        required=True,
        label="Profile icon"
    )

    class Meta:
        model = CustomUser
        fields = ["username", "profile_icon"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Nice labels/placeholders
        self.fields["username"].label = "Username"
        self.fields["username"].widget.attrs.update({"placeholder": "Your username"})

    def clean_username(self):
        username = self.cleaned_data["username"]
        qs = CustomUser.objects.filter(username__iexact=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username
    

#endregion
