from django.urls import path
from dashboard import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='index'),
    path('round/<int:round_id>/', views.round_detail, name='round_detail'),
    path('asset/<int:asset_id>/', views.asset_detail, name='asset_detail'),
    path('asset/<int:asset_id>/export-excel/', views.export_asset_excel, name='export_asset_excel'),
]
