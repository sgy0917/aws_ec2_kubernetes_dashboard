from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q, Sum, Avg
from datetime import datetime, timedelta
from collections import defaultdict
from dashboard.models import Asset, SecurityCheck, CheckRound
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import requests
import subprocess
import os
import time
from django.conf import settings  

API_SERVER_URL = settings.API_SERVER_URL

def index(request):
    """
    메인 대시보드
    - 회차별 점검 통계 그래프
    - 자산 비용 그래프
    - 점검 시작 버튼
    """
    # 최근 7일간의 회차별 통계
    seven_days_ago = datetime.now().date() - timedelta(days=7)
    recent_rounds = CheckRound.objects.filter(
        check_date__gte=seven_days_ago
    ).order_by('check_date', 'round_number')
    
    # 그래프 데이터 생성
    chart_dates = []
    chart_passed = []
    chart_failed = []
    chart_warnings = []
    
    for round_obj in recent_rounds:
        stats = round_obj.get_statistics()
        chart_dates.append(f"{round_obj.check_date.strftime('%m/%d')} {round_obj.round_number}회차")
        chart_passed.append(stats['total_passed'])
        chart_failed.append(stats['total_failed'])
        chart_warnings.append(stats['total_warnings'])
    
    # 자산별 비용 계산
    assets = Asset.objects.all()
    asset_costs = []
    
    for asset in assets:
        distro = asset.distro.lower() if asset.distro else ''
        if 'alpine' in distro:
            vcpu = 1
            memory_gb = 1
            cost = (vcpu * 50) + (memory_gb * 10)
        elif 'ubuntu' in distro:
            vcpu = 2
            memory_gb = 4
            cost = (vcpu * 50) + (memory_gb * 10)
        elif 'debian' in distro:
            vcpu = 2
            memory_gb = 2
            cost = (vcpu * 50) + (memory_gb * 10)
        else:
            vcpu = 1
            memory_gb = 1
            cost = (vcpu * 50) + (memory_gb * 10)
        
        asset_costs.append({
            'name': asset.name,
            'vcpu': vcpu,
            'memory_gb': memory_gb,
            'cost': cost
        })
    
    # 전체 통계
    total_assets = Asset.objects.count()
    total_rounds = CheckRound.objects.count()
    latest_round = CheckRound.objects.order_by('-check_date', '-round_number').first()
    
    latest_stats = {}
    if latest_round:
        latest_stats = latest_round.get_statistics()
    
    # 인프라 월간 비용
    infrastructure_cost = sum(item['cost'] for item in asset_costs) if asset_costs else 0
    
    # 점검 비용 계산
    CHECK_COST_PER_RUN = 10  # 점검 1회당 $10
    total_check_cost = total_rounds * CHECK_COST_PER_RUN
    
    # 총 비용
    total_cost = infrastructure_cost + total_check_cost
    
    # API 서버 상태 확인
    api_server_status = check_api_server_status()
    
    context = {
        'total_assets': total_assets,
        'total_rounds': total_rounds,
        'latest_round': latest_round,
        'latest_stats': latest_stats,
        'total_cost': total_cost,
        'infrastructure_cost': infrastructure_cost,
        'total_check_cost': total_check_cost,
        'check_cost_per_run': CHECK_COST_PER_RUN,
        'api_server_status': api_server_status,
        
        'chart_dates': json.dumps(chart_dates),
        'chart_passed': json.dumps(chart_passed),
        'chart_failed': json.dumps(chart_failed),
        'chart_warnings': json.dumps(chart_warnings),
        
        'asset_costs': asset_costs,
        'cost_labels': json.dumps([item['name'] for item in asset_costs]),
        'cost_data': json.dumps([item['cost'] for item in asset_costs]),
    }
    
    return render(request, 'dashboard/index.html', context)

def check_api_server_status():
    """API 서버 실행 상태 확인"""
    try:
        # /api 경로 추가!
        response = requests.get(f'{API_SERVER_URL}/api/health', timeout=2)
        if response.status_code == 200:
            return 'running'
    except Exception as e:
        print(f"[API 서버 상태 확인 실패] {e}")
    return 'stopped'


def start_check(request):
    """점검 시작 API"""
    if request.method == 'POST':
        try:
            print("="*60)
            print("📝 점검 시작 요청 받음")
            print("="*60)
            
            # /api 경로 추가!
            response = requests.post(
                f'{API_SERVER_URL}/api/start_check',  # ← 이렇게!
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 점검 시작 성공: {result}")
                
                return JsonResponse({
                    'success': True,
                    'message': '점검이 시작되었습니다.'
                })
            else:
                print(f"❌ 점검 시작 실패: HTTP {response.status_code}")
                return JsonResponse({
                    'success': False,
                    'message': f'점검 시작 실패: HTTP {response.status_code}'
                }, status=500)
        
        except requests.exceptions.ConnectionError:
            print("❌ Flask API 서버 연결 실패")
            return JsonResponse({
                'success': False,
                'message': 'Flask API 서버에 연결할 수 없습니다. API 서버를 먼저 시작해주세요.'
            }, status=500)
        
        except Exception as e:
            print(f"❌ 오류: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'서버 오류: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'POST 요청만 허용됩니다.'
    }, status=405)

