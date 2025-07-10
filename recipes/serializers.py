from rest_framework import serializers
from .models import Recipe, IngredientCategory, Ingredient

class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'quantity', 'unit']

class IngredientCategorySerializer(serializers.ModelSerializer):
    items = IngredientSerializer(many=True)

    class Meta:
        model = IngredientCategory
        fields = ['id', 'name', 'items']

class RecipeSerializer(serializers.ModelSerializer):
    ingredient_categories = IngredientCategorySerializer(many=True)

    class Meta:
        model = Recipe
        fields = ['id', 'title', 'safe_title', 'cook_time', 'portions', 'image', 'instructions', 'ingredient_categories']