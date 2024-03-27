from django.urls import path
from . import views

app_name = 'app'
urlpatterns = [
    path('', views.get, name='get'),
    path('delete_user/<int:id>/', views.delete_user, name='delete_user'),
    path('delete-societe/<str:uid>/', views.delete_societe, name='delete_societe'),
    path('update-user-field/', views.update_user_field, name='update_user_field'),
    path('update-societe-field/', views.update_societe_field, name='update_societe_field'),
    path('show-modal/', views.show_modal, name='show_modal'),
    path('cell-details/', views.cell_details_view, name='cell_details_view'),
    path('get-inventory-ajax/', views.get_inventory_ajax, name='get_inventory_ajax'),
]
