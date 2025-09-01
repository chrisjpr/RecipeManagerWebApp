from .data_acquisition import *
import uuid

#region GET DATA FROM URL / IMAGE FUNCTIONS
##################### GET DATA FROM URL / IMAGE FUNCTIONS #####################

def get_data_from_url(url, api_key, transform_vegan=False, custom_instructions=""):
    raw_data = fetch_recipe_from_url(url)
    structured_data = organize_with_llm(raw_data, api_key, transform_vegan, custom_instructions)

    # Get image
    image_path = raw_data.get("image_url")  # comes from scrape_me
    image_bytes = None

    if image_path:
        try:
            response = requests.get(image_path)
            if response.status_code == 200:
                original = response.content
                image_bytes = crop_image_to_visible_area(original)
        except Exception as e:
            print(f"⚠️ Failed to download image from URL: {e}")

    # Final data
    new_recipe_data = {
        "title": raw_data["title"],
        "cook_time": raw_data["cook_time"],
        "portions": raw_data["portions"],
        "image_url": raw_data["image_url"],
        "ingredients": structured_data["ingredients"],
        "instructions": structured_data["instructions"]
    }

    return new_recipe_data, image_bytes

def get_data_from_image(images, api_key, transform_vegan, custom_instruction, custom_title="", return_image_bytes=True):
    structured_data = None
    best_image_bytes = None

    try:
        result = extract_recipe_from_images(
            images=images,
            api_key=api_key,
            transform_vegan=transform_vegan,
            custom_instruction=custom_instruction,
            custom_title=custom_title
        )
        if result is None:
            raise ValueError("No result returned from image analysis.")

        structured_data = result
        best_image_bytes = result.get("image_bytes", None)  # manually inject this below if needed

        # If result only contains image path/url, re-fetch bytes:
        if return_image_bytes and not best_image_bytes and result.get("image_url"):
            try:
                resp = requests.get(result["image_url"])
                if resp.status_code == 200:
                    best_image_bytes = resp.content
            except Exception as e:
                print(f"⚠️ Could not re-download image: {e}")

        return structured_data, best_image_bytes

    except Exception as e:
        print("❌ Failed to extract recipe from image:", e)
        raise


def get_data_from_documents(documents, api_key, transform_vegan, custom_instruction, custom_title=""):
    """
    documents: list of dicts {"name": str, "content_type": str, "bytes": bytes}
    Returns (structured_data, image_bytes=None) to match the existing function shapes.
    """
    try:
        result = extract_recipe_from_documents(
            files=documents,
            api_key=api_key,
            transform_vegan=transform_vegan,
            custom_instruction=custom_instruction,
            custom_title=custom_title
        )
        if result is None:
            raise ValueError("No result returned from document analysis.")
        return result, None  # no hero image from docs
    except Exception as e:
        print("❌ Failed to extract recipe from document(s):", e)
        raise


##################### GET DATA FROM URL / IMAGE FUNCTIONS #####################


from recipes.models import Recipe, Ingredient, Instruction
from django.core.files.base import ContentFile
from django.conf import settings
import os

#region STR DATA TO DB
##################### SAVE STRUCTURED DATA TO DB FUNCTION #####################

def clean_int_from_string(value, fallback=1):
    """
    Extracts the first integer found in a string like '4 servings' or '30 min'.
    Returns fallback (default 1) if nothing is found or invalid.
    """
    try:
        return int(re.search(r'\d+', str(value)).group())
    except:
        return fallback


def clean_quantity(value):
    """
    Attempts to convert a quantity string like '1 1/2' or '½' to a float.
    Returns None if invalid.
    """
    from fractions import Fraction

    if not value:
        return None
    value = str(value).strip()

    unicode_fractions = {
        '½': 0.5, '⅓': 1/3, '⅔': 2/3,
        '¼': 0.25, '¾': 0.75, '⅛': 0.125,
        '⅜': 0.375, '⅝': 0.625, '⅞': 0.875,
    }

    if value in unicode_fractions:
        return float(unicode_fractions[value])

    try:
        if ' ' in value:
            whole, frac = value.split()
            return float(whole) + float(Fraction(frac))
        if '/' in value:
            return float(Fraction(value))
        if '-' in value:
            start, end = map(float, value.split('-'))
            return round((start + end) / 2, 2)
        return float(value)
    except:
        return None

def save_structured_recipe_to_db(data, user, image_bytes=None):
    """
    Save a structured recipe dictionary to the Django database.
    """
    recipe = Recipe(
        title=data.get("title", "Untitled"),
        cook_time=clean_int_from_string(data.get("cook_time")),
        portions=clean_int_from_string(data.get("portions")),
        notes="Imported automatically",
        user=user,
    )

    # Optionally attach image
    if image_bytes:
            filename = f"recipe_{uuid.uuid4().hex}.png"
            recipe.image.save(filename, ContentFile(image_bytes), save=False)

    recipe.save()

    # Save ingredients
    for group in data.get("ingredients", []):
        category = group.get("category", "")
        for item in group.get("items", []):
            Ingredient.objects.create(
                recipe=recipe,
                category=category,
                name=item.get("name", "").strip(),
                quantity=clean_quantity(item.get("quantity")),
                unit=(item.get("unit") or "").strip()
            )

    # Save instructions
    for idx, step in enumerate(data.get("instructions", []), start=1):
        Instruction.objects.create(
            recipe_id=recipe,
            step_number=idx,
            description=step.strip()
        )

    return recipe

##################### Save Structured Recipe to DB #####################