def rounds_list(request):
    """회차 목록 페이지 (기존 index)"""
    filter_date = request.GET.get('date', '')
    filter_round = request.GET.get('round', '')
    
    # 디버깅용 출력
    print(f"[필터링] 받은 날짜: '{filter_date}', 받은 회차: '{filter_round}'")
    
    rounds_query = CheckRound.objects.all()
    
    # 날짜 필터
    if filter_date:
        try:
            # 여러 날짜 형식 시도
            for date_format in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
                try:
                    filter_date_obj = datetime.strptime(filter_date, date_format).date()
                    rounds_query = rounds_query.filter(check_date=filter_date_obj)
                    print(f"[필터링] 날짜 필터 적용: {filter_date_obj}")
                    break
                except ValueError:
                    continue
        except Exception as e:
            print(f"[필터링] 날짜 파싱 실패: {e}")
    
    # 회차 필터
    if filter_round:
        try:
            filter_round_num = int(filter_round)
            rounds_query = rounds_query.filter(round_number=filter_round_num)
            print(f"[필터링] 회차 필터 적용: {filter_round_num}")
        except ValueError as e:
            print(f"[필터링] 회차 파싱 실패: {e}")
    
    # 필터 결과 확인
    print(f"[필터링] 결과 개수: {rounds_query.count()}개")
    
    rounds_by_date = defaultdict(list)
    
    for round_obj in rounds_query:
        round_data = {
            'id': round_obj.id,
            'round_number': round_obj.round_number,
            'check_time': round_obj.check_time.strftime('%H:%M:%S'),
            'datetime_str': round_obj.get_datetime_str(),
            'total_assets': round_obj.get_total_assets(),
            'stats': round_obj.get_statistics(),
        }
        rounds_by_date[round_obj.check_date].append(round_data)
    
    rounds_list = []
    for date in sorted(rounds_by_date.keys(), reverse=True):
        rounds_list.append({
            'date': date,
            'rounds': rounds_by_date[date]
        })
    
    # 전체 날짜 목록
    all_dates = CheckRound.objects.values_list('check_date', flat=True).distinct().order_by('-check_date')
    
    # 전체 회차 목록 (중복 제거하고 정렬)
    all_rounds = CheckRound.objects.values_list('round_number', flat=True).distinct().order_by('round_number')
    
    context = {
        'rounds_list': rounds_list,
        'all_dates': all_dates,
        'all_rounds': all_rounds,
        'filter_date': filter_date,
        'filter_round': filter_round,
    }
    
    return render(request, 'dashboard/rounds_list.html', context)

def round_detail(request, round_id):
    """회차별 자산 목록"""
    check_round = get_object_or_404(CheckRound, id=round_id)
    security_checks = SecurityCheck.objects.filter(round=check_round).select_related('asset')
    
    assets_data = []
    for check in security_checks:
        asset = check.asset
        assets_data.append({
            'id': asset.id,
            'asset_code': asset.asset_code,
            'name': asset.name,
            'hostname': asset.hostname,
            'distro': asset.distro,
            'os_version': asset.os_version,
            'execution_type': asset.execution_type,
            'check_date': check.check_date,
            'passed': check.passed_checks,
            'warnings': check.warning_checks,
            'failed': check.failed_checks,
            'na': check.not_applicable_checks,
            'status': check.status,
        })
    
    context = {
        'check_round': check_round,
        'assets': assets_data,
        'total_assets': len(assets_data),
    }
    
    return render(request, 'dashboard/list.html', context)


