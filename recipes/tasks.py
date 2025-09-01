import os
from io import BytesIO
import requests

from django.conf import settings
from django.contrib.auth import get_user_model

from rq import get_current_job

# Use the same imports you use in views.py so signatures match
from .functions.pipelines import (
    get_data_from_url,
    get_data_from_image,
    save_structured_recipe_to_db,
    get_data_from_documents,   # <-- NEW
)

from .functions.data_acquisition import (
    organize_with_llm,
    crop_image_to_visible_area,
)


def _openai_key():
    # env first, then settings attr (works locally & on Heroku)
    return os.getenv("OPENAI_KEY") or getattr(settings, "OPENAI_KEY", None)


def _fail_job(error_code: str, message: str):
    """
    Annotate the current RQ job with a failure code/message so the client
    can render precise red banners, then raise to mark the job failed.
    """
    job = get_current_job()
    if job:
        job.meta = job.meta or {}
        job.meta["error_code"] = error_code
        job.meta["error_message"] = message
        job.save_meta()
    # Raising any exception marks the job as failed in RQ
    raise RuntimeError(message)


def process_recipe_from_url(user_id, url, transform_vegan, custom_instruction, custom_title):
    """
    Background job for add_recipe_from_url.
    Uses your existing get_data_from_url + save_structured_recipe_to_db.
    Emits structured failure codes for the frontend.
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"📥 [TASK] URL import started for user={user_id} url={url}")

    try:
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

    except requests.exceptions.RequestException:
        # Explicit “webpage could not be found” path
        _fail_job("webpage_not_found", "The webpage could not be found.")
    except Exception as e:
        _fail_job("url_import_failed", f"URL import failed: {e}")


def process_recipe_from_image(user_id, images_bytes_list, transform_vegan, custom_instruction, custom_title):
    """
    Background job for add_recipe_from_image.
    Accepts a list of BYTES (not InMemoryUploadedFile), wraps them into BytesIO so your code can .read().
    Emits structured failure codes (including 'no_main_image').
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"🖼️ [TASK] Image import started for user={user_id} images={len(images_bytes_list) if images_bytes_list else 0}")

    try:
        # Convert bytes -> BytesIO to satisfy extract loop using .read()
        images_filelikes = [BytesIO(b) for b in (images_bytes_list or [])]

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
            image_bytes=(best_image_bytes or structured_data.get("image_bytes")),  # may be None
        )

        print(f"✅ [TASK] Image import done: {recipe.title} (id={recipe.recipe_id})")
        return {"ok": True, "recipe_id": recipe.recipe_id, "title": recipe.title}

    except Exception as e:
        _fail_job("image_import_failed", f"Image import failed: {e}")


def process_recipe_from_text(user_id, raw_text, use_llm, custom_instruction):
    """
    Background job for add_recipe_from_text.
    Uses your organize_with_llm if requested, else a basic manual structure.
    Manual path is intentionally more error-prone; we surface clearer errors.
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"⌨️ [TASK] Text import started for user={user_id} use_llm={use_llm}")

    try:
        if use_llm:
            api_key = _openai_key()
            if not api_key:
                _fail_job("manual_import_failed", "OPENAI_KEY missing for LLM mode.")

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
            # Manual is more error-prone; enforce a minimal quality bar
            text_norm = (raw_text or "").strip()
            if len(text_norm) < 40 or "\n" not in text_norm:
                _fail_job(
                    "manual_too_ambiguous",
                    "Manual import is more prone to errors and the provided text was too ambiguous."
                )

            structured_data = {
                "title": (text_norm.splitlines()[0] or "Untitled Recipe")[:255],
                "ingredients": [],
                "instructions": [ln for ln in text_norm.splitlines()[1:] if ln.strip()],
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

    except Exception as e:
        _fail_job("manual_import_failed", f"Manual import failed: {e}")


def process_recipe_from_uploads(user_id, uploads, transform_vegan=False, custom_instruction="", custom_title=""):
    """
    NEW: Handles mixed uploads of images and documents.
    `uploads` is a list of dicts: {"name": str, "content_type": str, "bytes": bytes}
    - Prefer documents for text extraction if present.
    - Use images to try to get a title image (optional).
    - Never fail just because a title image was not found.
    """
    import io
    User = get_user_model()
    user = User.objects.get(pk=user_id)

    print(f"📦 [TASK] Mixed upload started for user={user_id} files={len(uploads) if uploads else 0}")

    try:
        api_key = _openai_key()

        image_files = []
        document_files = []
        for f in (uploads or []):
            name = (f.get("name") or "").lower()
            ctype = (f.get("content_type") or "").lower()
            blob = f.get("bytes") or b""
            if not blob:
                continue
            if ctype.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
                image_files.append(io.BytesIO(blob))
            elif ("pdf" in ctype or name.endswith(".pdf") or
                  "word" in ctype or name.endswith(".docx") or name.endswith(".doc")):
                document_files.append({"name": name, "content_type": ctype, "bytes": blob})

        structured_data = None
        best_image_bytes = None

        # 1) Prefer reading the text from documents (PDF/DOCX) if present
        if document_files:
            structured_data, _ = get_data_from_documents(
                documents=document_files,
                api_key=api_key,
                transform_vegan=transform_vegan,
                custom_instruction=custom_instruction,
                custom_title=custom_title
            )

        # 2) If no structured text yet, fall back to OCR/vision on images
        if not structured_data and image_files:
            structured_data, best_image_bytes = get_data_from_image(
                images=image_files,
                api_key=api_key,
                transform_vegan=transform_vegan,
                custom_instruction=custom_instruction,
                custom_title=custom_title,
                return_image_bytes=True,
            )

        if not structured_data:
            _fail_job("import_failed", "Could not extract a recipe from the provided files.")

        # 3) If text came from docs and we also have images, try to pick a title image (optional)
        if best_image_bytes is None and image_files:
            try:
                _, best_image_bytes = get_data_from_image(
                    images=image_files,
                    api_key=api_key,
                    transform_vegan=transform_vegan,
                    custom_instruction=custom_instruction,
                    custom_title=custom_title,
                    return_image_bytes=True,
                )
            except Exception as e:
                print("⚠️ Could not derive hero image from images:", e)

        # 4) Optional crop step—same helper you already use
        if best_image_bytes:
            try:
                best_image_bytes = crop_image_to_visible_area(best_image_bytes)
            except Exception:
                pass

        recipe = save_structured_recipe_to_db(
            data=structured_data,
            user=user,
            image_bytes=best_image_bytes,   # may be None — that’s OK
        )

        print(f"✅ [TASK] Mixed upload done: {recipe.title} (id={recipe.recipe_id})")
        return {"ok": True, "recipe_id": recipe.recipe_id, "title": recipe.title}

    except Exception as e:
        _fail_job("mixed_import_failed", f"Import failed: {e}")
