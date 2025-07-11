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
    
]