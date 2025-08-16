from django.db import models

# Create your models here.
from django.conf import settings



class InsurerEmailLog(models.Model):
    # existing fields...
    insured_name = models.CharField(max_length=200)
    birth_date   = models.DateField(null=True, blank=True)

    # NEW / renamed fields – make them safe
    police_number = models.CharField(max_length=100, blank=True, default="")   # string default is fine
    start_date    = models.DateField(null=True, blank=True)                    # nullable, no prompt
    end_date      = models.DateField(null=True, blank=True)                    # nullable, no prompt
    sender_name   = models.CharField(max_length=200, default="Operations")     # default value
    to_email = models.EmailField(default= "vertrag@zurich.com")
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=[("sent", "sent"), ("failed", "failed")])
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.insured_name} → {self.to_email} on {self.created_at:%Y-%m-%d}"