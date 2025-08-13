# yourapp/management/commands/import_recipes.py
import json
import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string


from recipes.models import Recipe, Ingredient, Instruction
 

INT_RE = re.compile(r"\d+")
FLOAT_RE = re.compile(r"\d+(?:[.,]\d+)?")

def parse_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    m = INT_RE.search(str(value))
    return int(m.group(0)) if m else default

def parse_float_or_none(value):
    if value in ("", None):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = FLOAT_RE.search(str(value))
    if not m:
        return None
    return float(m.group(0).replace(",", "."))

class Command(BaseCommand):
    help = "Import recipes from legacy JSON per-user folders into Django models."

    def add_arguments(self, parser):
        parser.add_argument("base_folder", type=str, help="Path to recipe_data/ folder")
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing recipes (match by user+title) instead of skipping.",
        )
        parser.add_argument(
            "--create-missing-users",
            action="store_true",
            help="Create users that don't exist (with unusable password).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report what would be imported without writing to DB.",
        )

    def handle(self, base_folder, update, create_missing_users, dry_run, *args, **opts):
        base = Path(base_folder).expanduser().resolve()
        if not base.exists():
            raise CommandError(f"Base folder not found: {base}")

        User = get_user_model()
        total_created = total_updated = total_skipped = 0

        # each subfolder is a username
        for user_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
            username = user_dir.name
            json_path = user_dir / "recipe_data.json"
            if not json_path.exists():
                self.stdout.write(self.style.WARNING(f"[{username}] no recipe_data.json, skipping"))
                continue

            # get or create user
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                if not create_missing_users:
                    self.stdout.write(self.style.ERROR(
                        f"[{username}] user not found. Use --create-missing-users to auto-create."
                    ))
                    continue
                
                fake_email = f"{username.lower()}@import.local"
                temp_password = "1234" # generates a random 12-char password
                
                user = User.objects.create_user(
                    username=username,
                    email=fake_email,
                    password=temp_password,
                    is_verified=True,             # auto-verified
                    verification_code=None        # skip verification flow
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{username}] created user | email: {fake_email} | password: {temp_password}"
                    )
                )

            with json_path.open("r", encoding="utf-8") as f:
                try:
                    recipes = json.load(f)
                except json.JSONDecodeError as e:
                    self.stdout.write(self.style.ERROR(f"[{username}] JSON error: {e}"))
                    continue

            self.stdout.write(self.style.NOTICE(f"[{username}] importing {len(recipes)} recipes"))

            with transaction.atomic():
                for rec in recipes:
                    title = (rec.get("title") or "").strip()
                    if not title:
                        self.stdout.write(self.style.WARNING(f"[{username}] recipe missing title, skipping"))
                        total_skipped += 1
                        continue

                    cook_time = parse_int(rec.get("cook_time"), default=0)  # e.g. "15 Minuten" -> 15
                    portions = parse_int(rec.get("portions"), default=0)    # e.g. "4 servings" -> 4
                    notes = rec.get("notes") or None

                    # find existing
                    existing = Recipe.objects.filter(user=user, title=title).first()

                    # prepare image (local path preferred over URL)
                    image_path = rec.get("image_path") or ""
                    image_file = None
                    if image_path:
                        p = Path(image_path)
                        # if absolute path doesn't exist, also try relative to user's folder
                        if not p.exists():
                            rel_try = user_dir / Path(image_path.strip("/"))
                            if rel_try.exists():
                                p = rel_try
                        if p.exists() and p.is_file():
                            image_file = p

                    if existing and not update:
                        self.stdout.write(f"[{username}] '{title}' exists -> skip (use --update to overwrite)")
                        total_skipped += 1
                        continue

                    if dry_run:
                        self.stdout.write(f"[DRY] {username} :: {title} (+ingredients +instructions)")
                        continue

                    if existing and update:
                        recipe = existing
                        recipe.cook_time = cook_time
                        recipe.portions = portions
                        recipe.notes = notes
                        # image: replace if we found a local file
                        if image_file:
                            with image_file.open("rb") as fp:
                                recipe.image.save(image_file.name.split("/")[-1], File(fp), save=False)
                        recipe.save()
                        # clear children to re-sync
                        recipe.ingredients.all().delete()
                        recipe.instructions.all().delete()
                        total_updated += 1
                    else:
                        recipe = Recipe(
                            user=user,
                            title=title,
                            cook_time=cook_time,
                            portions=portions,
                            notes=notes,
                        )
                        if image_file:
                            with image_file.open("rb") as fp:
                                recipe.image.save(image_file.name.split("/")[-1], File(fp), save=False)
                        recipe.save()
                        total_created += 1

                    # ingredients: list of {category, items:[{name, quantity, unit, reference?}]}
                    for block in rec.get("ingredients", []) or []:
                        category = block.get("category")
                        for item in block.get("items", []) or []:
                            name = (item.get("name") or "").strip()
                            if not name:
                                continue
                            qty = parse_float_or_none(item.get("quantity"))
                            unit = (item.get("unit") or None) or None
                            Ingredient.objects.create(
                                recipe=recipe,
                                category=category or None,
                                name=name,
                                quantity=qty,
                                unit=unit
                            )

                    # instructions: list of strings (may contain HTML — your TextField can store it as-is)
                    for idx, step in enumerate(rec.get("instructions", []) or [], start=1):
                        if step is None:
                            continue
                        Instruction.objects.create(
                            recipe_id=recipe,
                            step_number=idx,
                            description=str(step),
                        )

            self.stdout.write(self.style.SUCCESS(f"[{username}] done"))

        self.stdout.write(self.style.SUCCESS(
            f"Created: {total_created}, Updated: {total_updated}, Skipped: {total_skipped}"
        ))
