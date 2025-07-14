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

