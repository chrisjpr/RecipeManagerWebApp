import re
import json
import base64
import requests
from io import BytesIO
from fractions import Fraction
from PIL import Image
from recipe_scrapers import scrape_me
from rembg import remove
import openai

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
        "safe_title": slugify(scraper.title()),
        "ingredients": scraper.ingredients(),
        "instructions": scraper.instructions().split("\n"),
        "cook_time": str(scraper.total_time() or 1),
        "portions": scraper.yields() or "1",
        "image_url": scraper.image()
    }

# -------------------- LLM ORGANIZER ----------------------

def organize_with_llm(data, api_key, transform_vegan=False, custom_instructions=""):
    if transform_vegan:
        preamble = "You are a vegan chef... Please transform the following recipe..."
    else:
        preamble = "Here is a recipe..."

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
    - ALWAYS: For ingredients mentioned add bold formatting, such that it is correctly identified as bold in html code
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

# ------------------ IMAGE EXTRACTION ---------------------

def extract_recipe_from_images(images, api_key, transform_vegan=False, custom_instruction="", custom_title=""):
    client = openai.OpenAI(api_key=api_key)

    image_parts = []
    for file in images:
        image_bytes = file.read()
        if not image_bytes:
            continue
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })

    system_prompt = "You are a vegan chef..." if transform_vegan else "You are a chef assistant..."
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

- {custom_instruction}
- Translate to german.
- Convert to decimal.
- Split quantity + unit.
- Bold ingredients in instructions as <b>Ingredient [amount]</b>.
- Return only JSON. No markdown, no commentary.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [{"type": "text", "text": instruction}, *image_parts]}],
            temperature=0
        )
        data = json.loads(response.choices[0].message.content.strip())
        data["safe_title"] = slugify(custom_title or data.get("title", "recipe"))
        if custom_title:
            data["title"] = custom_title
        return data
    except Exception as e:
        print("❌ Failed to parse image LLM response:", e)
        return None

# ------------------ IMAGE DOWNLOAD -----------------------

def download_image_from_url(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        print("❌ Error downloading image:", e)
        return None
