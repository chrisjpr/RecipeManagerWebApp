import re
import json
import base64
import requests
from io import BytesIO
from fractions import Fraction
from PIL import Image, ImageChops
from recipe_scrapers import scrape_me
from rembg import remove
import openai
import io

# ------------------------- UTILS -------------------------

def slugify(title):
    return re.sub(r'[^a-z0-9]+', '', title.lower())


def parse_quantity_to_float(s):
    s = s.strip()
    unicode_map = {
        '½': 0.5, '⅓': 1/3, '⅔': 2/3,
        '¼': 0.25, '¾': 0.75, '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875,
    }
    if s in unicode_map:
        return unicode_map[s]
    if re.match(r'^\d+\s+\d+/\d+$', s):
        parts = s.split()
        return float(parts[0]) + float(Fraction(parts[1]))
    if re.match(r'^\d+/\d+$', s):
        return float(Fraction(s))
    if re.match(r'^\d+(\.\d+)?\s*-\s*\d+(\.\d+)?$', s):
        a, b = map(float, re.split(r'\s*-\s*', s))
        return round((a + b) / 2, 2)
    try:
        return float(s)
    except ValueError:
        return None

# ------------------- FETCH FROM URL ----------------------

def fetch_recipe_from_url(url):
    scraper = scrape_me(url)
    return {
        "title": scraper.title(),
        "ingredients": scraper.ingredients(),
        "instructions": scraper.instructions().split("\n"),
        "cook_time": str(scraper.total_time() or 1),
        "portions": scraper.yields() or "1",
        "image_url": scraper.image()
    }

# -------------------- LLM ORGANIZER ----------------------

def organize_with_llm(data, api_key, transform_vegan=False, custom_instructions=""):
    if transform_vegan:
        preamble =  """You are a vegan chef, capable of transforming all non-vegan Recipes
        into 100% vegan Recipes, using the best of what the world of vegan replacement products/ cooking
        techniques has to offer. Please transform the following recipe to a vegan Recipe,
        by applying only proofingly working techniques and mimicking taste and food texture as good as
        possible. Here is the recipe:"""
    else:
        preamble = "Here is a recipe:"

    prompt = f"""
{preamble}


Ingredients:
{data["ingredients"]}
Instructions:
{data["instructions"]}

Please fulfill the following requirements precisely:
- {custom_instructions}
- Translate to german.
- Split dressings/sauces/.. into extra groups when applicable.
- Convert fractions and ranges to decimal.
- Split quantity and unit (unit can be an empty string).
- Only in the instructions: 
    - ALWAYS: Add the required quantities to the respective ingredients, like Meat [500g] or Lettuce [1 Head]. DO NOT FORGET!
    - ALWAYS: For ingredients mentioned add bold formatting, such that it is correctly identified as bold in html code by using <b> tags!
- Output the result as raw JSON only (no Markdown formatting, no commentary, no "```json" wrappers, no text before or after the JSON).
- Do NOT include any extraneous information.

Expected output format:
{{ "ingredients": [{{"category": "string", "items": [{{"name": "string", "quantity": "string", "unit": "string"}}]}}], "instructions": ["string"] }}
"""

    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print("⚠️ LLM fallback due to error:", e)
        return {
            "ingredients": [
                {
                    "category": "Ingredients",
                    "items": [{"name": i, "quantity": "", "unit": ""} for i in data["ingredients"]],
                }
            ],
            "instructions": data["instructions"],
        }


