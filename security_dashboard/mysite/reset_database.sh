#!/bin/bash

echo "========================================"
echo "PostgreSQL 데이터베이스 초기화"
echo "========================================"

# 프로젝트 경로로 이동 (실제 경로로 수정 필요)
cd /var/www/security_dashboard/mysite

# 가상환경 활성화 (실제 경로로 수정 필요)
source venv/bin/activate

echo ""
echo "현재 데이터 개수:"
python manage.py shell << EOF
from dashboard.models import Asset, SecurityCheck, CheckRound

asset_count = Asset.objects.count()
check_count = SecurityCheck.objects.count()
round_count = CheckRound.objects.count()

print(f"  CheckRound (회차): {round_count}개")
print(f"  Asset (자산): {asset_count}개")
print(f"  SecurityCheck (점검): {check_count}개")
EOF

echo ""
read -p "정말 삭제하시겠습니까? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo ""
    echo "데이터 삭제 중..."
    
    python manage.py shell << EOF
from dashboard.models import Asset, SecurityCheck, CheckRound

# 순서대로 삭제 (외래키 관계 때문)
SecurityCheck.objects.all().delete()
Asset.objects.all().delete()
CheckRound.objects.all().delete()

print("✅  삭제 완료")
EOF

    echo ""
    echo "삭제 후 데이터 개수:"
    python manage.py shell << EOF
from dashboard.models import Asset, SecurityCheck, CheckRound

print(f"  CheckRound (회차): {CheckRound.objects.count()}개")
print(f"  Asset (자산): {Asset.objects.count()}개")
print(f"  SecurityCheck (점검): {SecurityCheck.objects.count()}개")
EOF

    echo ""
    read -p "업로드된 JSON 파일도 삭제하시겠습니까? (yes/no): " confirm_files
    
    if [ "$confirm_files" = "yes" ]; then
        # JSON 파일 경로 (실제 경로로 수정 필요)
        JSON_DIR="/var/www/uploads/pod_results"
        
        if [ -d "$JSON_DIR" ] && [ "$(ls -A $JSON_DIR/*.json 2>/dev/null)" ]; then
            echo "JSON 파일 백업 중..."
            BACKUP_DIR=~/json_backup_$(date +%Y%m%d_%H%M%S)
            mkdir -p $BACKUP_DIR
            cp $JSON_DIR/*.json $BACKUP_DIR/ 2>/dev/null
            echo "✅  백업 완료: $BACKUP_DIR"
            
            echo "JSON 파일 삭제 중..."
            rm -f $JSON_DIR/*.json
            echo "✅  파일 삭제 완료"
        else
            echo "삭제할 JSON 파일이 없습니다."
        fi
    fi
    
    echo ""
    echo "========================================"
    echo "초기화 완료!"
    echo "========================================"
    echo ""
    echo "다음 명령어로 새 데이터를 임포트하세요:"
    echo "python manage.py import_security_data /path/to/json/files/"
    echo ""
else
    echo "취소되었습니다."
fi
