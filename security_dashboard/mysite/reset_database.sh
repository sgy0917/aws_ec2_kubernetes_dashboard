#!/bin/bash

echo "========================================"
echo "PostgreSQL 데이터베이스 초기화"
echo "========================================"

cd /var/www/security_dashboard/mysite
source venv/bin/activate

echo ""
echo "현재 데이터 개수:"
python manage.py shell << EOF
from dashboard.models import Asset, SecurityCheck
print(f"  Asset: {Asset.objects.count()}개")
print(f"  SecurityCheck: {SecurityCheck.objects.count()}개")
EOF

echo ""
read -p "정말 삭제하시겠습니까? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo ""
    echo "데이터 삭제 중..."
    
    python manage.py shell << EOF
from dashboard.models import Asset, SecurityCheck
Asset.objects.all().delete()
SecurityCheck.objects.all().delete()
print("✅ 삭제 완료")
EOF

    echo ""
    echo "삭제 후 데이터 개수:"
    python manage.py shell << EOF
from dashboard.models import Asset, SecurityCheck
print(f"  Asset: {Asset.objects.count()}개")
print(f"  SecurityCheck: {SecurityCheck.objects.count()}개")
EOF

    echo ""
    read -p "업로드된 JSON 파일도 삭제하시겠습니까? (yes/no): " confirm_files
    
    if [ "$confirm_files" = "yes" ]; then
        echo "JSON 파일 백업 중..."
        mkdir -p ~/json_backup_$(date +%Y%m%d_%H%M%S)
        cp /var/www/uploads/pod_results/*.json ~/json_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo "백업할 파일 없음"
        
        echo "JSON 파일 삭제 중..."
        rm -f /var/www/uploads/pod_results/*.json
        echo "✅ 파일 삭제 완료"
    fi
    
    echo ""
    echo "========================================"
    echo "초기화 완료!"
    echo "========================================"
else
    echo "취소되었습니다."
fi
