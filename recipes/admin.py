from django.contrib import admin
from .models import Recipe, Ingredient, IngredientCategory


# Register your models here.

class IngredientInline(admin.TabularInline):
    model = Ingredient
    extra = 1
    fields = ['name', 'quantity', 'unit', 'category']
    autocomplete_fields = ['category']  # optional, for UX

class IngredientCategoryInline(admin.StackedInline):
    model = IngredientCategory
    extra = 1

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    inlines = [IngredientCategoryInline]
    list_display = ('title', 'user')
    search_fields = ('title',)
    exclude = ('user',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)


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