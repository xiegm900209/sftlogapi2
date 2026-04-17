#!/usr/bin/env python3
with open('/app/tengine/conf/nginx.conf', 'r') as f:
    content = f.read()

old = '''        location /sftlogapi-v2/ {
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

new = '''        location /sftlogapi-v2/ {
            if ($access_ip = '0') {
                return 403;
            }
            
            alias /app/tengine/frontend/;
            index index.html;
            try_files $uri $uri/ /sftlogapi-v2/index.html;
        }
        location /sftlogapi-v2/api/ {
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
            if ($access_ip = '0') {
                return 403;
            }
            
            proxy_pass http://192.168.109.77:5001/api/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            access_log off;
        }'''

if old in content:
    content = content.replace(old, new)
    print("OK")
else:
    print("NOT FOUND")

with open('/app/tengine/conf/nginx.conf', 'w') as f:
    f.write(content)
