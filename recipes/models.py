from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User  # add at top



# Create your models here.
class Recipe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipes", null = True, blank = True)
    title = models.CharField(max_length=255)
    safe_title = models.SlugField(unique=True)
    cook_time = models.PositiveIntegerField()
    portions = models.CharField(max_length=50)
    image = models.ImageField(upload_to='recipe_images/', blank=True, null=True)
    instructions = models.JSONField()

    def __str__(self):
        return self.title

class IngredientCategory(models.Model):
    recipe = models.ForeignKey(Recipe, related_name='ingredient_categories', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = []  # No uniqueness constraints

    def __str__(self):
        return f"{self.name} ({self.recipe.title})"

class Ingredient(models.Model):
    category = models.ForeignKey(
        IngredientCategory,
        related_name='items',
        on_delete=models.CASCADE,
        blank=True,
        null=True)
    name = models.CharField(max_length=255)
    quantity = models.CharField(max_length=50, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    recipe = models.ForeignKey(Recipe, related_name='ingredients', on_delete=models.CASCADE, null=True, blank = True)

    

    def __str__(self):
        return f"{self.quantity or ''} {self.unit or ''} {self.name}"

