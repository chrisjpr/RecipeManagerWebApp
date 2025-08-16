from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter


from . import views




urlpatterns = [
    path('recipe_list', views.recipe_list, name='recipe_list'),
    path('<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    path('edit/<int:pk>/', views.recipe_edit, name='recipe_edit'),
    path('delete/<int:pk>/', views.recipe_delete, name='recipe_delete'),
    path('', views.home, name="home"),
    path('create_recipe/', views.create_recipe, name='create_recipe'),
    path("add-from-url/", views.add_recipe_from_url, name="add_recipe_from_url"),
    path("add-from-image/", views.add_recipe_from_image, name="add_recipe_from_image"),
    path('recipes/add-from-text/', views.add_recipe_from_text, name='add_recipe_from_text'),
    path('friends/recipes/<int:friend_id>/', views.friends_recipes, name='friends_recipes'),
    path('copy/<int:recipe_id>/', views.copy_recipe, name='copy_recipe'),
    path('update-visibility/', views.update_visibility_ajax, name='update_visibility'),
    path('create-options/', views.create_recipe_landing, name='create_recipe_landing'),
    path("public/", views.public_recipes, name="public_recipes"),
    path("recipe/<int:recipe_id>/pdf/", views.recipe_pdf, name="recipe_pdf_xhtml2pdf"),


]


