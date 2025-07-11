

from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import viewsets
from .models import Recipe
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .forms import RecipeForm, IngredientFormSet, InstructionFormSet
from django.contrib import messages
from .forms import AddRecipeForm
from .models import Recipe, Ingredient, Instruction
from django.conf import settings

from functions.pipelines import *  
from functions.data_acquisition import *

ingredient_formset = IngredientFormSet(prefix="ingredients")
instruction_formset = InstructionFormSet(prefix="instructions")

# Create your views here.


# Render a Recipe Template
def recipe_detail(request, recipe_id):
    recipe = get_object_or_404(Recipe, recipe_id=recipe_id)
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


@login_required
def recipe_delete(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.user != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        recipe.delete()
        return redirect('recipe_list')
    return render(request, 'recipes/recipe_confirm_delete.html', {'recipe': recipe})


@login_required
def recipe_edit(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.user != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        recipe_form = RecipeForm(request.POST, request.FILES, instance=recipe)
        ingredient_formset = IngredientFormSet(request.POST, instance=recipe, prefix="ingredients")
        instruction_formset = InstructionFormSet(request.POST, instance=recipe, prefix="instructions")

        if recipe_form.is_valid() and ingredient_formset.is_valid() and instruction_formset.is_valid():
            recipe_form.save()
            ingredient_formset.save()
            instruction_formset.save()
            return redirect('recipe_detail', recipe_id=recipe.recipe_id)
        else:
            print("Recipe form errors:", recipe_form.errors)
            print("Ingredient formset errors:", ingredient_formset.errors)
            print("Instruction formset errors:", instruction_formset.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        recipe_form = RecipeForm(instance=recipe)
        ingredient_formset = IngredientFormSet(instance=recipe, prefix="ingredients")
        instruction_formset = InstructionFormSet(instance=recipe, prefix="instructions")

    return render(request, 'recipes/edit_recipe.html', {
        "recipe_form": recipe_form,
        "ingredient_formset": ingredient_formset,
        "instruction_formset": instruction_formset,
        "recipe": recipe
    })

#region Manual Recipe Creation

################## Create Recipe Manually ######### #########
@login_required
def create_recipe(request):
    if request.method == 'POST':
        recipe_form = RecipeForm(request.POST, request.FILES)
        ingredient_formset = IngredientFormSet(request.POST, prefix="ingredients")
        instruction_formset = InstructionFormSet(request.POST, prefix="instructions")

        if recipe_form.is_valid() and ingredient_formset.is_valid() and instruction_formset.is_valid():
            recipe = recipe_form.save(commit=False)
            recipe.user = request.user
            recipe.save()

            ingredient_formset.instance = recipe
            instruction_formset.instance = recipe

            ingredient_formset.save()
            instruction_formset.save()

            return redirect('home')
        else:
            # You MUST return a response here
            return render(request, "recipes/create_recipe.html", {
                "recipe_form": recipe_form,
                "ingredient_formset": ingredient_formset,
                "instruction_formset": instruction_formset
            })

    else:  # GET request
        recipe_form = RecipeForm()
        ingredient_formset = IngredientFormSet(prefix="ingredients")
        instruction_formset = InstructionFormSet(prefix="instructions")
        return render(request, "recipes/create_recipe.html", {
            "recipe_form": recipe_form,
            "ingredient_formset": ingredient_formset,
            "instruction_formset": instruction_formset
        })
    

#region AI Data Retrieval
################## AI DATA RETRIEVAL ##################

@login_required
def add_recipe_from_url(request):
    if request.method == 'POST':
        url = request.POST.get('recipe_url')
        transform_vegan = request.POST.get('transform_vegan') == 'on'
        custom_instruction = request.POST.get('custom_instruction', '')
        custom_title = request.POST.get('custom_title', '')

        try:
            # Get structured data from URL via GPT
            structured_data = get_data_from_url(
                url=url,
                api_key=settings.OPENAI_API_KEY,
                html_dir='.',  # update if needed
                transform_vegan=transform_vegan,
                custom_instructions=custom_instruction
            )

            # Optionally override title
            if custom_title:
                structured_data['title'] = custom_title

            # Save to DB
            recipe = save_structured_recipe_to_db(structured_data, user=request.user)

            messages.success(request, f"🎉 Recipe '{recipe.title}' created from URL!")
            return redirect('recipe_detail', recipe_id=recipe.recipe_id)

        except Exception as e:
            print("❌ Error in add_recipe_from_url:", e)
            messages.error(request, "Error while creating recipe from URL.")
    
    return render(request, 'recipes/add_recipe_from_url.html')


@login_required
def add_recipe_from_image(request):
    if request.method == 'POST':
        images = request.FILES.getlist('images')
        transform_vegan = request.POST.get('transform_vegan') == 'on'
        custom_instruction = request.POST.get('custom_instruction', '')
        custom_title = request.POST.get('custom_title', '')

        try:
            # Extract data from image via GPT-4o
            structured_data, best_image_bytes = get_data_from_image(
                images=images,
                api_key=settings.OPENAI_API_KEY,
                html_dir='.',  # update as needed
                transform_vegan=transform_vegan,
                custom_instruction=custom_instruction,
                custom_title=custom_title,
                return_image_bytes=True
            )

            # Save recipe
            recipe = save_structured_recipe_to_db(
                data=structured_data,
                user=request.user,
                image_bytes=best_image_bytes
            )

            messages.success(request, f"📷 Recipe '{recipe.title}' created from image!")
            return redirect('recipe_detail', recipe_id=recipe.recipe_id)

        except Exception as e:
            print("❌ Error in add_recipe_from_image:", e)
            messages.error(request, "Error while creating recipe from image.")

    return render(request, 'recipes/add_recipe_from_image.html')
################## /AI DATA RETRIEVAL ##################

#endregion AI Data Retrieval