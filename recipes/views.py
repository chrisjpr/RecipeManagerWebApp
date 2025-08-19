
import os
import django_rq
import redis
from rq.job import Job
from django_rq import get_connection
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
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
from django.urls import reverse
import json
from django.shortcuts import redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from accounts.models import CustomUser 

from .functions.pipelines import *  
from .functions.data_acquisition import *
from .forms import ParseWithLLMForm

ingredient_formset = IngredientFormSet(prefix="ingredients")
instruction_formset = InstructionFormSet(prefix="instructions")


# Helper function to safe enqueue a job

def get_safe_rq_queue(name: str = "default"):
    """
    Build a Redis connection using settings.REDIS_URL + settings.REDIS_SSL_OPTIONS
    so local dev with Heroku Redis (TLS) works, then return a Queue bound to it.
    """
    try:
        ssl_opts = getattr(settings, "REDIS_SSL_OPTIONS", {})
        conn = redis.Redis.from_url(settings.REDIS_URL, **ssl_opts)
        return django_rq.get_queue(name, connection=conn)
    except Exception as e:
        print("❌ Could not build Redis connection for RQ:", e)
        # Fallback to the default behavior (may fail in local TLS case, but keeps behavior unchanged)
        return django_rq.get_queue(name)


# Create your views here.


# specify homepage

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()
try:
    # adjust import path to wherever your Friendship model lives
    from accounts.models import Friendship
except Exception:
    Friendship = None


def _friend_users_for(user):
    """
    Return a queryset of CustomUser friends for `user`,
    handling either a direct M2M to User or a Friendship through-model.
    """
    # Case A: direct M2M to the user model (user.friends is a manager of User)
    if hasattr(user, "friends") and getattr(user.friends, "model", None) is User:
        return user.friends.all().order_by("username")

    # Case B: Friendship model with user<->friend links
    if Friendship is not None:
        # Collect the other side's user IDs
        pairs = Friendship.objects.filter(
            Q(user=user) | Q(friend=user)
        ).values_list("user_id", "friend_id")

        uid = user.id
        friend_ids = []
        for u_id, f_id in pairs:
            friend_ids.append(f_id if u_id == uid else u_id)

        # de-duplicate while preserving order
        seen = set()
        friend_ids = [fid for fid in friend_ids if not (fid in seen or seen.add(fid))]

        if not friend_ids:
            return User.objects.none()
        # return actual users, ordered by username
        return User.objects.filter(id__in=friend_ids).order_by("username")

    # Fallback: no friends at all
    return User.objects.none()


@login_required
def home(request):
    recipes = (
        Recipe.objects.filter(user=request.user).order_by("-created_at")[:10]
    )

    random_images = (
        Recipe.objects.filter(visibility="public")
        .exclude(image="")
        .order_by("?")[:12]
    )

    friends = _friend_users_for(request.user)

    return render(
        request,
        "recipes/home.html",
        {
            "recipes": recipes,
            "random_images": random_images,
            "friends": friends,
        },
    )
    

#region BACKGR JOB STATUS
######################### BACKGROUND JOB STATUS #########################  
# views.py — imports (add if missing)
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django_rq import get_connection
from rq.job import Job

@require_GET
@login_required
def job_status(request):
    job_id = request.GET.get("job_id")
    if not job_id:
        return JsonResponse({"status": "error", "message": "job_id missing"}, status=400)

    try:
        conn = get_connection("default")
        job = Job.fetch(job_id, connection=conn)
    except Exception:
        return JsonResponse({"status": "error", "message": "invalid job_id"}, status=404)

    if job.is_finished:
        result = job.result or {}
        # ensure we return a dict even if result isn't one
        payload = {"status": "finished"}
        if isinstance(result, dict):
            payload.update(result)
        return JsonResponse(payload)

    if job.is_failed:
        meta = getattr(job, "meta", {}) or {}
        return JsonResponse({
            "status": "failed",
            "error_code": meta.get("error_code", "unknown"),
            "error_message": meta.get("error_message", "Import failed.")
        })

    if job.is_started:
        return JsonResponse({"status": "started"})

    # queued/deferred
    return JsonResponse({"status": "queued"})


########################### /JOB STATUS #########################
#endregion JOB STATUS


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

        # ✅ Preserve pagination & sorting (page, sort, dir) on redirect
        querystring = request.GET.urlencode()
        redirect_url = reverse('recipes:recipe_list')
        if querystring:
            redirect_url = f"{redirect_url}?{querystring}"
        return redirect(redirect_url)
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

    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        recipe.delete()
        # ✅ Go back to where the user was (page/sort preserved)
        if next_url:
            return redirect(next_url)
        return redirect('recipes:recipe_list')

    return render(
        request,
        'recipes/recipe_confirm_delete.html',
        {
            'recipe': recipe,
            'next': next_url,
            'recipe_list_url': reverse('recipes:recipe_list'),
        }
    )



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
# views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

