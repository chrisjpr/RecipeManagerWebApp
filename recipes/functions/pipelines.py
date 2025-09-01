import os
from .data_acquisition import *
import uuid
import re
import json
import base64
import requests
from io import BytesIO
from fractions import Fraction
from PIL import Image, ImageChops
from recipe_scrapers import scrape_me
from rembg import remove
from rembg import new_session  
import openai
import io
import numpy as np


OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4-turbo")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

# ------------------------- REMBG SESSION (low-memory) -------------------------
REMBG_MODEL = os.getenv("REMBG_MODEL", "u2netp")  # tiny model by default to avoid R14
_REMBG_SESSION = None
def rembg_session():
    """Create/reuse a single small rembg session to avoid loading a huge model per job."""
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        _REMBG_SESSION = new_session(REMBG_MODEL)
    return _REMBG_SESSION

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


def _downscale_image_bytes(image_bytes: bytes, max_side: int = int(os.getenv("IMG_MAX_SIDE", "1600")), format_hint: str = "JPEG") -> bytes:
    """
    Downscale large images to keep memory low. Returns RGB bytes in the chosen format.
    Idempotent for images already smaller than 'max_side'.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
        buf = BytesIO()
        # Use JPEG to keep bytes small; PNG if you need alpha (we only need RGB here)
        img.save(buf, format=format_hint, quality=85, optimize=True)
        return buf.getvalue()
    except Exception:
        return image_bytes

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
- Translate to german.
- Provide cook time in minutes.
- Split dressings/sauces/.. into extra groups when applicable.
- Convert fractions and ranges to decimal.
- Split quantity and unit (unit can be an empty string).
- Only in the instructions: 
    - ALWAYS: Add the required quantities to the respective ingredients, like Meat [500g] or Lettuce [1 Head]. DO NOT FORGET!
    - ALWAYS: For ingredients mentioned add bold formatting, such that it is correctly identified as bold in html code by using <b> tags!
    - NEVER ADD step numbers to the instructions, just write the steps in order.
- Output the result as raw JSON only (no Markdown formatting, no commentary, no "```json" wrappers, no text before or after the JSON).
- Do NOT include any extraneous information.

Expected output format:

{{ "ingredients": [{{"category": "string", "items": [{{"name": "string", "quantity": "string", "unit": "string"}}]}}], "instructions": ["string"] }}

Here is one more custom instruction, which comes from the user.
Give your best to follow it, as it is very important! Even if it interferes /overwrites other instructions. 
But never overwrite the output JSON format, even if stated in the following:
{custom_instructions}

"""

    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=OPENAI_TEXT_MODEL,
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

        # NEW: downscale to keep memory + payload small
        ds_bytes = _downscale_image_bytes(image_bytes)
        original_images.append(ds_bytes)

        b64 = base64.b64encode(ds_bytes).decode("utf-8")
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
- Translate to german.
- Provide cook time in minutes.
- Split dressings/sauces/.. into extra groups when applicable.
- Convert fractions and ranges to decimal.
- Split quantity and unit (unit can be an empty string).
- Only in the instructions: 
    - ALWAYS: Add the required quantities to the respective ingredients, like Meat [500g] or Lettuce [1 Head]. DO NOT FORGET!
    - ALWAYS: For ingredients mentioned add bold formatting, such that it is correctly identified as bold in html code by using <b> tags! Do not forget to do this for every ingredient!
    - NEVER ADD step numbers to the instructions, just write the steps in order.
- Output the result as raw JSON only (no Markdown formatting, no commentary, no "```json" wrappers, no text before or after the JSON).
- Do NOT include any extraneous information.
  
Expected output format:
{{ "ingredients": [{{"category": "string", "items": [{{"name": "string", "quantity": "string", "unit": "string"}}]}}], "instructions": ["string"] }}

Here is one more custom instruction, which comes from the user.
Give your best to follow it, as it is very important! Even if it interferes /overwrites other instructions. 
But never overwrite the output JSON format, even if stated in the following:
{custom_instruction}

