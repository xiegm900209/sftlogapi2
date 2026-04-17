#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nginx 配置补丁脚本 - 为 sftlogapi-v2 添加 IP 白名单
"""

import re

# 读取原文件
with open('/app/tengine/conf/nginx.conf', 'r') as f:
    content = f.read()

# 定义新的 location 配置
sftlogapi_config = '''        location /sftlogapi-v2/ {
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

# 使用正则替换
old_pattern = r'        location /sftlogapi-v2/ \{[^}]+\}[^}]*?location /sftlogapi-v2/api/ \{[^}]+\}[^}]*?location = /sftlogapi-v2/api/health \{[^}]+\}'

content = re.sub(old_pattern, sftlogapi_config, content, flags=re.DOTALL)

# 写回文件
with open('/app/tengine/conf/nginx.conf', 'w') as f:
    f.write(content)

print("✅ Nginx 配置已更新")
