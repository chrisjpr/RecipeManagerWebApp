from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.



class CustomUser(AbstractUser):
    # Add custom fields here if needed

    friends = models.ManyToManyField(
        'self',
        symmetrical=True,
        blank=True
    )
    pass