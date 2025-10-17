from django.urls import path
from dashboard import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('asset/<int:asset_id>/', views.asset_detail, name='asset_detail'),
    path('asset/<int:asset_id>/export-excel/', views.export_asset_excel, name='export_asset_excel'),
]
