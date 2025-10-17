import json
import os
from datetime import datetime, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Asset, SecurityCheck, CheckRound

class Command(BaseCommand):
    help = '보안 점검 JSON 파일을 PostgreSQL로 임포트 (회차 자동 생성)'

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
                round_count = CheckRound.objects.count()
                SecurityCheck.objects.all().delete()
                Asset.objects.all().delete()
                CheckRound.objects.all().delete()
                self.stdout.write(self.style.WARNING(
                    f'기존 데이터 삭제: 회차 {round_count}개, 자산 {asset_count}개, 점검 {check_count}개'
                ))
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

        # 파일들을 시간대별로 그룹화
        time_groups = {}
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    report_info = data.get('report_info', {})
                    generated_at = report_info.get('generated_at', '')
                    
                    try:
                        check_datetime = datetime.strptime(generated_at, '%Y-%m-%d %H:%M:%S')
                        check_datetime = timezone.make_aware(check_datetime)
                    except:
                        check_datetime = timezone.now()
                    
                    # 정확한 시간 (분까지만 사용, 초는 무시)
                    time_key = check_datetime.replace(second=0, microsecond=0)
                    
                    if time_key not in time_groups:
                        time_groups[time_key] = []
                    time_groups[time_key].append((json_file, data, check_datetime))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'파일 읽기 실패 {json_file}: {str(e)}'))

        # 시간대별로 회차 생성 및 데이터 임포트
        total_imported = 0
        total_errors = 0

        for time_key in sorted(time_groups.keys()):
            files_in_group = time_groups[time_key]
            check_date = time_key.date()
            check_time = time_key.time()
            
            # 같은 날짜와 시간에 이미 회차가 있는지 확인 (가장 중요!)
            existing_round = CheckRound.objects.filter(
                check_date=check_date,
                check_time=check_time
            ).first()
            
            if existing_round:
                # 기존 회차 사용
                check_round = existing_round
                self.stdout.write(self.style.WARNING(
                    f'\n📅 {check_date} {check_round.round_number}회차 (기존) - {check_time.strftime("%H:%M:%S")} ({len(files_in_group)}개 파일 추가)'
                ))
            else:
                # 새 회차 생성 - 해당 날짜의 마지막 회차 번호 + 1
                last_round = CheckRound.objects.filter(check_date=check_date).order_by('-round_number').first()
                round_number = (last_round.round_number + 1) if last_round else 1
                
                # 회차 생성
                check_round = CheckRound.objects.create(
                    check_date=check_date,
                    round_number=round_number,
                    check_time=check_time
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f'\n📅 {check_date} {round_number}회차 생성 - {check_time.strftime("%H:%M:%S")} ({len(files_in_group)}개 파일)'
                ))
            
            # 해당 회차에 파일들 임포트
            for json_file, data, check_datetime in files_in_group:
                try:
                    result = self.import_json_file(json_file, data, check_datetime, check_round)
                    if result:
                        total_imported += 1
                        self.stdout.write(self.style.SUCCESS(f'  ✓ {os.path.basename(json_file)}'))
                    else:
                        total_errors += 1
                except Exception as e:
                    total_errors += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ {os.path.basename(json_file)}: {str(e)}'))

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'임포트 완료: 성공 {total_imported}개, 실패 {total_errors}개'))
        self.stdout.write(self.style.SUCCESS(f'총 회차: {CheckRound.objects.count()}개'))
        self.stdout.write(self.style.SUCCESS(f'총 자산: {Asset.objects.count()}개'))
        self.stdout.write(self.style.SUCCESS(f'총 점검: {SecurityCheck.objects.count()}개'))
        self.stdout.write('=' * 70)

    def import_json_file(self, json_file, data, check_date, check_round):
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

        # 회차와 연결하여 점검 결과 생성
        security_check, created = SecurityCheck.objects.update_or_create(
            round=check_round,
            asset=asset,
            defaults={
                'check_date': check_date,
                'generated_at': report_info.get('generated_at', ''),
                'total_checks': summary.get('total_checks', 0),
                'passed_checks': summary.get('pass', 0),
                'failed_checks': summary.get('fail', 0),
                'warning_checks': summary.get('warn', 0),
                'not_applicable_checks': summary.get('not_applicable', 0),
                'status': overall_status,
                'details': checks,
                'report_info': report_info,
            }
        )

        action = '생성' if created else '업데이트'
        self.stdout.write(f'    └─ 자산 {action}: {asset.name} ({asset.asset_code})')
        self.stdout.write(f'       점검: {check_date.strftime("%Y-%m-%d %H:%M")} | 상태: {overall_status} | 양호: {summary.get("pass", 0)} | 취약: {summary.get("fail", 0)}')

        return True
