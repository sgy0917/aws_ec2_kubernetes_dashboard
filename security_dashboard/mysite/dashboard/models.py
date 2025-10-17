from django.db import models
from django.utils import timezone

class Asset(models.Model):
    """자산 정보"""
    asset_code = models.CharField(max_length=100, unique=True, verbose_name='자산 코드')
    name = models.CharField(max_length=200, verbose_name='자산명')
    hostname = models.CharField(max_length=200, blank=True, null=True, verbose_name='호스트네임')
    distro = models.CharField(max_length=50, blank=True, null=True, verbose_name='배포판')
    os_version = models.CharField(max_length=100, blank=True, null=True, verbose_name='OS 버전')
    kernel = models.CharField(max_length=100, blank=True, null=True, verbose_name='커널 버전')
    execution_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='실행 방식')
    is_container = models.BooleanField(default=False, verbose_name='컨테이너 여부')
    is_kubernetes = models.BooleanField(default=False, verbose_name='쿠버네티스 여부')
    latest_check_date = models.DateTimeField(blank=True, null=True, verbose_name='최근 점검일')
    latest_security_status = models.CharField(
        max_length=20, blank=True, null=True,
        choices=[('pass', '양호'), ('fail', '취약'), ('warn', '주의'), ('not_applicable', '해당없음')],
        verbose_name='최근 보안 상태'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    
    class Meta:
        db_table = 'dashboard_asset'
        verbose_name = '자산'
        verbose_name_plural = '자산 목록'
        ordering = ['-latest_check_date']
    
    def __str__(self):
        return f"{self.name} ({self.hostname or self.asset_code})"

class SecurityCheck(models.Model):
    """보안 점검 결과"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='security_checks', verbose_name='자산')
    check_date = models.DateTimeField(verbose_name='점검 날짜')
    generated_at = models.CharField(max_length=100, blank=True, null=True, verbose_name='생성 시각')
    total_checks = models.IntegerField(default=0, verbose_name='총 점검 수')
    passed_checks = models.IntegerField(default=0, verbose_name='양호 수')
    failed_checks = models.IntegerField(default=0, verbose_name='취약 수')
    warning_checks = models.IntegerField(default=0, verbose_name='주의 수')
    not_applicable_checks = models.IntegerField(default=0, verbose_name='해당없음 수')
    status = models.CharField(
        max_length=20,
        choices=[('pass', '양호'), ('fail', '취약'), ('warn', '주의'), ('not_applicable', '해당없음')],
        verbose_name='전체 보안 상태'
    )
    details = models.JSONField(verbose_name='상세 점검 내역')
    report_info = models.JSONField(blank=True, null=True, verbose_name='리포트 정보')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    
    class Meta:
        db_table = 'dashboard_securitycheck'
        verbose_name = '보안 점검'
        verbose_name_plural = '보안 점검 목록'
        ordering = ['-check_date']
    
    def __str__(self):
        return f"{self.asset.name} - {self.check_date.strftime('%Y-%m-%d %H:%M')}"
    
    def get_pass_rate(self):
        if self.total_checks == 0:
            return 0
        return round((self.passed_checks / self.total_checks) * 100, 1)
