from django import forms
from .models import Recipe, Ingredient, Instruction
from django.forms import inlineformset_factory


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['title', 'cook_time', 'portions', 'image', 'notes']



IngredientFormSet = inlineformset_factory(
    Recipe,
    Ingredient,
    fields=["name", "quantity", "unit", "category"],
    exclude=['ingredient_id'],
    extra=1,
    can_delete=True
)

InstructionFormSet = inlineformset_factory(
    Recipe,
    Instruction,
    fields=["step_number", "description"],
    exclude=['instruction_id'],
    extra=1,
    can_delete=True
)

class AddRecipeForm(forms.Form):
    url = forms.URLField(label="Recipe URL", required=False)
    image = forms.ImageField(label="Upload Image", required=False)
    prompt = forms.CharField(label="Custom Prompt", required=False, widget=forms.Textarea)
    transform_vegan = forms.BooleanField(label="Transform to Vegan?", required=False)

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("url") and not cleaned_data.get("image"):
            raise forms.ValidationError("Please provide either a URL or an image.")
        return cleaned_data