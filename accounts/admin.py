from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from django.utils.translation import gettext_lazy as _
from .models import FriendRequest, Friendship


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Optional: show verification info if you're using it
    fieldsets = UserAdmin.fieldsets + (
        (_('Verification'), {'fields': ('is_verified', 'verification_code')}),
    )

    readonly_fields = ['get_friend_count']
    list_display = UserAdmin.list_display + ('get_friend_count', 'is_verified')

    def get_friend_count(self, obj):
        return Friendship.objects.filter(user=obj).count()
    
    get_friend_count.short_description = 'Friends'


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'created_at')
    search_fields = ('from_user__username', 'to_user__username')


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('user', 'friend', 'created_at')
    search_fields = ('user__username', 'friend__username')