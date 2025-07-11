from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings


# Create your models here.
class Recipe(models.Model):
    recipe_id = models.AutoField(primary_key=True, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recipes'
    )
    
    title = models.CharField(max_length=255)
    cook_time = models.PositiveIntegerField()
    portions = models.PositiveIntegerField()
    image = models.ImageField(upload_to='recipe_images/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title



class Ingredient(models.Model):
    ingredient_id = models.AutoField(primary_key=True, unique=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    recipe_id = models.ForeignKey(Recipe, related_name='ingredients', on_delete=models.CASCADE, null=True, blank=True)

    name = models.CharField(max_length=255)
    quantity = models.FloatField(max_length=50, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.quantity or ''} {self.unit or ''} {self.name}"


class Instruction(models.Model):
    instruction_id = models.AutoField(primary_key=True, unique=True)
    recipe_id = models.ForeignKey(Recipe, related_name='instructions', on_delete=models.CASCADE)
    step_number = models.PositiveIntegerField()
    description = models.TextField()

    class Meta:
        ordering = ['step_number']

    def __str__(self):
        return f"Step {self.step_number} for {self.recipe_id.title}"