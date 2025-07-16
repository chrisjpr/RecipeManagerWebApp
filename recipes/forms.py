from django import forms
from .models import Recipe, Ingredient, Instruction
from django.forms import inlineformset_factory
from django.forms import BaseInlineFormSet


class RecipeForm(forms.ModelForm):
    use_llm = forms.BooleanField(required=False, label="Organize with LLM?")
    transform_vegan = forms.BooleanField(required=False, label="Transform to Vegan?")
    custom_instruction = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional instruction for the LLM..."}),
        required=False,
        label="Custom Instruction"
    )

    ingredients_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "1 tbsp olive oil\n200g tofu\n1 tsp paprika"}),
        label="Ingredients as Text"
    )

    instructions_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Preheat oven to 180°C\nChop the vegetables\nBake for 20 min"}),
        label="Instructions as Text"
    )

    class Meta:
        model = Recipe
        fields = ['title', 'cook_time', 'portions', 'image', 'notes']

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'quantity', 'unit', 'category', 'linked_recipe']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # get user from view
        super().__init__(*args, **kwargs)

        if user is not None:
            # limit linked_recipe choices to the current user's own recipes
            self.fields['linked_recipe'].queryset = Recipe.objects.filter(user=user)
        else:
            # fallback: no recipe options
            self.fields['linked_recipe'].queryset = Recipe.objects.none()


class BaseIngredientFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for form in self.forms:
            if self.user and 'linked_recipe' in form.fields:
                form.fields['linked_recipe'].queryset = Recipe.objects.filter(user=self.user)

IngredientFormSet = inlineformset_factory(
    parent_model=Recipe,
    model=Ingredient,
    form=IngredientForm,             # ✅ custom form
    formset=BaseIngredientFormSet,   # ✅ custom formset (handles user logic)
    fk_name='recipe',                # or 'recipe_id' depending on your model
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
    

class ParseWithLLMForm(forms.Form):
    raw_recipe_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "Paste raw recipe text here..."}),
        label="Raw Recipe"
    )
    use_llm = forms.BooleanField(required=False, label="Organize with LLM?")
    custom_instruction = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional instruction for the LLM..."}),
        required=False,
        label="Custom Instruction"
    )