from django.contrib import admin
from .models import Recipe, Ingredient, Instruction
import traceback
from django.core.files.storage import default_storage



# Register your models here.

class IngredientInline(admin.TabularInline):
    model = Ingredient
    fk_name = 'recipe'  # ✅ Tells Django which FK to use for this inline
    extra = 1
    fields = ['name', 'quantity', 'unit', 'category']
    autocomplete_fields = []  # Optional: disable to show dropdown with labels

    # Provide recipe object to formfield_for_foreignkey
    def get_formset(self, request, obj=None, **kwargs):
        request._obj_ = obj  # stash current recipe
        return super().get_formset(request, obj, **kwargs)



class InstructionInline(admin.TabularInline):
    model = Instruction
    extra = 1
    fields = ['step_number', 'description']
    ordering = ['step_number']

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    inlines = [IngredientInline, InstructionInline]
    list_display = ('title', 'user', 'recipe_id', 'cook_time', 'portions')
    search_fields = ('title',)




    def save_model(self, request, obj, form, change):
        try:
            image_file = request.FILES.get("image")

            if image_file:
                print("✅ Image upload initiated")
                print("📝 Image name:", image_file.name)
                print("📦 Storage backend:", default_storage.__class__.__name__)

                # Save the file manually to trigger storage backend
                saved_path = obj.image.save(image_file.name, image_file, save=False)
                print("✅ Image saved to:", saved_path)
                print("🌐 Image URL should be:", obj.image.url)
            else:
                print("⚠️ No image found in request.FILES")
            if not obj.user:
                obj.user = request.user
            super().save_model(request, obj, form, change)
        except Exception as e:
            print("❌ Exception during image save:")
            traceback.print_exc()



# Optionally register Ingredient if needed
@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):

    list_display = ('recipe', 'name', 'quantity', 'unit', 'category')
    search_fields = ('name',)

@admin.register(Instruction)
class InstructionAdmin(admin.ModelAdmin):
    list_display = ('recipe_id', 'step_number', 'description')
    search_fields = ('description',)
    ordering = ['step_number']  


