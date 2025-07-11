from django import forms
from .models import Recipe, Ingredient, Instruction
from django.forms import inlineformset_factory


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['title', 'cook_time', 'portions', 'image', 'notes']