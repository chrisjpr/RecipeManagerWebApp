

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
from accounts.models import Friendship
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model 


from .functions.pipelines import *  
from .functions.data_acquisition import *
from .forms import ParseWithLLMForm

ingredient_formset = IngredientFormSet(prefix="ingredients")
instruction_formset = InstructionFormSet(prefix="instructions")

# Create your views here.

# specify homepage
@login_required
def home(request):
    recipes = Recipe.objects.filter(user=request.user).order_by('-created_at')[:10] if request.user.is_authenticated else []
    random_images = Recipe.objects.exclude(image='').order_by('?')[:12]  # For rotator
    return render(request, 'recipes/home.html', {
        'recipes': recipes,
        'random_images': random_images,
    })


#region MANAGE RECIPES
########################## MANAGING RECIPES ##########################

# landing page for creating a recipe
@login_required
def create_recipe_landing(request):
    return render(request, "recipes/create_recipe_landing.html")


# Render a Recipe Template
def recipe_detail(request, recipe_id):
    recipe = get_object_or_404(Recipe, recipe_id=recipe_id)
    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe
    })

# Render all Recipes
@login_required
def recipe_list(request):
    recipes_qs = Recipe.objects.filter(user=request.user)
    # Determine sorting field and direction from query params (default: created_at desc)
    sort_field = request.GET.get('sort')
    direction = request.GET.get('dir', 'asc')
    if not sort_field:
        sort_field = 'created_at'
        direction = 'desc'
    order_by_expr = sort_field if direction == 'asc' else f'-{sort_field}'
    recipes_qs = recipes_qs.order_by(order_by_expr).prefetch_related('ingredients')
    # Get all ingredient names for this user's recipes (for dynamic suggestions)
    all_names = Ingredient.objects.filter(recipe__user=request.user).values_list('name', flat=True).distinct()
    all_names = sorted({name.lower() for name in all_names})
    # Paginate the recipes queryset (e.g., 10 per page)
    paginator = Paginator(recipes_qs, 10)  # :contentReference[oaicite:10]{index=10}
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)  # returns a Page object for the given page
    # Attach a comma-separated ingredients list to each recipe (for data-ingredients attribute)
    for recipe in page_obj:
        ingredient_list = [ing.name for ing in recipe.ingredients.all()]
        recipe.ingredients_csv = ", ".join(ingredient_list)
    # Handle bulk visibility update if form submitted
    if request.method == 'POST':
        recipe_ids = request.POST.getlist("recipe_ids")
        if not recipe_ids:
            messages.error(request, "No recipes found for update.")
            return redirect('recipes:recipe_list')
        updated_count = 0
        for rid in recipe_ids:
            visibility = request.POST.get(f'visibility_{rid}')
            if visibility:
                try:
                    recipe = Recipe.objects.get(recipe_id=int(rid), user=request.user)
                    recipe.visibility = visibility
                    recipe.save()
                    updated_count += 1
                except Recipe.DoesNotExist:
                    messages.warning(request, f"Failed to update recipe ID {rid}.")
            else:
                messages.warning(request, f"No visibility selected for recipe ID {rid}.")
        if updated_count:
            messages.success(request, f"✅ Updated visibility for {updated_count} recipe(s).")
        else:
            messages.info(request, "No recipes were updated.")
        return redirect('recipes:recipe_list')
    # Render template with all needed context
    return render(request, 'recipes/recipe_list.html', {
        'page_obj': page_obj,
        'current_sort': sort_field,
        'current_dir': direction,
        'all_ing_json': json.dumps(all_names)
    })

@require_POST
@login_required
def update_visibility_ajax(request):
    try:
        data = json.loads(request.body)
        recipe_id = data.get("recipe_id")
        visibility = data.get("visibility")

        recipe = get_object_or_404(Recipe, recipe_id=recipe_id, user=request.user)
        recipe.visibility = visibility
        recipe.save()

        return JsonResponse({"status": "success"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})



