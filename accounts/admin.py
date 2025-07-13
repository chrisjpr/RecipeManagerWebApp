from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from django.utils.translation import gettext_lazy as _
from .models import FriendRequest, Friendship



class CustomUserAdmin(UserAdmin):
    # Add 'friends' to the fieldsets (admin "Edit" page)
    fieldsets = UserAdmin.fieldsets + (
        (_('Friends'), {'fields': ('friends',)}),
    )


    list_display = UserAdmin.list_display + ('get_friend_count',)

    def get_friend_count(self, obj):
        return obj.friends.count()
    
    get_friend_count.short_description = 'Friends'

admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'created_at')
    search_fields = ('from_user__username', 'to_user__username')

@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('user', 'friend', 'created_at')
    search_fields = ('user__username', 'friend__username')