#complete_api_server.py
"""
flask_api_server 코드 
post,get api
"""

from flask import Flask, request, jsonify
import json
import os
import subprocess
from datetime import datetime

app = Flask(__name__)

# 설정
RESULTS_DIR = "/var/www/uploads/pod_results"
COMMANDS_FILE = "/home/ubuntu/pod-checker-api/commands.json"
DJANGO_PROJECT_DIR = "/var/www/security_dashboard/mysite"
PYTHON_PATH = "/var/www/security_dashboard/mysite/venv/bin/python3"

# ==================== 헬스 체크 ====================
@app.route('/health', methods=['GET'])
def health():
    """헬스 체크 (Django용)"""
    return jsonify({"status": "ok", "message": "API server is running"}), 200

@app.route('/api/health', methods=['GET'])
def api_health():
    """헬스 체크 (/api 접두사)"""
    return jsonify({"status": "ok"}), 200

# ==================== 점검 시작 ====================
@app.route('/start_check', methods=['POST'])
def start_check():
    """점검 시작 (Django용)"""
    try:
        # Content-Type 체크를 유연하게
        if request.is_json:
            data = request.json
        elif request.form:
            data = request.form.to_dict()
        else:
            data = {}
        
        command_id = f"cmd-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        command = {
            "id": command_id,
            "computer_id": data.get('computer_id', 'default'),
            "namespace": data.get('namespace', 'default'),
            "ai_model": data.get('ai_model', 2),
            "script": data.get('script', 'pre_linux_modify_v3.0.sh'),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        # commands.json 파일 처리
        commands = []
        if os.path.exists(COMMANDS_FILE):
            try:
                with open(COMMANDS_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        commands = json.loads(content)
            except json.JSONDecodeError:
                commands = []
        
        commands.append(command)
        
        with open(COMMANDS_FILE, 'w') as f:
            json.dump(commands, f, indent=2)
        
        print(f"[명령 생성] {command_id}")
        print(f"[대기 중인 명령] {len(commands)}개")
        
        return jsonify({
            "success": True,
            "command_id": command_id,
            "message": "점검 명령이 생성되었습니다"
        }), 200
        
    except Exception as e:
        print(f"[에러] {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/start_check', methods=['POST'])
def api_start_check():
    """점검 시작 (/api 접두사)"""
    try:
        try:
            data = request.json or {}
        except:
            data = {}
        
        command_id = f"cmd-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        command = {
            "id": command_id,
            "computer_id": data.get('computer_id', 'default'),
            "namespace": data.get('namespace', 'default'),
            "ai_model": data.get('ai_model', 2),
            "script": data.get('script', 'pre_linux_modify_v3.0.sh'),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        commands = []
        if os.path.exists(COMMANDS_FILE):
            try:
                with open(COMMANDS_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        commands = json.loads(content)
                    else:
                        commands = []
            except json.JSONDecodeError as e:
                print(f"[경고] commands.json 파싱 실패: {e}")
                commands = []
        
        commands.append(command)
        
        with open(COMMANDS_FILE, 'w') as f:
            json.dump(commands, f, indent=2)
        
        print(f"[명령 생성] {command_id}")
        print(f"[현재 대기 중인 명령] {len(commands)}개")
        
        return jsonify({
            "success": True,
            "command_id": command_id,
            "message": "점검 명령이 생성되었습니다"
        }), 200
        
    except Exception as e:
        print(f"[에러 발생] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== 나머지 엔드포인트 ====================
@app.route('/api/get_command', methods=['GET'])
def get_command():
    """명령 조회"""
    try:
        computer_id = request.args.get('computer_id')
        
        if not os.path.exists(COMMANDS_FILE):
            return jsonify({"has_command": False}), 200
        
        with open(COMMANDS_FILE, 'r') as f:
            commands = json.load(f)
        
        for i, cmd in enumerate(commands):
            if cmd.get('status') == 'pending':
                commands[i]['status'] = 'running'
                
                with open(COMMANDS_FILE, 'w') as f:
                    json.dump(commands, f, indent=2)
                
                print(f"[명령 전달] {cmd['id']}")
                
                return jsonify({"has_command": True, "command": cmd}), 200
        
        return jsonify({"has_command": False}), 200
        
    except Exception as e:
        print(f"[에러] {e}")
        return jsonify({"has_command": False}), 200

@app.route('/api/update_progress', methods=['POST'])
def update_progress():
    """진행률 업데이트"""
    data = request.json
    print(f"[진행률] {data.get('command_id')}: {data.get('progress')}%")
    return jsonify({"success": True}), 200

@app.route('/api/complete_check', methods=['POST'])
def complete_check():
    """점검 완료 처리"""
    try:
        data = request.json
        
        command_id = data.get('command_id')
        success = data.get('success')
        message = data.get('message')
        result_files = data.get('result_files', [])
        results_data = data.get('results_data', [])
        
        print(f"[완료 처리] command_id: {command_id}, success: {success}")
        print(f"[완료 처리] 데이터 개수: {len(results_data)}")
        
        saved_files = []
        
        if results_data:
            print(f"[저장 경로] {RESULTS_DIR}")
            
            for item in results_data:
                filename = item.get('filename')
                content = item.get('content')
                
                if filename and content:
                    basename = os.path.basename(filename)
                    filepath = os.path.join(RESULTS_DIR, basename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)
                    
                    print(f"[저장 완료] {filepath}")
                    saved_files.append(filepath)
        
        if saved_files:
            print(f"\n[DB 임포트 시작] {len(saved_files)}개 파일")
            
            try:
                result = subprocess.run(
                    [
                        PYTHON_PATH,
                        'manage.py',
                        'import_security_data',
                        RESULTS_DIR,
                    ],
                    cwd=DJANGO_PROJECT_DIR,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    print(f"[DB 임포트 성공]")
                    print(f"[출력]\n{result.stdout}")
                    
                    return jsonify({
                        "success": True,
                        "message": "점검 완료 및 DB 임포트 성공",
                        "saved_files": len(saved_files),
                        "import_result": result.stdout
                    }), 200
                else:
                    print(f"[DB 임포트 실패]")
                    print(f"[에러]\n{result.stderr}")
                    
                    return jsonify({
                        "success": True,
                        "message": "파일 저장 성공, DB 임포트 실패",
                        "saved_files": len(saved_files),
                        "import_error": result.stderr
                    }), 200
                    
            except subprocess.TimeoutExpired:
                print(f"[DB 임포트 타임아웃]")
                return jsonify({
                    "success": True,
                    "message": "파일 저장 성공, DB 임포트 타임아웃",
                    "saved_files": len(saved_files)
                }), 200
                
            except Exception as e:
                print(f"[DB 임포트 오류] {e}")
                import traceback
                traceback.print_exc()
                
                return jsonify({
                    "success": True,
                    "message": f"파일 저장 성공, DB 임포트 오류: {str(e)}",
                    "saved_files": len(saved_files)
                }), 200
        
        return jsonify({
            "success": True,
            "message": "점검 완료 처리됨 (저장된 파일 없음)",
            "saved_files": 0
        }), 200
        
    except Exception as e:
        print(f"[에러] {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    print("=" * 50)
    print(f"API 서버 시작 - 포트: 5001")
    print(f"결과 저장 경로: {RESULTS_DIR}")
    print(f"Django 프로젝트: {DJANGO_PROJECT_DIR}")
    print(f"Python 경로: {PYTHON_PATH}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5001, debug=Tru