@login_required
def recipe_delete(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.user != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        recipe.delete()
        return redirect('recipes:recipe_list')
    return render(request, 'recipes/recipe_confirm_delete.html', {'recipe': recipe})


@login_required
def recipe_edit(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.user != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        recipe_form = RecipeForm(request.POST, request.FILES, instance=recipe)
        ingredient_formset = IngredientFormSet(request.POST, instance=recipe, prefix="ingredients", user=request.user)
        instruction_formset = InstructionFormSet(request.POST, instance=recipe, prefix="instructions")

        # ✅ Skip empty instruction forms
        for form in instruction_formset.forms:
            if not form.data.get(form.add_prefix('description')) and not form.data.get(form.add_prefix('step_number')):
                form.empty_permitted = True

        if recipe_form.is_valid() and ingredient_formset.is_valid() and instruction_formset.is_valid():
            recipe_form.save()
            ingredient_formset.save()
            instruction_formset.save()
            return redirect('recipes:recipe_detail', recipe_id=recipe.recipe_id)
        else:
            print("Recipe form errors:", recipe_form.errors)
            print("Ingredient formset errors:", ingredient_formset.errors)
            print("Instruction formset errors:", instruction_formset.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        recipe_form = RecipeForm(instance=recipe)
        ingredient_formset = IngredientFormSet(instance=recipe, prefix="ingredients", user=request.user)
        instruction_formset = InstructionFormSet(instance=recipe, prefix="instructions")

    return render(request, 'recipes/edit_recipe.html', {
        "recipe_form": recipe_form,
        "ingredient_formset": ingredient_formset,
        "instruction_formset": instruction_formset,
        "recipe": recipe
    })
########################## MANAGING RECIPES ##########################
#endregion MANAGING RECIPES


#region MANUAL RECIPE CREATION
##################  MANUAL RECIPE CREATION ##################
@login_required
def create_recipe(request):
    use_llm = False  # default for GET or manual

    if request.method == 'POST':
        recipe_form = RecipeForm(request.POST, request.FILES)
        ingredient_formset = IngredientFormSet(request.POST, prefix="ingredients")
        instruction_formset = InstructionFormSet(request.POST, prefix="instructions")

        use_llm = request.POST.get("use_llm") == "ai"
        transform_vegan = request.POST.get("transform_vegan") == "on"
        custom_instruction = request.POST.get("custom_instruction", "")

        # ✅ Skip empty instruction forms
        for form in instruction_formset.forms:
            if not form.data.get(form.add_prefix('description')) and not form.data.get(form.add_prefix('step_number')):
                form.empty_permitted = True

        if use_llm:
            ingredients_text = request.POST.get('ingredients_text', '')
            instructions_text = request.POST.get('instructions_text', '')

            ingredients = [line.strip() for line in ingredients_text.splitlines() if line.strip()]
            instructions = [line.strip() for line in instructions_text.splitlines() if line.strip()]

            raw_data = {
                "ingredients": ingredients,
                "instructions": instructions
            }

            if recipe_form.is_valid():
                try:
                    structured_data = organize_with_llm(
                        data=raw_data,
                        api_key=os.getenv("OPENAI_KEY"),
                        transform_vegan=transform_vegan,
                        custom_instructions=custom_instruction
                    )

                    recipe = Recipe.objects.create(
                        user=request.user,
                        title=recipe_form.cleaned_data.get("title"),
                        cook_time=recipe_form.cleaned_data.get("cook_time") or 0,
                        portions=recipe_form.cleaned_data.get("portions") or 1,
                        notes=recipe_form.cleaned_data.get("notes", ""),
                        image=recipe_form.cleaned_data.get("image")
                    )

                    for group in structured_data.get("ingredients", []):
                        for item in group.get("items", []):
                            Ingredient.objects.create(
                                recipe=recipe,
                                name=item.get("name", ""),
                                quantity=float(item.get("quantity") or 0),
                                unit=item.get("unit", ""),
                                category=group.get("category", "")
                            )

                    for i, step in enumerate(structured_data.get("instructions", []), start=1):
                        Instruction.objects.create(
                            recipe_id=recipe,
                            step_number=i,
                            description=step
                        )

                    messages.success(request, f"✅ Recipe '{recipe.title}' created via LLM.")
                    return redirect('recipes:recipe_detail', recipe_id=recipe.recipe_id)

                except Exception as e:
                    print("❌ LLM error:", repr(e))
                    messages.error(request, f"Failed to parse and save recipe using LLM: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors above.")
        else:
            # Manual input path
            if recipe_form.is_valid() and ingredient_formset.is_valid() and instruction_formset.is_valid():
                recipe = recipe_form.save(commit=False)
                recipe.user = request.user
                recipe.save()

                ingredient_formset.instance = recipe
                instruction_formset.instance = recipe
                ingredient_formset.save()
                instruction_formset.save()

                messages.success(request, f"✅ Recipe '{recipe.title}' created.")
                return redirect('recipes:recipe_detail', recipe_id=recipe.recipe_id)

            messages.error(request, "Please correct the errors below.")

    else:
        recipe_form = RecipeForm()
        ingredient_formset = IngredientFormSet(prefix="ingredients")
        instruction_formset = InstructionFormSet(prefix="instructions")

    return render(request, "recipes/create_recipe.html", {
        "recipe_form": recipe_form,
        "ingredient_formset": ingredient_formset,
        "instruction_formset": instruction_formset
    })


##################  MANUAL RECIPE CREATION ##################  
#endregion


#region AI RECIPES
################## AI RECIPE FEATURES ##################

@login_required
def add_recipe_from_url(request):
    if request.method == 'POST':
        url = request.POST.get('recipe_url')
        transform_vegan = request.POST.get('transform_vegan') == 'on'
        custom_instruction = request.POST.get('custom_instruction', '')
        custom_title = request.POST.get('custom_title', '')

        try:
            # Get structured data + image
            structured_data, image_bytes = get_data_from_url(
                url=url,
                api_key= os.getenv("OPENAI_KEY"),
                transform_vegan=transform_vegan,
                custom_instructions=custom_instruction
            )

            # Optionally override title
            if custom_title:
                structured_data['title'] = custom_title

            # Save to DB with image
            recipe = save_structured_recipe_to_db(
                data=structured_data,
                user=request.user,
                image_bytes=image_bytes
            )

            messages.success(request, f"🎉 Recipe '{recipe.title}' created from URL!")
            return redirect('recipes:recipe_detail', recipe_id=recipe.recipe_id)

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
                api_key=os.getenv("OPENAI_KEY"),
                transform_vegan=transform_vegan,
                custom_instruction=custom_instruction,
                custom_title=custom_title,
                return_image_bytes=True
            )

            best_image_bytes = crop_image_to_visible_area(best_image_bytes) if best_image_bytes else None

            # Save recipe
            recipe = save_structured_recipe_to_db(
                data=structured_data,
                user=request.user,
                image_bytes=best_image_bytes
            )

            messages.success(request, f"📷 Recipe '{recipe.title}' created from image!")
            return redirect('recipes:recipe_detail', recipe_id=recipe.recipe_id)

        except Exception as e:
            print("❌ Error in add_recipe_from_image:", e)
            messages.error(request, "Error while creating recipe from image.")

    return render(request, 'recipes/add_recipe_from_image.html')




@login_required
def add_recipe_from_text(request):
    if request.method == 'POST':
        form = ParseWithLLMForm(request.POST)
        if form.is_valid():
            raw_text = form.cleaned_data['raw_recipe_text']
            use_llm = form.cleaned_data['use_llm']
            custom_instruction = form.cleaned_data['custom_instruction']

            try:
                if use_llm:
                    structured_data = organize_with_llm(
                        recipe_input=raw_text,
                        custom_instruction=custom_instruction,
                        api_key=os.getenv("OPENAI_KEY")
                    )
                else:
                    structured_data = {
                        "title": "Untitled Recipe",
                        "ingredients": [],
                        "instructions": [],
                        "notes": "",
                        "raw_text": raw_text,
                    }

                recipe = save_structured_recipe_to_db(
                    data=structured_data,
                    user=request.user,
                    image_bytes=None  # no image from text input
                )

                messages.success(request, f"✅ Recipe '{recipe.title}' created!")
                return redirect('recipes:recipe_detail', recipe_id=recipe.recipe_id)

            except Exception as e:
                print("❌ Error in add_recipe_from_text:", e)
                messages.error(request, "Error while creating recipe from text input.")

    else:
        form = ParseWithLLMForm()

    return render(request, 'recipes/add_recipe_from_text.html', {"form": form})

################## /AI RECIPE FEATURES ##################

#endregion



#region FRIEND MANAGEMENT
###################### FRIEND MANAGEMENT #####################
@login_required
def friends_recipes(request, friend_id):
    if not Friendship.objects.filter(user=request.user, friend_id=friend_id).exists():
        return HttpResponseForbidden("You are not friends with this user.")

    # Fetch the full User object for display
    friend = get_object_or_404(get_user_model(), id=friend_id)

    sort_field = request.GET.get('sort') or 'created_at'
    direction = request.GET.get('dir') or 'desc'
    order_expr = sort_field if direction == 'asc' else f'-{sort_field}'

    recipes_qs = Recipe.objects.filter(
        user_id=friend_id,
        visibility__in=['friends', 'public']
    ).order_by(order_expr).prefetch_related('ingredients')

    all_ingredients = Ingredient.objects.filter(
        recipe__in=recipes_qs
    ).values_list('name', flat=True).distinct()
    all_ingredients = sorted({name.lower() for name in all_ingredients})

    paginator = Paginator(recipes_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for recipe in page_obj:
        ingredient_list = [ing.name for ing in recipe.ingredients.all()]
        recipe.ingredients_csv = ", ".join(ingredient_list)

    return render(request, 'recipes/friends_recipes.html', {
        'page_obj': page_obj,
        'current_sort': sort_field,
        'current_dir': direction,
        'all_ing_json': json.dumps(all_ingredients),
        'friend_id': friend_id,
        'friend': friend  # ✅ Now passed to the template
    })

@login_required
def copy_recipe(request, recipe_id):
    original = get_object_or_404(Recipe, recipe_id=recipe_id)
    if original.visibility not in ['friends', 'public']:
        return HttpResponseForbidden("Not allowed to copy this recipe.")
    
    copied = Recipe.objects.create(
        title=original.title,
        cook_time=original.cook_time,
        portions=original.portions,
        image=original.image,
        notes=original.notes,
        user=request.user,
        visibility='private',
    )
    for ing in original.ingredients.all():
        copied.ingredients.create(
            name=ing.name,
            quantity=ing.quantity,
            unit=ing.unit,               # <-- This line fixes the issue
            category=ing.category
        )
    for inst in original.instructions.all():
        copied.instructions.create(description=inst.description, step_number=inst.step_number)
    
    messages.success(request, "Recipe copied!")
    return redirect('recipes:friends_recipes', friend_id=original.user_id)

###################### /FRIEND MANAGEMENT #####################