@login_required
def add_recipe_from_url(request):
    if request.method == 'POST':
        url = request.POST.get('recipe_url')
        transform_vegan = request.POST.get('transform_vegan') == 'on'
        custom_instruction = request.POST.get('custom_instruction', '')
        custom_title = request.POST.get('custom_title', '')

        try:
            queue = get_safe_rq_queue('default')
            job = queue.enqueue(
                'recipes.tasks.process_recipe_from_url',
                request.user.id,
                url,
                transform_vegan,
                custom_instruction,
                custom_title
            )
            messages.success(request, "✅ Import request was succesfullys bumitted. It can take a few minutes. If something goes wrong with the import, you will be notified.")
            resp = redirect('recipes:recipe_list')

            # append job id into cookie (comma-separated), ~15 minutes
            existing = request.COOKIES.get('last_import_job')
            val = job.id if not existing else f"{existing},{job.id}"
            resp.set_cookie('last_import_job', val, max_age=900, samesite='Lax')
            return resp

        except Exception as e:
            print("❌ Error enqueueing add_recipe_from_url:", e)
            messages.error(request, "❌ The recipe generation services are currently in maintenance. Try again later!")
            return redirect('recipes:recipe_list')

    # GET: render the form page
    return render(request, 'recipes/add_recipe_from_url.html')

# views.py
@login_required
def add_recipe_from_image(request):
    if request.method == 'POST':
        images = request.FILES.getlist('images')
        transform_vegan = request.POST.get('transform_vegan') == 'on'
        custom_instruction = request.POST.get('custom_instruction', '')
        custom_title = request.POST.get('custom_title', '')

        try:
            images_as_bytes = []
            for f in images:
                b = f.read()
                if b:
                    images_as_bytes.append(b)

            queue = get_safe_rq_queue('default')
            job = queue.enqueue(
                'recipes.tasks.process_recipe_from_image',
                request.user.id,
                images_as_bytes,
                transform_vegan,
                custom_instruction,
                custom_title,
            )

            messages.success(request, "✅ Import request was succesfullys bumitted. It can take a few minutes. If something goes wrong with the import, you will be notified.")
            resp = redirect('recipes:recipe_list')

            existing = request.COOKIES.get('last_import_job')
            val = job.id if not existing else f"{existing},{job.id}"
            resp.set_cookie('last_import_job', val, max_age=900, samesite='Lax')
            return resp

        except Exception as e:
            print("❌ Error enqueueing add_recipe_from_image:", e)
            messages.error(request, "❌ The recipe generation services are currently in maintenance. Try again later!")
            return redirect('recipes:recipe_list')

    # GET: render the form page
    return render(request, 'recipes/add_recipe_from_image.html')


# views.py
@login_required
def add_recipe_from_text(request):
    if request.method == 'POST':
        form = ParseWithLLMForm(request.POST)
        if form.is_valid():
            raw_text = form.cleaned_data['raw_recipe_text']
            use_llm = form.cleaned_data['use_llm']
            custom_instruction = form.cleaned_data['custom_instruction']
            try:
                queue = get_safe_rq_queue('default')
                job = queue.enqueue(
                    'recipes.tasks.process_recipe_from_text',
                    request.user.id,
                    raw_text,
                    use_llm,
                    custom_instruction,
                )
                messages.success(request, "✅ Import request was succesfullys bumitted. It can take a few minutes. If something goes wrong with the import, you will be notified.")
                resp = redirect('recipes:recipe_list')

                existing = request.COOKIES.get('last_import_job')
                val = job.id if not existing else f"{existing},{job.id}"
                resp.set_cookie('last_import_job', val, max_age=900, samesite='Lax')
                return resp

            except Exception as e:
                print("❌ Error enqueueing add_recipe_from_text:", e)
                messages.error(request, "❌ The recipe generation services are currently in maintenance. Try again later!")
                return redirect('recipes:recipe_list')
        else:
            messages.error(request, "Please correct the form errors.")
            # fall through to GET render with the bound form below
    else:
        form = ParseWithLLMForm()

    # GET (or invalid POST): render the form page
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
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')

    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    # Final fallback (adjust to whatever makes sense in your app)
    return redirect("recipes:friends_list")  # or friends_recipes, etc.

###################### /FRIEND MANAGEMENT #####################


