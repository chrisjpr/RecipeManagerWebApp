from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter


from .views import *

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')

urlpatterns = [
    path('', include(router.urls)),
    path('', recipe_list, name='recipe_list'),
    path('<slug:slug>/', recipe_detail, name='recipe_detail'),
]