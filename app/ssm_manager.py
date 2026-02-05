import subprocess
import json
import os
import socket
import threading
import time
import psutil

CONFIG_FILE = 'config.json'


# --- 1. 데이터 관리 (JSON 저장소) ---
def load_config():
    """설정 파일을 읽어서 딕셔너리로 반환"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_config(data):
    """딕셔너리를 설정 파일에 저장"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)


# --- 2. 포트 브릿지 (localhost <-> 0.0.0.0 중계) ---
# SSM은 보안상 127.0.0.1(내부)에만 포트를 엽니다.
# 외부(내 PC IP)에서 접속하려면 파이썬이 0.0.0.0에서 받아서 127.0.0.1로 토스해줘야 합니다.
def start_bridge(local_bind_port, internal_ssm_port):
    """
    외부(0.0.0.0:local_bind_port) <===> 내부(127.0.0.1:internal_ssm_port)
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # 0.0.0.0으로 바인딩하여 외부 접속 허용
        server.bind(('0.0.0.0', int(local_bind_port)))
        server.listen(5)

        while True:
            client, addr = server.accept()
            # 내부 SSM 포트로 연결 시도
            ssm_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                ssm_sock.connect(('127.0.0.1', int(internal_ssm_port)))

                # 양방향 데이터 전달 (스레드)
                threading.Thread(target=_forward, args=(client, ssm_sock), daemon=True).start()
                threading.Thread(target=_forward, args=(ssm_sock, client), daemon=True).start()
            except:
                client.close()
    except Exception as e:
        print(f"[Bridge Error] {e}")


def _forward(src, dst):
    """데이터 토스 함수"""
    try:
        while True:
            data = src.recv(4096)
            if not data: break
            dst.send(data)
    except:
        pass
    finally:
        src.close()
        dst.close()


# --- 3. SSM 프로세스 제어 (핵심 기능) ---
def start_session(name, instance_id, bind_port, target_port=22):
    """SSM 세션을 시작하고 브릿지를 연결"""
    config = load_config()
    bind_port = str(bind_port)

    # 이미 사용 중인 포트인지 확인
    if bind_port in config:
        return False, "Port already in use"

    # 1. SSM 명령어 실행 (백그라운드)
    # 실제 SSM은 충돌 방지를 위해 (입력포트 + 10000)번 포트에 엽니다.
    internal_port = int(bind_port) + 10000

    # AWS CLI 명령어 생성
    cmd = [
        "aws", "ssm", "start-session",
        "--target", instance_id,
        "--document-name", "AWS-StartPortForwardingSession",
        "--parameters", f'portNumber=["{target_port}"],localPortNumber=["{internal_port}"]'
    ]

    # AWS SSM 프로세스 시작 (로그는 버림)
    ssm_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # SSM이 켜질 때까지 2초 대기
    time.sleep(2)

    # 2. 브릿지 스레드 시작 (0.0.0.0 -> 127.0.0.1)
    bridge_thread = threading.Thread(target=start_bridge, args=(bind_port, internal_port), daemon=True)
    bridge_thread.start()

    # 3. 설정 저장
    config[bind_port] = {
        "name": name,
        "instance_id": instance_id,
        "target_port": target_port,
        "internal_port": internal_port,
        "pid": ssm_proc.pid,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_config(config)
    return True, "Started"


def stop_session(bind_port):
    """SSM 세션 종료 및 프로세스 킬"""
    config = load_config()
    bind_port = str(bind_port)

    if bind_port in config:
        pid = config[bind_port].get("pid")

        # 프로세스 죽이기 (SSM CLI 종료)
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except:
            pass  # 이미 죽었으면 패스

        del config[bind_port]
        save_config(config)
        return True
    return False