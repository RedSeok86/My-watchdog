from typing import List, Dict, Any

SERVERS: List[Dict[str, Any]] = [
    {
        "name": "aimie-dev-server-a-01",
        "ip": "10.15.100.127",
        "tcp_ports": [80, 443],
        "http_urls": ["http://10.15.100.127/health"],
        "ssm": {
            "instance_id": "i-044b2091610cfab62",
            "checks": [
                # 서비스 상태
                {"type": "systemd_active", "service": "apache2"},
                {"type": "systemd_active", "service": "uvicorn"},
                {"type": "systemd_active", "service": "mariadb"},
                {"type": "systemd_active", "service": "postgresql"},

                # 변조 탐지(기록/비교)
                {"type": "command_text", "name": "users(uid>=1000)",
                 "cmd": "getent passwd | awk -F: '$3>=1000{print $1\":\"$3\":\"$6\":\"$7}' | sort"},
                {"type": "command_text", "name": "home_dirs",
                 "cmd": "ls -la /home | sed -n '1,200p'"},
                {"type": "command_text", "name": "authorized_keys_hash",
                 "cmd": "for f in /home/*/.ssh/authorized_keys; do [ -f \"$f\" ] && echo \"$f $(sha256sum \"$f\" | awk '{print $1}')\"; done | sort"},
                {"type": "command_hash", "name": "systemd_unit_files_hash",
                 "cmd": "find /etc/systemd/system -maxdepth 2 -type f -name '*.service' -printf '%p %s %TY-%Tm-%Td %TH:%TM\\n' 2>/dev/null | sort"},
                {"type": "command_text", "name": "enabled_services",
                 "cmd": "systemctl list-unit-files --type=service --state=enabled | sed -n '1,200p'"},
                {"type": "command_hash", "name": "cron_hash",
                 "cmd": "(ls -la /etc/cron.d /etc/crontab /etc/cron.* 2>/dev/null; for u in ubuntu aimie-dev; do echo \"--- crontab:$u ---\"; crontab -u $u -l 2>/dev/null; done) | sed 's/[[:space:]]\\+/ /g'"},
                {"type": "command_text", "name": "listening_ports",
                 "cmd": "ss -lntp | sed -n '1,200p'"},
                {"type": "command_text", "name": "ps_top",
                 "cmd": "ps aux --sort=-%cpu | sed -n '1,30p'"},
            ],
        },
    },
    {
        "name": "aimie-dev-api-server-a-02",
        "ip": "10.15.103.161",
        "tcp_ports": [80, 443],
        "http_urls": [],
        "ssm": {
            "instance_id": "i-0362114ea472782e0",
            "checks": [
                {"type": "systemd_active", "service": "apache2"},

                {"type": "command_text", "name": "users(uid>=1000)",
                 "cmd": "getent passwd | awk -F: '$3>=1000{print $1\":\"$3\":\"$6\":\"$7}' | sort"},
                {"type": "command_text", "name": "home_dirs",
                 "cmd": "ls -la /home | sed -n '1,200p'"},
                {"type": "command_text", "name": "authorized_keys_hash",
                 "cmd": "for f in /home/*/.ssh/authorized_keys; do [ -f \"$f\" ] && echo \"$f $(sha256sum \"$f\" | awk '{print $1}')\"; done | sort"},
                {"type": "command_hash", "name": "systemd_unit_files_hash",
                 "cmd": "find /etc/systemd/system -maxdepth 2 -type f -name '*.service' -printf '%p %s %TY-%Tm-%Td %TH:%TM\\n' 2>/dev/null | sort"},
                {"type": "command_text", "name": "enabled_services",
                 "cmd": "systemctl list-unit-files --type=service --state=enabled | sed -n '1,200p'"},
                {"type": "command_hash", "name": "cron_hash",
                 "cmd": "(ls -la /etc/cron.d /etc/crontab /etc/cron.* 2>/dev/null; for u in ubuntu aimie-dev; do echo \"--- crontab:$u ---\"; crontab -u $u -l 2>/dev/null; done) | sed 's/[[:space:]]\\+/ /g'"},
                {"type": "command_text", "name": "listening_ports",
                 "cmd": "ss -lntp | sed -n '1,200p'"},
                {"type": "command_text", "name": "ps_top",
                 "cmd": "ps aux --sort=-%cpu | sed -n '1,30p'"},
            ],
        },
    },
    {
        "name": "aimie-pregnant-dev-server-a-01",
        "ip": "10.15.103.80",
        "tcp_ports": [80, 443],
        "http_urls": [],
        "ssm": {
            "instance_id": "i-09a9a432c13bf5d47",
            "checks": [
                {"type": "systemd_active", "service": "apache2"},
                {"type": "systemd_active", "service": "uvicorn"},
                {"type": "systemd_active", "service": "postgresql"},

                {"type": "command_text", "name": "users(uid>=1000)",
                 "cmd": "getent passwd | awk -F: '$3>=1000{print $1\":\"$3\":\"$6\":\"$7}' | sort"},
                {"type": "command_text", "name": "home_dirs",
                 "cmd": "ls -la /home | sed -n '1,200p'"},
                {"type": "command_text", "name": "authorized_keys_hash",
                 "cmd": "for f in /home/*/.ssh/authorized_keys; do [ -f \"$f\" ] && echo \"$f $(sha256sum \"$f\" | awk '{print $1}')\"; done | sort"},
                {"type": "command_hash", "name": "systemd_unit_files_hash",
                 "cmd": "find /etc/systemd/system -maxdepth 2 -type f -name '*.service' -printf '%p %s %TY-%Tm-%Td %TH:%TM\\n' 2>/dev/null | sort"},
                {"type": "command_text", "name": "enabled_services",
                 "cmd": "systemctl list-unit-files --type=service --state=enabled | sed -n '1,200p'"},
                {"type": "command_hash", "name": "cron_hash",
                 "cmd": "(ls -la /etc/cron.d /etc/crontab /etc/cron.* 2>/dev/null; for u in ubuntu aimie-dev; do echo \"--- crontab:$u ---\"; crontab -u $u -l 2>/dev/null; done) | sed 's/[[:space:]]\\+/ /g'"},
                {"type": "command_text", "name": "listening_ports",
                 "cmd": "ss -lntp | sed -n '1,200p'"},
                {"type": "command_text", "name": "ps_top",
                 "cmd": "ps aux --sort=-%cpu | sed -n '1,30p'"},
            ],
        },
    },
]


def get_servers() -> List[Dict[str, Any]]:
    return SERVERS
