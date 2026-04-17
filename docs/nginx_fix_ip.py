#!/usr/bin/env python3
# -*- coding: utf-8 -*-

with open('/app/tengine/conf/nginx.conf', 'r') as f:
    content = f.read()

# 1. 确保 geo 块有 120.196.51.13
if '120.196.51.13' not in content.split('geo $http_x_forwarded_for $access_ip')[1].split('}')[0]:
    content = content.replace(
        'geo $http_x_forwarded_for $access_ip {\n        default 0;\n        210.5.155.115 1;',
        'geo $http_x_forwarded_for $access_ip {\n        default 0;\n        210.5.155.115 1;\n        120.196.51.13 1;'
    )

# 2. 替换 sftlogapi 的 location 配置
old_config = '''        location /sftlogapi-v2/ {
            # IP 白名单 - 只允许办公室公网出口
            allow 120.196.51.13;
            deny all;
            
            alias /app/tengine/frontend/;
            index index.html;
            try_files $uri $uri/ /sftlogapi-v2/index.html;
        }
        location /sftlogapi-v2/api/ {
            # IP 白名单 - 只允许办公室公网出口
            allow 120.196.51.13;
            deny all;
            
            proxy_pass http://192.168.109.77:5001/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 120s;
            proxy_send_timeout 120s;
            proxy_read_timeout 120s;
            client_max_body_size 100m;
        }
        location = /sftlogapi-v2/api/health {
            # IP 白名单 - 只允许办公室公网出口
            allow 120.196.51.13;
            deny all;
            
            proxy_pass http://192.168.109.77:5001/api/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            access_log off;
        }'''

new_config = '''        location /sftlogapi-v2/ {
            # IP 白名单 - 只允许办公室公网出口
            if ($access_ip = '0') {
                return 403;
            }
            
            alias /app/tengine/frontend/;
            index index.html;
            try_files $uri $uri/ /sftlogapi-v2/index.html;
        }
        location /sftlogapi-v2/api/ {
            # IP 白名单 - 只允许办公室公网出口
            if ($access_ip = '0') {
                return 403;
            }
            
            proxy_pass http://192.168.109.77:5001/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 120s;
            proxy_send_timeout 120s;
            proxy_read_timeout 120s;
            client_max_body_size 100m;
        }
        location = /sftlogapi-v2/api/health {
            # IP 白名单 - 只允许办公室公网出口
            if ($access_ip = '0') {
                return 403;
            }
            
            proxy_pass http://192.168.109.77:5001/api/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            access_log off;
        }'''

if old_config in content:
    content = content.replace(old_config, new_config)
    print("✅ 替换成功")
else:
    print("⚠️  未找到匹配的配置，可能是格式问题")

with open('/app/tengine/conf/nginx.conf', 'w') as f:
    f.write(content)

EOF
cat /root/sft/sftlogapi-v2/docs/nginx_fix_ip.py | sshpass -p 'sftuser' ssh -p 2224 sftuser@localhost "python3"