#region PUBLIC RECIPES
####################### PUBLIC RECIPES #######################
@login_required
def public_recipes(request):
    # Sorting (default: created_at desc)
    sort_field = request.GET.get('sort') or 'created_at'
    direction = request.GET.get('dir') or 'desc'
    order_expr = sort_field if direction == 'asc' else f'-{sort_field}'

    # All public recipes EXCEPT the current user's
    recipes_qs = (
        Recipe.objects
        .filter(visibility='public')
        .exclude(user=request.user)
        .order_by(order_expr)
        .prefetch_related('ingredients')
    )

    # Ingredient suggestions (lowercased/distinct), like friends_recipes
    all_ingredients = Ingredient.objects.filter(
        recipe__in=recipes_qs
    ).values_list('name', flat=True).distinct()
    all_ingredients = sorted({name.lower() for name in all_ingredients})

    # Pagination (10 per page, consistent with your other lists)
    paginator = Paginator(recipes_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Build CSV for client-side ingredient filtering
    for recipe in page_obj:
        ingredient_list = [ing.name for ing in recipe.ingredients.all()]
        recipe.ingredients_csv = ", ".join(ingredient_list)

    return render(request, 'recipes/public_recipes.html', {
        'page_obj': page_obj,
        'current_sort': sort_field,
        'current_dir': direction,
        'all_ing_json': json.dumps(all_ingredients),
    })
####################### /PUBLIC RECIPES #######################
#endregion PUBLIC RECIPES




#region PDF EXPORT
######################### PDF EXPORT ########################


# recipes/views.py
from io import BytesIO
from django.http import HttpResponse, HttpResponseForbidden
from xhtml2pdf import pisa
from django.contrib.staticfiles import finders
from django.template.loader import get_template

import os

from .models import Recipe

def user_can_view_recipe(user, recipe):
    if recipe.visibility == "public":
        return True
    if user.is_authenticated and recipe.user_id == user.id:
        return True
    # add any "friends" rules here if you have them
    return False

def _is_abs(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def _strip_prefix(s: str, prefix: str) -> str:
    return s[len(prefix):] if s.startswith(prefix) else s


def _link_callback(uri: str, rel: str | None):
    """
    Resolve URIs in HTML so xhtml2pdf can load assets.

    - If the URI is absolute (http/https), return it unchanged (let xhtml2pdf fetch it).
    - If MEDIA_URL/STATIC_URL are absolute (CDN/S3) and the URI starts with them, return the URI unchanged.
    - If MEDIA_URL/STATIC_URL are relative, map to MEDIA_ROOT/STATIC_ROOT or use staticfiles finders.
    - For other relative paths, resolve against 'rel' (the current template directory).
    - Never raise FileNotFoundError; fall back to returning the original URI so xhtml2pdf can try.
    """
    if not uri:
        return uri

    # 1) Fully-qualified external URL?
    if _is_abs(uri):
        return uri

    # 2) MEDIA_URL handling (S3/CDN vs local)
    media_url = getattr(settings, "MEDIA_URL", "") or ""
    if media_url:
        if _is_abs(media_url) and uri.startswith(media_url):
            # S3/CDN media → leave as is
            return uri
        if uri.startswith(media_url):
            candidate = os.path.join(settings.MEDIA_ROOT, _strip_prefix(uri, media_url))
            if os.path.isfile(candidate):
                return candidate

    # 3) STATIC_URL handling (CDN vs local)
    static_url = getattr(settings, "STATIC_URL", "") or ""
    if static_url:
        if _is_abs(static_url) and uri.startswith(static_url):
            # CDN static → leave as is
            return uri
        if uri.startswith(static_url):
            # Try collectstatic path
            found = finders.find(_strip_prefix(uri, static_url))
            if found:
                return found
            candidate = os.path.join(getattr(settings, "STATIC_ROOT", "") or "", _strip_prefix(uri, static_url))
            if candidate and os.path.isfile(candidate):
                return candidate

    # 4) Relative path: resolve against template directory if provided
    if rel and not os.path.isabs(uri):
        base_dir = os.path.dirname(rel)
        candidate = os.path.normpath(os.path.join(base_dir, uri))
        if os.path.isfile(candidate):
            return candidate

    # 5) Last resort: return the original string and let xhtml2pdf try
    return uri

def recipe_pdf(request, recipe_id):
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related("ingredients", "instructions"),
        recipe_id=recipe_id
    )
    if not user_can_view_recipe(request.user, recipe):
        return HttpResponseForbidden("You don't have access to this recipe.")

    # Optional: convenience attribute if your template wants it
    recipe.ingredients_csv = ", ".join(i.name for i in recipe.ingredients.all())

    template = get_template("recipes/recipe_pdf_xhtml2pdf.html")
    html = template.render({"recipe": recipe, "request": request})

    result = BytesIO()
    pdf_status = pisa.CreatePDF(html, dest=result, link_callback=_link_callback)
    if pdf_status.err:
        return HttpResponse("Error rendering PDF", status=500)

    filename = f'{slugify(recipe.title or "recipe")}.pdf'
    resp = HttpResponse(result.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


######################### /PDF EXPORT ########################



