from django.db import models
from django.utils import timezone


class CheckRound(models.Model):
    """점검 회차 - 날짜별로 회차 관리"""
    check_date = models.DateField(verbose_name='점검 날짜')
    round_number = models.IntegerField(default=1, verbose_name='회차 번호')
    check_time = models.TimeField(verbose_name='점검 시각')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')

    class Meta:
        db_table = 'dashboard_checkround'
        verbose_name = '점검 회차'
        verbose_name_plural = '점검 회차 목록'
        # 전부 내림차순 (DESC): 날짜, 시간, 회차번호
        ordering = ['-check_date', '-check_time', '-round_number']
        unique_together = ['check_date', 'check_time']

    def __str__(self):
        return f"{self.check_date} {self.round_number}회차 ({self.check_time.strftime('%H:%M:%S')})"

    def get_total_assets(self):
        """이 회차의 총 자산 수"""
        return self.security_checks.values('asset').distinct().count()

    def get_statistics(self):
        """이 회차의 통계 정보"""
        checks = self.security_checks.all()
        stats = {
            'total_passed': sum(c.passed_checks for c in checks),
            'total_warnings': sum(c.warning_checks for c in checks),
            'total_failed': sum(c.failed_checks for c in checks),
            'total_na': sum(c.not_applicable_checks for c in checks),
        }
        stats['total_checks'] = sum(stats.values())
        return stats

    def get_datetime_str(self):
        """날짜와 시각을 결합한 문자열"""
        return f"{self.check_date} {self.check_time.strftime('%H:%M:%S')}"


class Asset(models.Model):
    """자산 정보"""
    asset_code = models.CharField(max_length=100, unique=True, verbose_name='자산 코드')
    name = models.CharField(max_length=200, verbose_name='자산명')
    hostname = models.CharField(max_length=200, blank=True, null=True, verbose_name='호스트')
    distro = models.CharField(max_length=50, blank=True, null=True, verbose_name='배포판')
    os_version = models.CharField(max_length=100, blank=True, null=True, verbose_name='OS 버전')
    kernel = models.CharField(max_length=100, blank=True, null=True, verbose_name='커널 버전')
    execution_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='실행 방식')
    is_container = models.BooleanField(default=False, verbose_name='컨테이너 여부')
    is_kubernetes = models.BooleanField(default=False, verbose_name='쿠버네티스 여부')
    latest_check_date = models.DateTimeField(blank=True, null=True, verbose_name='최근 점검일')
    latest_security_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ('pass', '양호'),
            ('fail', '취약'),
            ('warn', '주의'),
            ('not_applicable', '해당없음')
        ],
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

    def get_latest_check(self):
        """가장 최근 점검 결과"""
        return self.security_checks.order_by('-check_date').first()


class SecurityCheck(models.Model):
    """보안 점검 결과"""
    round = models.ForeignKey(
        CheckRound,
        on_delete=models.CASCADE,
        related_name='security_checks',
        verbose_name='점검 회차'
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='security_checks',
        verbose_name='자산'
    )
    check_date = models.DateTimeField(verbose_name='점검 날짜시각')
    generated_at = models.CharField(max_length=100, blank=True, null=True, verbose_name='생성 시각')
    total_checks = models.IntegerField(default=0, verbose_name='총 점검 수')
    passed_checks = models.IntegerField(default=0, verbose_name='양호 수')
    failed_checks = models.IntegerField(default=0, verbose_name='취약 수')
    warning_checks = models.IntegerField(default=0, verbose_name='주의 수')
    not_applicable_checks = models.IntegerField(default=0, verbose_name='해당없음 수')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pass', '양호'),
            ('fail', '취약'),
            ('warn', '주의'),
            ('not_applicable', '해당없음')
        ],
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
        unique_together = ['round', 'asset']

    def __str__(self):
        return f"{self.asset.name} - {self.round}"

    def get_pass_rate(self):
        """합격률 계산"""
        if self.total_checks == 0:
            return 0
        return round((self.passed_checks / self.total_checks) * 100, 1)
