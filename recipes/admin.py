from django.contrib import admin
from .models import Recipe, Ingredient, IngredientCategory


# Register your models here.

# Inline for Ingredient (used inside IngredientCategory admin)
class IngredientInline(admin.TabularInline):
    model = Ingredient
    extra = 1

# Inline for IngredientCategory (used inside Recipe admin)
class IngredientCategoryInline(admin.StackedInline):
    model = IngredientCategory
    extra = 1
    show_change_link = True

# Register Recipe with inlines for IngredientCategories (not Ingredients directly!)
@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    inlines = [IngredientCategoryInline]
    list_display = ('title',)  # Add fields like source_url or created_at if they exist
    search_fields = ('title',)
    # list_filter = ('created_at',)  # Only include if `created_at` is defined on model

# Register IngredientCategory separately to manage its Ingredients
@admin.register(IngredientCategory)
class IngredientCategoryAdmin(admin.ModelAdmin):
    inlines = [IngredientInline]
    list_display = ('name', 'recipe')
    search_fields = ('name',)

# Optionally register Ingredient if needed
@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit')
    search_fields = ('name',)