from .data_acquisition import *


#region GET DATA FROM URL / IMAGE FUNCTIONS
##################### GET DATA FROM URL / IMAGE FUNCTIONS #####################

def get_data_from_url(url, api_key, transform_vegan=False, custom_instructions=""):
    """
    Fetches and organizes recipe data from a URL and prepares it for database insertion.
    Returns a dictionary with all necessary fields for saving.
    """

    # Step 1: Raw scrape
    raw_data = fetch_recipe_from_url(url)

    # Step 2: LLM postprocessing
    structured_data = organize_with_llm(raw_data, api_key, transform_vegan, custom_instructions)

    # Step 3: Download image (optional)
    image_io = None
    if raw_data.get("image_url"):
        image_io = download_image_from_url(raw_data["image_url"])

    # Step 4: Return all fields needed for DB save
    return {
        "title": raw_data["title"],
        "safe_title": slugify(raw_data["title"]),
        "cook_time": raw_data.get("cook_time", 1),
        "portions": raw_data.get("portions", 1),
        "image_file": image_io,  # This can be passed directly to a Django ImageField
        "ingredients": structured_data["ingredients"],
        "instructions": structured_data["instructions"]
    }

def get_data_from_image(images, api_key, html_dir, transform_vegan=False, custom_instruction="", custom_title=""):
    """
    Main pipeline to extract and structure a recipe from uploaded images.
    Returns a dictionary with all required recipe information.
    """

    print("🔄 Starting pipeline to get data from image...")

    structured_data = extract_recipe_from_images(
        images=images,
        api_key=api_key,
        html_dir=html_dir,
        transform_vegan=transform_vegan,
        custom_instruction=custom_instruction,
        custom_title=custom_title
    )

    if not structured_data:
        raise ValueError("No structured data returned from image extraction.")

    # Normalize quantities (optional)
    for group in structured_data.get("ingredients", []):
        for item in group.get("items", []):
            try:
                item["quantity"] = parse_quantity_to_float(str(item["quantity"])) if item.get("quantity") else None
            except Exception as e:
                print(f"⚠️ Could not parse quantity '{item['quantity']}':", e)
                item["quantity"] = None

    return structured_data

##################### GET DATA FROM URL / IMAGE FUNCTIONS #####################


from recipes.models import Recipe, Ingredient, Instruction
from django.core.files.base import ContentFile
from django.conf import settings
import os

#region Save Structured Recipe to DB
##################### Save Structured Recipe to DB #####################

def save_structured_recipe_to_db(data, user, image_bytes=None):
    """
    Save a structured recipe (from GPT or similar) into the database.
    
    Arguments:
        data (dict): Must contain title, cook_time, portions, ingredients (list), instructions (list)
        user (User): Django User who owns the recipe
        image_bytes (bytes or None): Optional image to save to Recipe.image (as ImageField)
    Returns:
        Recipe instance
    """

    # Create Recipe object
    recipe = Recipe(
        title=data["title"],
        cook_time=int(data.get("cook_time", 1)),
        portions=int(data.get("portions", 1)),
        notes="Imported automatically",
        user=user
    )

    # Optionally save image to ImageField
    if image_bytes:
        filename = f"{data['safe_title']}.png"
        recipe.image.save(filename, ContentFile(image_bytes), save=False)

    recipe.save()

    # Add ingredients
    for group in data.get("ingredients", []):
        category = group.get("category", "")
        for item in group.get("items", []):
            Ingredient.objects.create(
                recipe_id=recipe,
                category=category,
                name=item.get("name", ""),
                quantity=item.get("quantity") or None,
                unit=item.get("unit") or ""
            )

    # Add instructions
    for idx, step in enumerate(data.get("instructions", []), start=1):
        Instruction.objects.create(
            recipe_id=recipe,
            step_number=idx,
            description=step
        )

    return recipe
##################### /Save Structured Recipe to DB #####################