"""

    try:
        # Step 1: Get structured data from GPT-4o
        response = client.chat.completions.create(
            model=OPENAI_VISION_MODEL,
            messages=[{"role": "user", "content": [{"type": "text", "text": instruction}, *image_parts]}],
            temperature=0
        )
        data = json.loads(response.choices[0].message.content.strip())
        if custom_title:
            data["title"] = custom_title

        # Step 2: Process best image using GPT-4 vision scoring
        if original_images:
            best_result, best_bytes = identify_best_dish_image(original_images, api_key)

            if best_bytes:
                # Step 3: Background removal (use shared small model session)
                raw_img = Image.open(BytesIO(best_bytes)).convert("RGBA")
                fg_only = remove(raw_img, session=rembg_session())  # CHANGED

                # Step 4: Strict crop of transparent + white space
                buffer = BytesIO()
                fg_only.save(buffer, format="PNG")
                buffer.seek(0)

                cropped_bytes = crop_image_to_visible_area(
                    image_bytes=buffer.getvalue(),
                    white_threshold=240,
                    alpha_threshold=10,
                    margin=2
                )

                data["image_bytes"] = cropped_bytes
            else:
                print("❌ No valid dish image identified.")

        return data

    except Exception as e:
        print("❌ Failed to parse image LLM response:", e)
        return None
    

#---------------------- IMAGE PROCESSING FUNCTIONS -----------------------#
def crop_image_to_visible_area(image_bytes: bytes, white_threshold: int = 240, alpha_threshold: int = 10, margin: int = 2) -> bytes:
    """
    Crops away both transparent and nearly-white areas from image.
    Works on RGBA input and returns a tightly cropped RGB image.
    """
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    rgba = np.array(image)

    r, g, b, a = rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2], rgba[:, :, 3]

    # Define visibility mask: pixel is visible if:
    # - Alpha is sufficiently high
    # - OR it's not nearly white
    visible = ((a > alpha_threshold) & ~((r > white_threshold) & (g > white_threshold) & (b > white_threshold)))

    if not np.any(visible):
        print("⚠️ Image appears fully white/transparent.")
        return image_bytes  # fallback

    coords = np.argwhere(visible)
    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0) + 1

    # Optional margin
    y0 = max(0, y0 - margin)
    x0 = max(0, x0 - margin)
    y1 = min(rgba.shape[0], y1 + margin)
    x1 = min(rgba.shape[1], x1 + margin)

    cropped_rgba = image.crop((x0, y0, x1, y1))

    # Paste onto white background to remove alpha
    white_bg = Image.new("RGB", cropped_rgba.size, (255, 255, 255))
    white_bg.paste(cropped_rgba, mask=cropped_rgba.split()[3])

    output = BytesIO()
    white_bg.save(output, format="PNG")
    return output.getvalue()




def download_image_from_url(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        print("❌ Error downloading image:", e)
        return None
    


def identify_best_dish_image(image_bytes_list, api_key):
    import base64, json
    import openai
    from PIL import Image
    from io import BytesIO

    client = openai.OpenAI(api_key=api_key)
    best_result = None
    best_confidence = -1
    best_bytes = None

    print(f"🧠 Evaluating {len(image_bytes_list)} image(s)...")
    for idx, image_bytes in enumerate(image_bytes_list):
        try:
            # NEW: ensure candidate is downscaled to control memory
            image_bytes = _downscale_image_bytes(image_bytes)

            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            width, height = img.size
            print(f"📐 Image {idx}: dimensions {width}x{height}")
        except Exception as e:
            print(f"❌ Failed to open image {idx}: {e}")
            continue

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{b64}"

        try:
            response = client.chat.completions.create(
                model=OPENAI_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are a vision model trained to identify food images.\n"
                                    "Does this image show a clearly plated dish (not ingredients or packaging)? "
                                    "If yes, return bounding box of dish as JSON like:\n"
                                    '{"confidence": float, "bounding_box": [x, y, width, height]}.\n'
                                    "x, y, width, height must be relative percentages (0.0 - 1.0).\n"
                                    "If not a clean dish, return: {\"confidence\": 0, \"bounding_box\": null}"
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }
                        ]
                    }
                ]
            )

            content = response.choices[0].message.content.strip().strip("`").strip()
            if content.startswith("json"):
                content = content[len("json"):].strip()  # handles ```json
            print(f"📨 Image {idx} model response:", content)
            if not content:
                print(f"⚠️ Empty content from API for image {idx}")
                continue

            content = content.strip("`")  # remove markdown ticks if any
            result = json.loads(content)

            if result.get("confidence", 0) > best_confidence and result.get("bounding_box"):
                # Convert relative bbox to absolute pixel coordinates
                x, y, w, h = result["bounding_box"]
                scaled_box = [
                    int(x * width),
                    int(y * height),
                    int(w * width),
                    int(h * height)
                ]
                result["bounding_box"] = scaled_box
                best_result = result
                best_bytes = image_bytes
                best_confidence = result["confidence"]
                print(f"🏆 Image {idx} selected with confidence {best_confidence}")

        except json.JSONDecodeError as jde:
            print(f"⚠️ Skipping image {idx}: Failed to parse JSON: {jde}")
        except Exception as e:
            print(f"⚠️ Skipping image {idx}: {e}")

    return best_result, best_bytes


##################### EXTRACT RECIPE FROM IMAGES #####################
#endregion


#region EXTRACT RECIPE FROM DOCUMENTS
##################### EXTRACT RECIPE FROM DOCUMENTS #####################

def _normalize_text_chunks(chunks):
    text = "\n".join([c for c in chunks if c]).strip()
    return re.sub(r'\n{3,}', '\n\n', text)

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Lightweight PDF text extraction."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return _normalize_text_chunks(pages)
    except Exception as e:
        print("⚠️ PDF text extraction failed:", e)
        return ""

def extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    """DOCX text extraction."""
    try:
        from docx import Document
        doc = Document(BytesIO(docx_bytes))
        paras = [p.text for p in doc.paragraphs]
        return _normalize_text_chunks(paras)
    except Exception as e:
        print("⚠️ DOCX text extraction failed:", e)
        return ""
    

def _images_from_pdf(pdf_bytes: bytes,
                     max_pages: int = int(os.getenv("DOC_IMAGE_MAX_PAGES", "5")),
                     max_images: int = int(os.getenv("MAX_DOC_IMAGES", "8")),
                     thumb_max_side: int = int(os.getenv("DOC_IMAGE_MAX_SIDE", "1600"))):
    """
    Extract up to `max_images` embedded images from the first `max_pages` of a PDF
    using doc.extract_image(xref) (more memory-friendly). Downscale big images.
    """
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        print("ℹ️ PyMuPDF not installed; skipping PDF image extraction:", e)
        return []

    out = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        seen = set()
        for page_index in range(min(len(doc), max_pages)):
            page = doc[page_index]
            for img in page.get_images(full=True):
                if len(out) >= max_images:
                    break
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    info = doc.extract_image(xref)
                    img_bytes = info.get("image", b"")
                    if not img_bytes:
                        continue
                    img_bytes = _downscale_image_bytes(img_bytes, max_side=thumb_max_side)
                    out.append(img_bytes)
                except Exception as ie:
                    print("⚠️ Could not extract image from PDF:", ie)
            if len(out) >= max_images:
                break
        doc.close()
    except Exception as e:
        print("⚠️ PDF image extraction failed:", e)
    return out

def _images_from_docx(docx_bytes: bytes,
                      max_images: int = int(os.getenv("MAX_DOC_IMAGES", "8")),
                      thumb_max_side: int = int(os.getenv("DOC_IMAGE_MAX_SIDE", "1600"))):
    """
    Read /word/media/* from docx zip, cap the count, and downscale.
    """
    import zipfile
    from io import BytesIO
    imgs = []
    try:
        with zipfile.ZipFile(BytesIO(docx_bytes)) as z:
            for name in z.namelist():
                if len(imgs) >= max_images:
                    break
                ext = name.lower().split(".")[-1]
                if not (name.startswith("word/media/") and ext in {"png","jpg","jpeg","gif","bmp","webp"}):
                    continue
                try:
                    b = z.read(name)
                    b = _downscale_image_bytes(b, max_side=thumb_max_side)
                    imgs.append(b)
                except Exception as ie:
                    print("⚠️ Could not read DOCX media:", ie)
    except Exception as e:
        print("⚠️ DOCX image extraction failed:", e)
    return imgs

def extract_recipe_from_documents(files, api_key, transform_vegan=False, custom_instruction="", custom_title=""):
    """
    files: list of dicts: {"name": str, "content_type": str, "bytes": bytes}
    Returns structured recipe dict (same shape as image/url flows). Also tries to
    derive a title image (data["image_bytes"]) from embedded document images.
    """
    all_texts = []
    gathered_images = []  # NEW

    for f in files:
        name = (f.get("name") or "").lower()
        ctype = (f.get("content_type") or "").lower()
        blob = f.get("bytes") or b""

        text = ""
        if "pdf" in ctype or name.endswith(".pdf"):
            text = extract_text_from_pdf_bytes(blob)
            # NEW: extract embedded images
            gathered_images.extend(_images_from_pdf(blob))
        elif "wordprocessingml" in ctype or name.endswith(".docx"):
            text = extract_text_from_docx_bytes(blob)
            # NEW: extract embedded images
            gathered_images.extend(_images_from_docx(blob))
        elif "msword" in ctype or name.endswith(".doc"):
            # Legacy .doc is not natively supported; recommend converting to .docx
            print("ℹ️ Legacy .doc detected (convert to .docx for best results).")
        else:
            # Ignore non-doc types - image pipeline handles those
            continue

        if text:
            all_texts.append(text)

    combined = "\n\n".join(all_texts).strip()
    if not combined:
        raise ValueError("No extractable text found in uploaded document(s).")

    # Build prompt (same output contract you already use elsewhere)
    if transform_vegan:
        preface = """You are a vegan chef, capable of transforming all non-vegan Recipes
        into 100% vegan Recipes, using the best of what the world of vegan replacement products/ cooking
        techniques has to offer. Please transform the following recipe to a vegan Recipe,
        by applying only proofingly working techniques and mimicking taste and food texture as good as
        possible."""
    else:
        preface = "You are a chef assistant. Extract a complete recipe from the text."

    prompt = f"""
{preface}

Return JSON:
{{
"title": "string",
"cook_time": "string or number",
"portions": "string or number",
"ingredients": [{{"category": "Ingredients", "items": [{{"name": "string", "quantity": "string", "unit": "string"}}]}}], 
"instructions": ["step 1", "step 2", ...]
}}
Please fulfill the following requirements precisely:
- Translate to german.
- Provide cook time in minutes.
- Split dressings/sauces/.. into extra groups when applicable.
- Convert fractions and ranges to decimal.
- Split quantity and unit (unit can be an empty string).
- Only in the instructions: 
    - ALWAYS: Add the required quantities to the respective ingredients, like Meat [500g] or Lettuce [1 Head]. DO NOT FORGET!
    - ALWAYS: For ingredients mentioned add bold formatting, such that it is correctly identified as bold in html code by using <b> tags! Do not forget to do this for every ingredient!
    - NEVER ADD step numbers to the instructions, just write the steps in order.
- Output the result as raw JSON only (no Markdown formatting, no commentary, no "```json" wrappers, no text before or after the JSON).
- Do NOT include any extraneous information.

Here is one more custom instruction from the user (respect it without changing the JSON format):
{custom_instruction}
"""

    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=OPENAI_TEXT_MODEL,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "text", "text": combined}
                ]}
            ],
            temperature=0
        )
        data = json.loads(response.choices[0].message.content.strip())
        if custom_title:
            data["title"] = custom_title

        # NEW: try to select + refine a hero image from the doc images
        if gathered_images:
            best_result, best_bytes = identify_best_dish_image(gathered_images, api_key)  # your existing scorer
            if best_bytes:
                # Background removal (same as image flow) — use shared small session
                raw_img = Image.open(BytesIO(best_bytes)).convert("RGBA")
                fg_only = remove(raw_img, session=rembg_session())  # CHANGED

                buf = BytesIO()
                fg_only.save(buf, format="PNG")
                buf.seek(0)

                cropped = crop_image_to_visible_area(
                    image_bytes=buf.getvalue(),
                    white_threshold=240,
                    alpha_threshold=10,
                    margin=2
                )
                data["image_bytes"] = cropped
            else:
                print("ℹ️ No suitable dish image found inside the document.")

        return data
    except Exception as e:
        print("❌ Failed to parse document LLM response:", e)
        return None
#endregion


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
        return result, result.get("image_bytes")  # may be None
    except Exception as e:
        print("❌ Failed to extract recipe from document(s):", e)
        raise


##################### GET DATA FROM URL / IMAGE FUNCTIONS #####################
