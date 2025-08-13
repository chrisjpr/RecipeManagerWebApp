import os
from io import BytesIO
from django.conf import settings
from django.contrib.auth import get_user_model

# Use the same imports you use in views.py so signatures match
from .functions.pipelines import (
    get_data_from_url,
    get_data_from_image,
    save_structured_recipe_to_db,
)
from .functions.data_acquisition import (
    organize_with_llm,
    crop_image_to_visible_area,
)


def _openai_key():
    # env first, then settings attr (works locally & on Heroku)
    return os.getenv("OPENAI_KEY") or getattr(settings, "OPENAI_KEY", None)


def process_recipe_from_url(user_id, url, transform_vegan, custom_instruction, custom_title):
    """
    Background job for add_recipe_from_url.
    Uses your existing get_data_from_url + save_structured_recipe_to_db.
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"📥 [TASK] URL import started for user={user_id} url={url}")

    # 1) fetch + LLM organize + optional image download (your function)
    data, image_bytes = get_data_from_url(
        url=url,
        api_key=_openai_key(),
        transform_vegan=transform_vegan,
        custom_instructions=custom_instruction,
    )

    # Title override (same logic you do in views)
    if custom_title:
        data["title"] = custom_title

    # 2) Save to DB
    recipe = save_structured_recipe_to_db(
        data=data,
        user=user,
        image_bytes=image_bytes,
    )

    print(f"✅ [TASK] URL import done: {recipe.title} (id={recipe.recipe_id})")
    return {"ok": True, "recipe_id": recipe.recipe_id, "title": recipe.title}


def process_recipe_from_image(user_id, images_bytes_list, transform_vegan, custom_instruction, custom_title):
    """
    Background job for add_recipe_from_image.
    Accepts a list of BYTES (not InMemoryUploadedFile), wraps them into BytesIO so your code can .read().
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"🖼️ [TASK] Image import started for user={user_id} images={len(images_bytes_list)}")

    # Convert bytes -> BytesIO to satisfy extract_recipe_from_images loop using .read()
    images_filelikes = [BytesIO(b) for b in images_bytes_list]

    structured_data, best_image_bytes = get_data_from_image(
        images=images_filelikes,
        api_key=_openai_key(),
        transform_vegan=transform_vegan,
        custom_instruction=custom_instruction,
        custom_title=custom_title,
        return_image_bytes=True,
    )

    # Keep your extra crop step (you do this in the view)
    best_image_bytes = crop_image_to_visible_area(best_image_bytes) if best_image_bytes else None

    recipe = save_structured_recipe_to_db(
        data=structured_data,
        user=user,
        image_bytes=best_image_bytes,
    )

    print(f"✅ [TASK] Image import done: {recipe.title} (id={recipe.recipe_id})")
    return {"ok": True, "recipe_id": recipe.recipe_id, "title": recipe.title}


def process_recipe_from_text(user_id, raw_text, use_llm, custom_instruction):
    """
    Background job for add_recipe_from_text.
    Uses your organize_with_llm if requested, else your manual-structure path.
    Safe-calls organizer with both possible signatures you might have.
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"⌨️ [TASK] Text import started for user={user_id} use_llm={use_llm}")

    if use_llm:
        api_key = _openai_key()
        if not api_key:
            raise ValueError("OPENAI_KEY missing for LLM mode.")

        # Try your current call first (as in your views), fall back to the other signature if needed
        try:
            structured_data = organize_with_llm(
                recipe_input=raw_text,
                custom_instruction=custom_instruction,
                api_key=api_key,
            )
        except TypeError:
            # Fallback to the other known signature in your codebase
            raw_data = {"ingredients": [], "instructions": [raw_text]}
            structured_data = organize_with_llm(
                data=raw_data,
                api_key=api_key,
                transform_vegan=False,
                custom_instructions=custom_instruction,
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
        user=user,
        image_bytes=None,
    )

    print(f"✅ [TASK] Text import done: {recipe.title} (id={recipe.recipe_id})")
    return {"ok": True, "recipe_id": recipe.recipe_id, "title": recipe.title}
