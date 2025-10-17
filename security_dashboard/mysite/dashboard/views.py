from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Count, Sum
from datetime import datetime, timedelta
from dashboard.models import Asset, SecurityCheck
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def dashboard(request):
    """메인 대시보드"""

    # 날짜 필터 처리
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    date_error = None

    # 기본 쿼리셋
    security_checks_query = SecurityCheck.objects.all()

    # 날짜 필터링
    if date_from and date_to:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')

            # 1달(30일) 제한 검증
            date_diff = (date_to_obj - date_from_obj).days
            if date_diff < 0:
                date_error = "종료 날짜는 시작 날짜보다 이후여야 합니다."
            elif date_diff > 30:
                date_error = "날짜 범위는 최대 30일까지만 선택할 수 있습니다."
            else:
                # 날짜 범위로 필터링
                security_checks_query = security_checks_query.filter(
                    check_date__gte=date_from_obj,
                    check_date__lte=date_to_obj + timedelta(days=1)  # 종료일 포함
                ) 
        except ValueError:
            date_error = "올바른 날짜 형식이 아닙니다."

    # 필터링된 점검 결과에서 자산 목록 가져오기
    if not date_error and (date_from and date_to):
        # 날짜 범위 내의 자산만 가져오기
        asset_ids = security_checks_query.values_list('asset_id', flat=True).distinct()
        assets = Asset.objects.filter(id__in=asset_ids).order_by('-latest_check_date')
    else:
        # 전체 자산
        assets = Asset.objects.all().order_by('-latest_check_date')

    total_assets = assets.count()

    # 각 자산의 상세 점검 개수 계산
    assets_with_counts = []
    total_passed = 0
    total_warnings = 0
    total_failed = 0
    total_na = 0
    for asset in assets:
        # 날짜 필터가 있으면 해당 기간의 점검만, 없으면 최근 점검
        if date_from and date_to and not date_error:
            latest_check = security_checks_query.filter(asset=asset).order_by('-check_date').first()
        else:
            latest_check = SecurityCheck.objects.filter(asset=asset).order_by('-check_date').first()

        if latest_check:
            # 각 자산의 통계
            asset.pass_count = latest_check.passed_checks
            asset.warn_count = latest_check.warning_checks
            asset.fail_count = latest_check.failed_checks
            asset.na_count = latest_check.not_applicable_checks

            # 점검 날짜도 표시용으로 저장
            asset.filtered_check_date = latest_check.check_date

            # 전체 통계 누적
            total_passed += latest_check.passed_checks
            total_warnings += latest_check.warning_checks
            total_failed += latest_check.failed_checks
            total_na += latest_check.not_applicable_checks
        else:
            asset.pass_count = 0
            asset.warn_count = 0
            asset.fail_count = 0
            asset.na_count = 0
            asset.filtered_check_date = None

        assets_with_counts.append(asset)

    # 마지막 업데이트 시간 (가장 최근 점검 데이터의 생성 시간)
    latest_check_all = SecurityCheck.objects.order_by('-check_date').first()
    if latest_check_all and latest_check_all.generated_at:
        last_update_time = latest_check_all.generated_at
    elif latest_check_all:
        last_update_time = latest_check_all.check_date.strftime('%Y-%m-%d %H:%M:%S')
    else:
        last_update_time = "데이터 없음"

    context = {
        'assets': assets_with_counts,
        'total_assets': total_assets,
        'total_passed': total_passed,
        'total_warnings': total_warnings,
        'total_failed': total_failed,
        'total_na': total_na,
        'last_update_time': last_update_time,
        'date_from': date_from,
        'date_to': date_to,
        'date_error': date_error,
    }

    return render(request, 'dashboard/index.html', context)


def asset_detail(request, asset_id):
    """자산 상세 페이지"""

    # 자산 정보 가져오기
    asset = get_object_or_404(Asset, id=asset_id)

    # 해당 자산의 모든 보안 점검 결과
    security_checks = SecurityCheck.objects.filter(asset=asset).order_by('-check_date')

    # 필터링 처리
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # 보안 상태 필터
    if status_filter:
        security_checks = security_checks.filter(status=status_filter)

    # 날짜 범위 필터
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            security_checks = security_checks.filter(check_date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            security_checks = security_checks.filter(check_date__lte=date_to_obj)
        except ValueError:
            pass

    # 최근 점검 정보
    latest_check = security_checks.first()

    # 상세 점검 항목들의 통계 계산 (details 필드에서)
    check_details = []
    detail_passed = 0
    detail_warn = 0
    detail_fail = 0
    detail_na = 0

    if latest_check and latest_check.details:
        check_details = latest_check.details

        # details 배열에서 각 상태별 개수 계산
        for check in check_details:
            status = check.get('status', '')

            if status == '양호' or status == 'pass':
                detail_passed += 1
            elif status == '취약' or status == 'fail':
                detail_fail += 1
            elif status == '주의' or status == 'warn':
                detail_warn += 1
            elif status == '해당 없음' or status == '해당없음' or status == 'not_applicable':
                detail_na += 1

    # 통계 계산 (상세 점검 항목 기준)
    total_checks = detail_passed + detail_warn + detail_fail + detail_na

    if total_checks > 0:
        pass_rate = round((detail_passed / total_checks * 100), 1)
    else:
        pass_rate = 0

    # Chart.js용 데이터 (상세 점검 항목 통계 반영)
    chart_labels = json.dumps(['양호', '주의', '취약', '해당없음'])
    chart_data = json.dumps([detail_passed, detail_warn, detail_fail, detail_na])

    context = {
        'asset': asset,
        'security_checks': security_checks[:10],
        'total_checks': total_checks,
        'passed_checks': detail_passed,
        'failed_checks': detail_fail,
        'warning_checks': detail_warn,
        'not_applicable_checks': detail_na,
        'pass_rate': pass_rate,
        'latest_check': latest_check,
        'check_details': check_details,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        # 필터 값 유지
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'dashboard/asset_detail.html', context)


def export_asset_excel(request, asset_id):
    """자산 점검 결과 Excel 다운로드"""
    
    # 자산 정보 가져오기
    asset = get_object_or_404(Asset, id=asset_id)
    
    # 최근 점검 결과 가져오기
    latest_check = SecurityCheck.objects.filter(asset=asset).order_by('-check_date').first()
    
    if not latest_check:
        return HttpResponse("점검 데이터가 없습니다.", status=404)
    
    # Excel 워크북 생성
    wb = Workbook()
    ws = wb.active
    ws.title = "점검 결과"
    
    # 스타일 정의
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
    
    # 제목 작성
    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = f"보안 점검 결과 리포트 - {asset.name}"
    title_cell.font = Font(size=16, bold=True)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # 자산 정보 섹션
    ws['A3'] = "자산 정보"
    ws['A3'].font = Font(bold=True, size=14)
    
    info_data = [
        ["자산 코드", asset.asset_code],
        ["자산명", asset.name],
        ["호스트네임", asset.hostname or "N/A"],
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
    
    # 통계 섹션
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
    
    # 상세 점검 결과 섹션
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
    
    # 컬럼 너비 설정
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 40
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 30
    ws.column_dimensions['H'].width = 40
    
    # 상세 점검 데이터 작성
    if latest_check.details:
        for idx, check in enumerate(latest_check.details, 1):
            row += 1
            
            status = check.get('status', '')
            status_kr = status
            
            # 상태에 따른 배경색 설정
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
                
                # 상태 컬럼에 색상 적용
                if col == 4:
                    cell.fill = fill
                    cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # HTTP 응답 생성
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    filename = f"security_check_{asset.asset_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response
