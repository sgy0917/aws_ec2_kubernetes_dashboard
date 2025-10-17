# dashboard/management/commands/merge_duplicate_rounds.py
from django.core.management.base import BaseCommand
from django.db.models import Count
from dashboard.models import CheckRound, SecurityCheck


class Command(BaseCommand):
    help = '같은 날짜, 같은 시간의 중복 회차를 하나로 병합'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 병합하지 않고 확인만',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('중복 회차 병합 스크립트'))
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # 같은 날짜, 같은 시간을 가진 회차 그룹 찾기
        rounds = CheckRound.objects.all().order_by('check_date', 'check_time', 'round_number')
        
        time_groups = {}
        for round_obj in rounds:
            key = (round_obj.check_date, round_obj.check_time)
            if key not in time_groups:
                time_groups[key] = []
            time_groups[key].append(round_obj)

        # 중복 회차 찾기
        duplicates = {k: v for k, v in time_groups.items() if len(v) > 1}

        if not duplicates:
            self.stdout.write(self.style.SUCCESS('중복된 회차가 없습니다! ✓'))
            return

        self.stdout.write(self.style.WARNING(f'중복된 시간대: {len(duplicates)}개'))
        self.stdout.write('')

        total_merged = 0

        for (check_date, check_time), round_list in sorted(duplicates.items()):
            self.stdout.write(self.style.HTTP_INFO(
                f'\n📅 {check_date} {check_time.strftime("%H:%M:%S")}'
            ))
            self.stdout.write(f'   중복 회차: {len(round_list)}개')

            # 각 회차 정보 표시
            for r in round_list:
                check_count = r.security_checks.count()
                self.stdout.write(f'   - {r.round_number}회차 (자산 {check_count}개)')

            # 첫 번째 회차(번호가 가장 작은)를 메인으로 사용
            main_round = min(round_list, key=lambda x: x.round_number)
            other_rounds = [r for r in round_list if r.id != main_round.id]

            self.stdout.write(self.style.SUCCESS(
                f'\n   ➜ {main_round.round_number}회차로 병합 (메인)'
            ))

            if not dry_run:
                # 다른 회차의 SecurityCheck를 메인 회차로 이동
                for other_round in other_rounds:
                    checks = SecurityCheck.objects.filter(round=other_round)
                    moved_count = 0

                    for check in checks:
                        # 같은 자산의 점검이 이미 있는지 확인
                        existing = SecurityCheck.objects.filter(
                            round=main_round,
                            asset=check.asset
                        ).first()

                        if existing:
                            # 이미 있으면 중복이므로 삭제
                            check.delete()
                            self.stdout.write(f'     중복 제거: {check.asset.name}')
                        else:
                            # 없으면 메인 회차로 이동
                            check.round = main_round
                            check.save()
                            moved_count += 1

                    self.stdout.write(f'   ✓ {other_round.round_number}회차에서 {moved_count}개 이동')

                    # 빈 회차 삭제
                    other_round.delete()
                    self.stdout.write(f'   ✓ {other_round.round_number}회차 삭제')

                total_merged += len(other_rounds)
            else:
                self.stdout.write(self.style.WARNING('   (dry-run 모드 - 실제 병합하지 않음)'))

        self.stdout.write('')
        self.stdout.write('=' * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN 완료 - 실제 병합되지 않았습니다'))
            self.stdout.write('실제 병합하려면: python manage.py merge_duplicate_rounds')
        else:
            self.stdout.write(self.style.SUCCESS(f'병합 완료! {total_merged}개 회차 병합됨'))
            
            # 병합 후 회차 번호 재정렬
            self.stdout.write('')
            self.stdout.write('회차 번호 재정렬 중...')
            self.renumber_rounds()
            self.stdout.write(self.style.SUCCESS('✓ 재정렬 완료'))

        self.stdout.write('=' * 70)

    def renumber_rounds(self):
        """날짜별로 회차 번호를 시간 순서대로 재정렬 (이른 시간 = 1회차)"""
        dates = CheckRound.objects.values_list('check_date', flat=True).distinct()

        for date in dates:
            # 시간 오름차순으로 정렬 (이른 시간부터)
            rounds = CheckRound.objects.filter(check_date=date).order_by('check_time')
            
            for idx, round_obj in enumerate(rounds, start=1):
                if round_obj.round_number != idx:
                    round_obj.round_number = idx
                    round_obj.save()
                    self.stdout.write(f'  {date} {round_obj.check_time.strftime("%H:%M:%S")} → {idx}회차')
