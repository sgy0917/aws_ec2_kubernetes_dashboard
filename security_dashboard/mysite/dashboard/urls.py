from django.urls import path
from dashboard import views

app_name = 'dashboard'

urlpatterns = [
    # 메인 대시보드 (새로운 페이지)
    path('', views.index, name='index'),
    
    # 회차 목록 (기존 index → rounds_list)
    path('rounds/', views.rounds_list, name='rounds_list'),
    
    # 회차별 자산 목록
    path('round/<int:round_id>/', views.round_detail, name='round_detail'),
    
    # 자산 상세
    path('asset/<int:asset_id>/', views.asset_detail, name='asset_detail'),
    
    # Excel 다운로드
    path('asset/<int:asset_id>/export-excel/', views.export_asset_excel, name='export_asset_excel'),
    
    # 점검 시작 API
    path('api/start-check/', views.start_check, name='start_check'),
]
