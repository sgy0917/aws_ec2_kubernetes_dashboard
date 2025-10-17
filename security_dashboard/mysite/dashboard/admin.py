from django.contrib import admin
from dashboard.models import Asset, SecurityCheck, CheckRound


@admin.register(CheckRound)
class CheckRoundAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'check_date',
        'round_number',
        'check_time',
        'get_total_assets',
        'created_at',
    ]
    list_filter = [
        'check_date',
        'round_number',
    ]
    search_fields = [
        'check_date',
    ]
    ordering = ['-check_date', '-round_number']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('회차 정보', {
            'fields': ('check_date', 'round_number', 'check_time')
        }),
        ('메타 정보', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_total_assets(self, obj):
        return obj.get_total_assets()
    get_total_assets.short_description = '자산 수'


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'asset_code',
        'name',
        'hostname',
        'distro',
        'os_version',
        'latest_security_status',
        'latest_check_date',
        'execution_type',
    ]
    list_filter = [
        'latest_security_status',
        'distro',
        'execution_type',
        'is_container',
        'is_kubernetes',
    ]
    search_fields = [
        'asset_code',
        'name',
        'hostname',
        'distro',
    ]
    ordering = ['-latest_check_date']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('asset_code', 'name', 'hostname')
        }),
        ('시스템 정보', {
            'fields': ('distro', 'os_version', 'kernel')
        }),
        ('실행 환경', {
            'fields': ('execution_type', 'is_container', 'is_kubernetes')
        }),
        ('최근 점검 정보', {
            'fields': ('latest_check_date', 'latest_security_status')
        }),
        ('메타 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SecurityCheck)
class SecurityCheckAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'round',
        'asset',
        'check_date',
        'status',
        'total_checks',
        'passed_checks',
        'failed_checks',
        'warning_checks',
        'get_pass_rate',
    ]
    list_filter = [
        'status',
        'check_date',
        'round__check_date',
    ]
    search_fields = [
        'asset__name',
        'asset__hostname',
        'asset__asset_code',
    ]
    ordering = ['-check_date']
    readonly_fields = ['created_at', 'generated_at']
    
    fieldsets = (
        ('회차 및 자산', {
            'fields': ('round', 'asset')
        }),
        ('점검 정보', {
            'fields': ('check_date', 'generated_at', 'status')
        }),
        ('통계', {
            'fields': (
                'total_checks',
                'passed_checks',
                'failed_checks',
                'warning_checks',
                'not_applicable_checks'
            )
        }),
        ('상세 데이터', {
            'fields': ('details', 'report_info'),
            'classes': ('collapse',)
        }),
        ('메타 정보', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_pass_rate(self, obj):
        return f"{obj.get_pass_rate()}%"
    get_pass_rate.short_description = '합격률'
