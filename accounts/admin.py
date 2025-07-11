from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from django.utils.translation import gettext_lazy as _



class CustomUserAdmin(UserAdmin):
    # Add 'friends' to the fieldsets (admin "Edit" page)
    fieldsets = UserAdmin.fieldsets + (
        (_('Friends'), {'fields': ('friends',)}),
    )

    # Optional: Show 'friends' on the list display or add/edit forms
    filter_horizontal = ('friends',)

    list_display = UserAdmin.list_display + ('get_friend_count',)

    def get_friend_count(self, obj):
        return obj.friends.count()
    
    get_friend_count.short_description = 'Friends'

admin.site.register(CustomUser, CustomUserAdmin)