def asset_detail(request, asset_id):
    """자산 상세 페이지"""
    asset = get_object_or_404(Asset, id=asset_id)
    latest_check = SecurityCheck.objects.filter(asset=asset).order_by('-check_date').first()
    
    if not latest_check:
        context = {
            'asset': asset,
            'error_message': '점검 데이터가 없습니다.'
        }
        return render(request, 'dashboard/asset_detail.html', context)
    
    check_details = latest_check.details if latest_check.details else []
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        if status_filter == 'pass':
            check_details = [c for c in check_details if c.get('status') in ['양호', 'pass']]
        elif status_filter == 'fail':
            check_details = [c for c in check_details if c.get('status') in ['취약', 'fail']]
        elif status_filter == 'warn':
            check_details = [c for c in check_details if c.get('status') in ['주의', 'warn']]
        elif status_filter == 'not_applicable':
            check_details = [c for c in check_details if c.get('status') in ['해당없음', 'not_applicable', '해당 없음']]
    
    for check in check_details:
        status = check.get('status', '')
        if status in ['pass', 'PASS']:
            check['status_normalized'] = 'pass'
            check['status_display'] = '양호'
        elif status in ['fail', 'FAIL', '취약']:
            check['status_normalized'] = 'fail'
            check['status_display'] = '취약'
        elif status in ['warn', 'WARN', '주의']:
            check['status_normalized'] = 'warn'
            check['status_display'] = '주의'
        else:
            check['status_normalized'] = 'not_applicable'
            check['status_display'] = '해당없음'
    
    chart_labels = json.dumps(['양호', '주의', '취약', '해당없음'])
    chart_data = json.dumps([
        latest_check.passed_checks,
        latest_check.warning_checks,
        latest_check.failed_checks,
        latest_check.not_applicable_checks
    ])
    
    context = {
        'asset': asset,
        'latest_check': latest_check,
        'check_round': latest_check.round,
        'check_details': check_details,
        'total_checks': latest_check.total_checks,
        'passed_checks': latest_check.passed_checks,
        'warning_checks': latest_check.warning_checks,
        'failed_checks': latest_check.failed_checks,
        'not_applicable_checks': latest_check.not_applicable_checks,
        'pass_rate': latest_check.get_pass_rate(),
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'status_filter': status_filter,
    }
    
    return render(request, 'dashboard/asset_detail.html', context)


def export_asset_excel(request, asset_id):
    """자산 점검 결과 Excel 다운로드"""
    asset = get_object_or_404(Asset, id=asset_id)
    latest_check = SecurityCheck.objects.filter(asset=asset).order_by('-check_date').first()
    
    if not latest_check:
        return HttpResponse("점검 데이터가 없습니다.", status=404)
    
    wb = Workbook()
    ws = wb.active
    ws.title = "점검 결과"
    
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    
    pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    warn_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    na_fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = f"보안 점검 결과 리포트 - {asset.name}"
    title_cell.font = Font(size=16, bold=True)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    
    ws['A3'] = "자산 정보"
    ws['A3'].font = Font(bold=True, size=14)
    
    info_data = [
        ["자산 코드", asset.asset_code],
        ["자산명", asset.name],
        ["호스트", asset.hostname or "N/A"],
        ["배포판", asset.distro or "Unknown"],
        ["OS 버전", asset.os_version or "Unknown"],
        ["커널 버전", asset.kernel or "N/A"],
        ["실행 방식", asset.execution_type or "N/A"],
        ["점검 일시", latest_check.check_date.strftime("%Y-%m-%d %H:%M:%S")],
    ]
    
    row = 4
    for label, value in info_data:
        ws[f'A{row}'] = label
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = value
        row += 1
    
    row += 1
    ws[f'A{row}'] = "점검 통계"
    ws[f'A{row}'].font = Font(bold=True, size=14)
    
    row += 1
    stats_data = [
        ["총 점검 수", latest_check.total_checks],
        ["양호", latest_check.passed_checks],
        ["주의", latest_check.warning_checks],
        ["취약", latest_check.failed_checks],
        ["해당없음", latest_check.not_applicable_checks],
        ["합격률", f"{latest_check.get_pass_rate()}%"],
    ]
    
    for label, value in stats_data:
        ws[f'A{row}'] = label
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = value
        row += 1
    
    row += 2
    ws[f'A{row}'] = "상세 점검 결과"
    ws[f'A{row}'].font = Font(bold=True, size=14)
    
    row += 1
    headers = ["번호", "점검ID", "점검명", "상태", "점검내용", "점검경로", "실행명령어", "권장사항"]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 40
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 30
    ws.column_dimensions['H'].width = 40
    
    if latest_check.details:
        for idx, check in enumerate(latest_check.details, 1):
            row += 1
            
            status = check.get('status', '')
            
            if status in ['양호', 'pass']:
                status_kr = '양호'
                fill = pass_fill
            elif status in ['취약', 'fail']:
                status_kr = '취약'
                fill = fail_fill
            elif status in ['주의', 'warn']:
                status_kr = '주의'
                fill = warn_fill
            else:
                status_kr = '해당없음'
                fill = na_fill
            
            data_row = [
                idx,
                check.get('id', ''),
                check.get('name', ''),
                status_kr,
                check.get('details', ''),
                check.get('checked_paths', ''),
                check.get('commands_executed', ''),
                check.get('recommendation', '')
            ]
            
            for col, value in enumerate(data_row, 1):
                cell = ws.cell(row=row, column=col)
                cell.value = value
                cell.border = border
                cell.alignment = Alignment(vertical='top', wrap_text=True)
                
                if col == 4:
                    cell.fill = fill
                    cell.alignment = Alignment(horizontal='center', vertical='center')
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    filename = f"security_check_{asset.asset_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response
