
# Register your models here.
from django.contrib import admin
from .models import InsurerEmailLog

@admin.register(InsurerEmailLog)
class InsurerEmailLogAdmin(admin.ModelAdmin):
    list_display = ("police_number", "insured_name", "birth_date", "start_date", "end_date", "to_email", "status", "created_at", "sent_at")
    search_fields = ("police_number", "insured_name", "to_email", "subject")
    list_filter = ("status", "created_at")
