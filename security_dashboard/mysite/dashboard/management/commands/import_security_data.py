import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Asset, SecurityCheck

class Command(BaseCommand):
    help = '보안 점검 JSON 파일을 PostgreSQL로 임포트'

    def add_arguments(self, parser):
        parser.add_argument('json_path', type=str, help='JSON 파일 또는 디렉토리 경로')
        parser.add_argument('--clear', action='store_true', help='기존 데이터 삭제 후 임포트')

    def handle(self, *args, **options):
        json_path = options['json_path']
        clear = options['clear']

        if clear:
            try:
                check_count = SecurityCheck.objects.count()
                asset_count = Asset.objects.count()
                SecurityCheck.objects.all().delete()
                Asset.objects.all().delete()
                self.stdout.write(self.style.WARNING(f'기존 데이터 삭제: 자산 {asset_count}개, 점검 {check_count}개'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'데이터 삭제 중 오류: {str(e)}'))

        json_files = []
        if os.path.isfile(json_path):
            json_files = [json_path]
        elif os.path.isdir(json_path):
            json_files = [os.path.join(json_path, f) for f in os.listdir(json_path) if f.endswith('.json')]
        else:
            self.stdout.write(self.style.ERROR(f'경로를 찾을 수 없습니다: {json_path}'))
            return

        if not json_files:
            self.stdout.write(self.style.ERROR('JSON 파일을 찾을 수 없습니다.'))
            return

        self.stdout.write(self.style.SUCCESS(f'총 {len(json_files)}개 파일 발견'))

        total_imported = 0
        total_errors = 0

        for json_file in json_files:
            try:
                result = self.import_json_file(json_file)
                if result:
                    total_imported += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ {os.path.basename(json_file)}'))
                else:
                    total_errors += 1
            except Exception as e:
                total_errors += 1
                self.stdout.write(self.style.ERROR(f'✗ {os.path.basename(json_file)}: {str(e)}'))

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'임포트 완료: 성공 {total_imported}개, 실패 {total_errors}개'))
        self.stdout.write(self.style.SUCCESS(f'총 자산: {Asset.objects.count()}개'))
        self.stdout.write(self.style.SUCCESS(f'총 점검: {SecurityCheck.objects.count()}개'))
        self.stdout.write('=' * 70)

    def import_json_file(self, json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        report_info = data.get('report_info', {})
        summary = data.get('summary', {})
        checks = data.get('checks', [])

        if not report_info:
            self.stdout.write(self.style.WARNING(f'report_info가 없습니다: {json_file}'))
            return False

        hostname = report_info.get('hostname', 'unknown')
        distro = report_info.get('distro', '')
        version = report_info.get('version', '')
        asset_code = hostname
        asset_name = f"{distro.capitalize()} {version}" if distro else hostname
        
        generated_at = report_info.get('generated_at', '')
        try:
            check_date = datetime.strptime(generated_at, '%Y-%m-%d %H:%M:%S')
            check_date = timezone.make_aware(check_date)
        except:
            check_date = timezone.now()

        asset, created = Asset.objects.update_or_create(
            asset_code=asset_code,
            defaults={
                'name': asset_name,
                'hostname': hostname,
                'distro': distro,
                'os_version': version,
                'kernel': report_info.get('kernel', ''),
                'execution_type': report_info.get('execution_mode', ''),
                'is_container': report_info.get('is_container', False),
                'is_kubernetes': report_info.get('is_kubernetes', False),
                'latest_check_date': check_date,
            }
        )

        if summary.get('fail', 0) > 0:
            overall_status = 'fail'
        elif summary.get('warn', 0) > 0:
            overall_status = 'warn'
        elif summary.get('pass', 0) > 0:
            overall_status = 'pass'
        else:
            overall_status = 'not_applicable'

        asset.latest_security_status = overall_status
        asset.save()

        security_check = SecurityCheck.objects.create(
            asset=asset,
            check_date=check_date,
            generated_at=generated_at,
            total_checks=summary.get('total_checks', 0),
            passed_checks=summary.get('pass', 0),
            failed_checks=summary.get('fail', 0),
            warning_checks=summary.get('warn', 0),
            not_applicable_checks=summary.get('not_applicable', 0),
            status=overall_status,
            details=checks,
            report_info=report_info,
        )

        action = '생성' if created else '업데이트'
        self.stdout.write(f'  └─ 자산 {action}: {asset.name} ({asset.asset_code})')
        self.stdout.write(f'     점검: {check_date.strftime("%Y-%m-%d %H:%M")} | 상태: {overall_status} | 양호: {summary.get("pass", 0)} | 취약: {summary.get("fail", 0)}')

        return True
