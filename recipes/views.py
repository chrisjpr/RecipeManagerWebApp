

from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import viewsets
from .models import Recipe
from .serializers import RecipeSerializer
from django.contrib.auth.decorators import login_required




# Create your views here.

class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer


# Render a Recipe Template
def recipe_detail(request, slug):
    recipe = get_object_or_404(Recipe, safe_title=slug)
    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe
    })

# Render all Recipes
@login_required
def recipe_list(request):
    recipes = Recipe.objects.filter(user=request.user)
    return render(request, "recipes/recipe_list.html", {"recipes": recipes})

# specify homepage
@login_required
def home(request):
    recipes = Recipe.objects.filter(user=request.user)
    return render(request, 'recipes/home.html', {'recipes': recipes})