#region EXTRACT RECIPE FROM IMAGES
##################### EXTRACT RECIPE FROM IMAGES #####################
def extract_recipe_from_images(images, api_key, transform_vegan=False, custom_instruction="", custom_title=""):
    client = openai.OpenAI(api_key=api_key)

    image_parts = []
    original_images = []

    for file in images:
        image_bytes = file.read()
        if not image_bytes:
            continue
        original_images.append(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })

    if transform_vegan:
        system_prompt =   """You are a vegan chef, capable of transforming all non-vegan Recipes
        into 100% vegan Recipes, using the best of what the world of vegan replacement products/ cooking
        techniques has to offer. Please transform the following recipe to a vegan Recipe,
        by applying only proofingly working techniques and mimicking taste and food texture as good as
        possible. Here is the recipe:"""
    else:
        system_prompt = """You are a chef assistant, capable of extracting recipes from images.
        Please extract the recipe from the following images.
        Here are the images:"""
    instruction = f"""
{system_prompt}

Return JSON:
{{
"title": "string",
"cook_time": "string or number",
"portions": "string or number",
"ingredients": [{{"category": "Ingredients", "items": [{{"name": "string", "quantity": "float", "unit": "string"}}]}}], 
"instructions": ["step 1", "step 2", ...]
}}
Please fulfill the following requirements precisely:
- {custom_instruction}
- Translate to german.
- Split dressings/sauces/.. into extra groups when applicable.
- Convert fractions and ranges to decimal.
- Split quantity and unit (unit can be an empty string).
- Only in the instructions: 
    - ALWAYS: Add the required quantities to the respective ingredients, like Meat [500g] or Lettuce [1 Head]. DO NOT FORGET!
    - ALWAYS: For ingredients mentioned add bold formatting, such that it is correctly identified as bold in html code by using <b> tags!
- Output the result as raw JSON only (no Markdown formatting, no commentary, no "```json" wrappers, no text before or after the JSON).
- Do NOT include any extraneous information.
  
Expected output format:
{{ "ingredients": [{{"category": "string", "items": [{{"name": "string", "quantity": "string", "unit": "string"}}]}}], "instructions": ["string"] }}
"""

    try:
        # Step 1: Get structured data from GPT-4o
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [{"type": "text", "text": instruction}, *image_parts]}],
            temperature=0
        )
        data = json.loads(response.choices[0].message.content.strip())
        if custom_title:
            data["title"] = custom_title

        # Step 2: Process best image (first one for simplicity)
        if original_images:
            raw_img = Image.open(BytesIO(original_images[0])).convert("RGBA")
            fg_only = remove(raw_img)

            bbox = fg_only.getbbox()
            if bbox:
                cropped = fg_only.crop(bbox)
            else:
                cropped = fg_only  # fallback

            # Remove alpha for JPG compatibility
            white_bg = Image.new("RGB", cropped.size, (255, 255, 255))
            white_bg.paste(cropped, mask=cropped.split()[3])

            buffer = BytesIO()
            white_bg.save(buffer, format="PNG")
            buffer.seek(0)

            # 🟩 Crop the visible content to avoid transparent boundaries
            cropped_bytes = crop_image_to_visible_area(buffer.getvalue())
            data["image_bytes"] = cropped_bytes

        return data

    except Exception as e:
        print("❌ Failed to parse image LLM response:", e)
        return None
    

#---------------------- IMAGE PROCESSING FUNCTIONS -----------------------#
def crop_image_to_visible_area(image_bytes):
    """
    Crops an image to its visible (non-transparent) area.

    Args:
        image_bytes (bytes): PNG image with possible transparency

    Returns:
        bytes: Cropped image as PNG
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # Create a mask from alpha channel
    alpha = image.split()[3]
    bbox = alpha.getbbox()

    if bbox:
        cropped = image.crop(bbox)
    else:
        cropped = image  # fallback if bbox fails

    # Optionally: convert to RGB on white background (for JPEG-like output)
    white_bg = Image.new("RGB", cropped.size, (255, 255, 255))
    white_bg.paste(cropped, mask=cropped.split()[3])  # use alpha as mask

    buffer = io.BytesIO()
    white_bg.save(buffer, format="PNG")
    return buffer.getvalue()


def download_image_from_url(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        print("❌ Error downloading image:", e)
        return None

##################### EXTRACT RECIPE FROM IMAGES #####################
#endregion

