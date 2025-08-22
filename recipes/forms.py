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
        
        # Make name field not required at the field level to allow empty forms
        # We'll handle validation in the clean method
        self.fields['name'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # If all fields are empty, this form should be ignored
        name = cleaned_data.get('name', '').strip() if cleaned_data.get('name') else ''
        quantity = cleaned_data.get('quantity')
        unit = cleaned_data.get('unit', '').strip() if cleaned_data.get('unit') else ''
        category = cleaned_data.get('category', '').strip() if cleaned_data.get('category') else ''
        linked_recipe = cleaned_data.get('linked_recipe')
        
        if not name and not quantity and not unit and not category and not linked_recipe:
            # All fields are empty, mark for deletion
            cleaned_data['DELETE'] = True
        elif not name and (quantity or unit or category or linked_recipe):
            # Name is required if any other field has content
            raise forms.ValidationError("Ingredient name is required if you provide other details.")
        
        return cleaned_data






class BaseIngredientFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for form in self.forms:
            if self.user and 'linked_recipe' in form.fields:
                form.fields['linked_recipe'].queryset = Recipe.objects.filter(user=self.user)

    def _should_delete_form(self, form):
        """Override to handle empty forms as deleted"""
        if form.cleaned_data.get('DELETE', False):
            return True
        
        # Check if form is completely empty
        name = form.cleaned_data.get('name', '').strip() if form.cleaned_data.get('name') else ''
        quantity = form.cleaned_data.get('quantity')
        unit = form.cleaned_data.get('unit', '').strip() if form.cleaned_data.get('unit') else ''
        category = form.cleaned_data.get('category', '').strip() if form.cleaned_data.get('category') else ''
        linked_recipe = form.cleaned_data.get('linked_recipe')
        
        return not name and not quantity and not unit and not category and not linked_recipe




class InstructionForm(forms.ModelForm):
    class Meta:
        model = Instruction
        fields = ['step_number', 'description']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make description field not required at the field level to allow empty forms
        # We'll handle validation in the formset clean method
        self.fields['description'].required = False





class BaseInstructionFormSet(BaseInlineFormSet):
    def _should_delete_form(self, form):
        """Override to handle empty forms as deleted"""
        if form.cleaned_data.get('DELETE', False):
            return True
        
        # Check if form has no meaningful content
        description = form.cleaned_data.get('description', '').strip() if form.cleaned_data.get('description') else ''
        step_number = form.cleaned_data.get('step_number')
        
        return not description




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
    form=InstructionForm,
    exclude=['instruction_id'],
    extra=1,
    can_delete=True,
    formset=BaseInstructionFormSet
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