# Kế Hoạch Triển Khai 2 Tuần — Self-Hosted Ubuntu Server

> **Vai trò:** Security Architect
> **Mục tiêu:** Chuyển từ Render.io sang self-hosted Ubuntu Server trên VMware, kết nối Cloudflare, triển khai Docker, tự tạo TLS/SSL, xây dựng Admin Panel & RBAC
> **Ngày bắt đầu:** 2026-03-09

---

## Tổng Quan Kiến Trúc

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────────────┐
│   Client     │─────▶│  Cloudflare  │─────▶│   Ubuntu Server (VM)    │
│  (Browser)   │◀─────│  (CDN + DNS) │◀─────│   ┌───────────────────┐ │
└─────────────┘      └──────────────┘      │   │  Docker Engine     │ │
                          │                │   │  ┌──────────────┐  │ │
                     TLS Termination       │   │  │  Nginx Proxy │  │ │
                     DDoS Protection       │   │  │  (+ mTLS)    │  │ │
                     WAF Rules             │   │  └──────┬───────┘  │ │
                                           │   │         │          │ │
                                           │   │  ┌──────┴───────┐  │ │
                                           │   │  │  App Server  │  │ │
                                           │   │  │  (API + RBAC)│  │ │
                                           │   │  └──────┬───────┘  │ │
                                           │   │         │          │ │
                                           │   │  ┌──────┴───────┐  │ │
                                           │   │  │  Database    │  │ │
                                           │   │  │  (PostgreSQL)│  │ │
                                           │   │  └──────────────┘  │ │
                                           │   └───────────────────┘ │
                                           └─────────────────────────┘
```

---

# TUẦN 1: HẠ TẦNG & DOCKER

---

## Ngày 1–2: Cài Đặt VMware & Ubuntu Server

### Bước 1: Chuẩn bị VMware

1. Tải VMware Workstation Pro (hoặc ESXi nếu dùng server vật lý) từ trang chủ VMware.
2. Tạo máy ảo mới với thông số tối thiểu:

| Tài nguyên | Tối thiểu | Khuyến nghị |
|---|---|---|
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4–8 GB |
| Disk | 40 GB | 80–120 GB (SSD) |
| Network | NAT hoặc Bridged | **Bridged** (để có IP riêng trong LAN) |

3. Tải ISO Ubuntu Server 24.04 LTS từ [ubuntu.com/download/server](https://ubuntu.com/download/server).

### Bước 2: Cài đặt Ubuntu Server

```bash
# Trong quá trình cài đặt:
# - Chọn "Ubuntu Server (minimized)" để giảm attack surface
# - Bật OpenSSH Server khi được hỏi
# - KHÔNG cài đặt snap packages không cần thiết
# - Tạo user admin (KHÔNG dùng root trực tiếp)
```

### Bước 3: Hardening cơ bản sau cài đặt

```bash
# 1. Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# 2. Tạo user deploy riêng (không dùng user admin cho app)
sudo adduser deploy
sudo usermod -aG sudo deploy

# 3. Cấu hình SSH an toàn
sudo nano /etc/ssh/sshd_config
```

Thay đổi các dòng sau trong `sshd_config`:

```
Port 2222                          # Đổi port mặc định
PermitRootLogin no                 # Cấm root login
PasswordAuthentication no          # Chỉ dùng SSH key
MaxAuthTries 3                     # Giới hạn số lần thử
AllowUsers deploy                  # Chỉ cho phép user deploy
ClientAliveInterval 300
ClientAliveCountMax 2
```

```bash
# 4. Tạo SSH key trên máy local
ssh-keygen -t ed25519 -C "deploy@server"

# 5. Copy public key lên server
ssh-copy-id -p 2222 deploy@<server-ip>

# 6. Restart SSH
sudo systemctl restart sshd

# 7. Cài đặt và cấu hình UFW Firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 2222/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw enable
sudo ufw status verbose

# 8. Cài đặt Fail2Ban chống brute-force
sudo apt install fail2ban -y
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo nano /etc/fail2ban/jail.local
```

Cấu hình Fail2Ban (`jail.local`):

```ini
[sshd]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
```

```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 9. Cài đặt auto security updates
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

**Checkpoint ngày 2:** SSH vào server thành công bằng key, firewall hoạt động, Fail2Ban đang chạy.

---

## Ngày 3: Cài Đặt Docker & Docker Compose

### Bước 1: Cài Docker Engine

```bash
# Gỡ các phiên bản cũ (nếu có)
sudo apt remove docker docker-engine docker.io containerd runc 2>/dev/null

# Cài đặt dependencies
sudo apt install ca-certificates curl gnupg -y

# Thêm Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Thêm Docker repository
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Cài đặt Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin -y

# Thêm user deploy vào group docker
sudo usermod -aG docker deploy

# Verify
docker --version
docker compose version
```

### Bước 2: Hardening Docker

```bash
# Tạo file cấu hình Docker daemon
sudo nano /etc/docker/daemon.json
```

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "no-new-privileges": true,
  "userns-remap": "default",
  "live-restore": true,
  "userland-proxy": false
}
```

```bash
sudo systemctl restart docker
```

**Checkpoint ngày 3:** `docker run hello-world` chạy thành công.

---

## Ngày 4: Tạo Dockerfile & Docker Compose

### Bước 1: Cấu trúc thư mục dự án

```
/home/deploy/app/
├── docker-compose.yml
├── .env                        # Biến môi trường (KHÔNG commit vào git)
├── nginx/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── conf.d/
│       └── default.conf
├── app/
│   ├── Dockerfile
│   ├── package.json            # (hoặc requirements.txt nếu Python)
│   └── src/
└── certs/                      # TLS certificates
    ├── origin-cert.pem
    └── origin-key.pem
```

### Bước 2: Dockerfile cho ứng dụng (ví dụ Node.js)

```dockerfile
# app/Dockerfile
# === Build stage ===
FROM node:20-alpine AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci --only=production
COPY src/ ./src/

# === Production stage ===
FROM node:20-alpine AS production

# Security: chạy app dưới user non-root
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app
COPY --from=builder --chown=appuser:appgroup /build ./

# Security: read-only filesystem ngoại trừ /tmp
USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "src/server.js"]
```

### Bước 3: Nginx Reverse Proxy Dockerfile

```dockerfile
# nginx/Dockerfile
FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/

EXPOSE 80 443
```

### Bước 4: nginx.conf (bảo mật)

```nginx
# nginx/nginx.conf
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # === Security Headers ===
    server_tokens off;                              # Ẩn version nginx

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    # === Rate Limiting ===
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    # === Logging ===
    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent"';
    access_log /var/log/nginx/access.log main;

    sendfile on;
    keepalive_timeout 65;

    include /etc/nginx/conf.d/*.conf;
}
```

### Bước 5: nginx/conf.d/default.conf

```nginx
# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    # === TLS với Cloudflare Origin Certificate ===
    ssl_certificate     /etc/nginx/certs/origin-cert.pem;
    ssl_certificate_key /etc/nginx/certs/origin-key.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # === Chỉ chấp nhận request từ Cloudflare ===
    # (Cập nhật IP ranges từ https://www.cloudflare.com/ips/)
    # set_real_ip_from 173.245.48.0/20;
    # set_real_ip_from 103.21.244.0/22;
    # ... (thêm tất cả IP ranges của Cloudflare)
    # real_ip_header CF-Connecting-IP;

    # === Proxy tới App Container ===
    location / {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://app:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Rate limit riêng cho login
    location /api/auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://app:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Chặn truy cập file ẩn
    location ~ /\. {
        deny all;
    }
}
```

### Bước 6: docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  nginx:
    build: ./nginx
    container_name: nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./certs:/etc/nginx/certs:ro        # Mount certificates (read-only)
      - nginx-logs:/var/log/nginx
    depends_on:
      app:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - frontend

  app:
    build: ./app
    container_name: app-server
    env_file: .env
    expose:
      - "3000"                              # Chỉ expose nội bộ, KHÔNG ra ngoài
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    read_only: true                         # Filesystem read-only
    tmpfs:
      - /tmp                                # Chỉ /tmp được ghi
    security_opt:
      - no-new-privileges:true
    networks:
      - frontend
      - backend
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  db:
    image: postgres:16-alpine
    container_name: postgres-db
    env_file: .env
    volumes:
      - pgdata:/var/lib/postgresql/data
    expose:
      - "5432"
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
    driver: local
  nginx-logs:
    driver: local

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true                          # Database network KHÔNG có internet
```

### Bước 7: File .env

```bash
# .env — KHÔNG BAO GIỜ commit file này vào Git
NODE_ENV=production
PORT=3000

# Database
POSTGRES_USER=appuser
POSTGRES_PASSWORD=<SINH_RANDOM_PASSWORD_MẠNH>
POSTGRES_DB=appdb
DATABASE_URL=postgresql://appuser:<PASSWORD>@db:5432/appdb

# JWT Secret (dùng cho Auth/RBAC)
JWT_SECRET=<SINH_RANDOM_SECRET_256bit>
JWT_EXPIRES_IN=15m
JWT_REFRESH_EXPIRES_IN=7d
```

```bash
# Sinh random password mạnh
openssl rand -base64 32
```

**Checkpoint ngày 4:** `docker compose up -d` chạy thành công, app trả về response ở localhost:3000.

---

## Ngày 5: Tạo TLS/SSL Certificate & Cấu Hình Cloudflare

### Bước 1: Đăng ký tên miền trên Cloudflare

1. Đăng nhập [dash.cloudflare.com](https://dash.cloudflare.com).
2. Thêm tên miền → Chọn plan Free.
3. Cloudflare sẽ cung cấp 2 nameserver, ví dụ:
   - `ada.ns.cloudflare.com`
   - `bob.ns.cloudflare.com`
4. Đăng nhập vào nhà cung cấp tên miền (ví dụ: Namecheap, GoDaddy) → Đổi nameserver sang Cloudflare.
5. Chờ DNS propagation (thường 5–30 phút, tối đa 24 giờ).

### Bước 2: Tạo Cloudflare Origin Certificate (15 năm)

Đây là certificate giữa Cloudflare ↔ Server của bạn (không phải Let's Encrypt):

1. Vào Cloudflare Dashboard → **SSL/TLS** → **Origin Server**.
2. Click **Create Certificate**.
3. Chọn:
   - **Key type:** RSA (2048) hoặc ECDSA
   - **Hostnames:** `yourdomain.com`, `*.yourdomain.com`
   - **Validity:** 15 years
4. Cloudflare sẽ hiển thị **Origin Certificate** và **Private Key**.
5. **QUAN TRỌNG:** Copy cả hai ngay lập tức. Private key chỉ hiển thị một lần.

```bash
# Trên server, lưu certificate
mkdir -p /home/deploy/app/certs
nano /home/deploy/app/certs/origin-cert.pem
# Dán nội dung Origin Certificate vào

nano /home/deploy/app/certs/origin-key.pem
# Dán nội dung Private Key vào

# Bảo vệ private key
chmod 600 /home/deploy/app/certs/origin-key.pem
chmod 644 /home/deploy/app/certs/origin-cert.pem
```

### Bước 3: Cấu hình DNS trên Cloudflare

Tạo các DNS record:

| Type | Name | Content | Proxy Status |
|---|---|---|---|
| A | `@` | `<IP-Server-Của-Bạn>` | Proxied (cam) |
| A | `www` | `<IP-Server-Của-Bạn>` | Proxied (cam) |
| A | `api` | `<IP-Server-Của-Bạn>` | Proxied (cam) |

**LƯU Ý:** Nếu server ở nhà (behind NAT), bạn cần:
- Mở port 80 và 443 trên router (port forwarding).
- Hoặc dùng **Cloudflare Tunnel** (xem Bước 4).

### Bước 4: (Khuyến nghị) Dùng Cloudflare Tunnel thay vì mở port

Cloudflare Tunnel an toàn hơn vì KHÔNG cần mở port nào trên firewall:

```bash
# Cài đặt cloudflared trên server
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/cloudflared jammy main' | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt update && sudo apt install cloudflared -y

# Đăng nhập và tạo tunnel
cloudflared tunnel login
cloudflared tunnel create my-app-tunnel

# Cấu hình tunnel
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

```yaml
# ~/.cloudflared/config.yml
tunnel: <TUNNEL_ID>
credentials-file: /home/deploy/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: yourdomain.com
    service: https://localhost:443
    originRequest:
      noTLSVerify: false
      originServerName: yourdomain.com
  - hostname: api.yourdomain.com
    service: https://localhost:443
  - service: http_status:404
```

```bash
# Tạo DNS record tự động
cloudflared tunnel route dns my-app-tunnel yourdomain.com

# Chạy tunnel như service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Bước 5: Cấu hình SSL trên Cloudflare Dashboard

1. **SSL/TLS** → **Overview** → Chọn **Full (strict)**.
   - "Full (strict)" yêu cầu certificate hợp lệ trên server → đã có Origin Cert.
2. **SSL/TLS** → **Edge Certificates:**
   - Bật **Always Use HTTPS**: ON
   - Bật **Automatic HTTPS Rewrites**: ON
   - **Minimum TLS Version:** TLS 1.2
   - Bật **TLS 1.3**: ON
3. **Security** → **WAF:**
   - Bật Managed Rules (có sẵn trong plan Free).
   - Tạo custom rule chặn các quốc gia không cần thiết (tuỳ chọn).
4. **Security** → **Bots:**
   - Bật **Bot Fight Mode**: ON

**Checkpoint ngày 5:** Truy cập `https://yourdomain.com` thấy ổ khoá xanh, certificate hợp lệ.

---

## Ngày 6–7: Testing Hạ Tầng & Backup

### Ngày 6: Kiểm tra bảo mật cơ bản

```bash
# 1. Kiểm tra SSL/TLS
# Truy cập: https://www.ssllabs.com/ssltest/
# Nhập domain → Mục tiêu: đạt điểm A hoặc A+

# 2. Kiểm tra security headers
# Truy cập: https://securityheaders.com
# Nhập domain → Mục tiêu: đạt điểm A

# 3. Kiểm tra ports mở (từ bên ngoài)
nmap -sT yourdomain.com
# Chỉ nên thấy 80 và 443 (nếu dùng Tunnel thì không thấy port nào)

# 4. Test rate limiting
# Cài apache2-utils
sudo apt install apache2-utils -y
ab -n 100 -c 10 https://yourdomain.com/
# Phải thấy nhiều response trả về 429 (Too Many Requests)

# 5. Kiểm tra Docker containers
docker compose ps                    # Tất cả phải UP + healthy
docker compose logs --tail=50        # Không có error bất thường
```

### Ngày 7: Thiết lập Backup & Monitoring

```bash
# === Database Backup Script ===
mkdir -p /home/deploy/backups

nano /home/deploy/scripts/backup-db.sh
```

```bash
#!/bin/bash
# backup-db.sh
BACKUP_DIR="/home/deploy/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"

# Backup PostgreSQL
docker exec postgres-db pg_dump -U appuser appdb | gzip > "$BACKUP_FILE"

# Giữ lại 7 bản backup gần nhất
ls -tp ${BACKUP_DIR}/db_backup_*.sql.gz | tail -n +8 | xargs -I {} rm -- {}

echo "[$(date)] Backup completed: $BACKUP_FILE"
```

```bash
chmod +x /home/deploy/scripts/backup-db.sh

# Cron job: backup mỗi ngày lúc 2 giờ sáng
crontab -e
# Thêm dòng:
0 2 * * * /home/deploy/scripts/backup-db.sh >> /home/deploy/logs/backup.log 2>&1
```

```bash
# === Monitoring cơ bản với Docker logs ===
# Xem logs real-time
docker compose logs -f

# Kiểm tra disk usage
df -h
docker system df
```

**Checkpoint cuối tuần 1:** Hệ thống chạy ổn định 24h, backup hoạt động, SSL score A+.

---

# TUẦN 2: ADMIN PANEL & RBAC

---

## Ngày 8–9: Thiết Kế & Code RBAC System

### Bước 1: Thiết kế Database Schema cho RBAC

```sql
-- migrations/001_rbac_schema.sql

-- Bảng Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Bảng Roles
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,       -- 'super_admin', 'admin', 'moderator', 'user'
    description TEXT,
    is_system BOOLEAN DEFAULT false,        -- Role hệ thống không thể xoá
    created_at TIMESTAMP DEFAULT NOW()
);

-- Bảng Permissions
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource VARCHAR(100) NOT NULL,         -- 'users', 'posts', 'settings'
    action VARCHAR(50) NOT NULL,            -- 'create', 'read', 'update', 'delete'
    description TEXT,
    UNIQUE(resource, action)
);

-- Bảng liên kết Role ↔ Permission (Many-to-Many)
CREATE TABLE role_permissions (
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Bảng liên kết User ↔ Role (Many-to-Many)
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES users(id),
    assigned_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- Bảng Audit Log (ghi lại mọi thao tác quan trọng)
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,           -- 'LOGIN', 'CREATE_USER', 'ASSIGN_ROLE', etc.
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Bảng Refresh Tokens
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP
);

-- Indexes cho performance
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_users_email ON users(email);

-- Seed data: Default roles
INSERT INTO roles (name, description, is_system) VALUES
    ('super_admin', 'Full system access, cannot be deleted', true),
    ('admin', 'Administrative access', true),
    ('moderator', 'Content moderation access', false),
    ('user', 'Standard user access', true);

-- Seed data: Default permissions
INSERT INTO permissions (resource, action) VALUES
    ('users', 'create'), ('users', 'read'), ('users', 'update'), ('users', 'delete'),
    ('roles', 'create'), ('roles', 'read'), ('roles', 'update'), ('roles', 'delete'),
    ('roles', 'assign'),
    ('posts', 'create'), ('posts', 'read'), ('posts', 'update'), ('posts', 'delete'),
    ('settings', 'read'), ('settings', 'update'),
    ('audit_logs', 'read');
```

### Bước 2: Authentication Middleware (Node.js/Express ví dụ)

```javascript
// src/middleware/auth.js
const jwt = require('jsonwebtoken');
const { pool } = require('../config/database');

/**
 * Middleware xác thực JWT token
 */
const authenticate = async (req, res, next) => {
    try {
        const authHeader = req.headers.authorization;
        if (!authHeader?.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Access token required' });
        }

        const token = authHeader.split(' ')[1];
        const decoded = jwt.verify(token, process.env.JWT_SECRET);

        // Kiểm tra user còn active không
        const result = await pool.query(
            'SELECT id, email, full_name, is_active FROM users WHERE id = $1',
            [decoded.userId]
        );

        if (!result.rows[0] || !result.rows[0].is_active) {
            return res.status(401).json({ error: 'User not found or deactivated' });
        }

        req.user = result.rows[0];
        next();
    } catch (error) {
        if (error.name === 'TokenExpiredError') {
            return res.status(401).json({ error: 'Token expired', code: 'TOKEN_EXPIRED' });
        }
        return res.status(401).json({ error: 'Invalid token' });
    }
};

/**
 * Middleware kiểm tra permission
 * Sử dụng: authorize('users', 'create')
 */
const authorize = (resource, action) => {
    return async (req, res, next) => {
        try {
            const query = `
                SELECT COUNT(*) as count
                FROM user_roles ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = $1
                  AND p.resource = $2
                  AND p.action = $3
            `;

            const result = await pool.query(query, [req.user.id, resource, action]);

            if (parseInt(result.rows[0].count) === 0) {
                // Ghi audit log cho unauthorized access attempt
                await logAudit(req, 'UNAUTHORIZED_ACCESS', resource, null, {
                    attempted_action: action,
                });
                return res.status(403).json({
                    error: 'Insufficient permissions',
                    required: `${resource}:${action}`,
                });
            }

            next();
        } catch (error) {
            next(error);
        }
    };
};

/**
 * Ghi audit log
 */
const logAudit = async (req, action, resourceType, resourceId, details) => {
    try {
        await pool.query(
            `INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
             VALUES ($1, $2, $3, $4, $5, $6, $7)`,
            [
                req.user?.id || null,
                action,
                resourceType,
                resourceId,
                JSON.stringify(details),
                req.ip || req.headers['cf-connecting-ip'],
                req.headers['user-agent'],
            ]
        );
    } catch (err) {
        console.error('Audit log failed:', err);
    }
};

module.exports = { authenticate, authorize, logAudit };
```

### Bước 3: Auth Routes (Login, Register, Token Refresh)

```javascript
// src/routes/auth.js
const express = require('express');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { pool } = require('../config/database');
const { logAudit } = require('../middleware/auth');

const router = express.Router();
const SALT_ROUNDS = 12;
const MAX_LOGIN_ATTEMPTS = 5;
const LOCK_DURATION_MINUTES = 15;

/**
 * POST /api/auth/register
 */
router.post('/register', async (req, res) => {
    try {
        const { email, password, fullName } = req.body;

        // Validation
        if (!email || !password || !fullName) {
            return res.status(400).json({ error: 'All fields are required' });
        }
        if (password.length < 12) {
            return res.status(400).json({ error: 'Password must be at least 12 characters' });
        }
        // Kiểm tra password complexity
        const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/;
        if (!passwordRegex.test(password)) {
            return res.status(400).json({
                error: 'Password must contain uppercase, lowercase, number, and special character',
            });
        }

        // Hash password
        const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);

        // Tạo user
        const result = await pool.query(
            `INSERT INTO users (email, password_hash, full_name)
             VALUES ($1, $2, $3) RETURNING id, email, full_name`,
            [email.toLowerCase().trim(), passwordHash, fullName.trim()]
        );

        // Gán default role 'user'
        await pool.query(
            `INSERT INTO user_roles (user_id, role_id)
             SELECT $1, id FROM roles WHERE name = 'user'`,
            [result.rows[0].id]
        );

        res.status(201).json({
            message: 'Registration successful',
            user: result.rows[0],
        });
    } catch (error) {
        if (error.code === '23505') {
            return res.status(409).json({ error: 'Email already registered' });
        }
        res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * POST /api/auth/login
 */
router.post('/login', async (req, res) => {
    try {
        const { email, password } = req.body;

        // Tìm user
        const result = await pool.query(
            'SELECT * FROM users WHERE email = $1',
            [email.toLowerCase().trim()]
        );
        const user = result.rows[0];

        if (!user) {
            // Trả về message giống nhau để tránh user enumeration
            return res.status(401).json({ error: 'Invalid email or password' });
        }

        // Kiểm tra account lock
        if (user.locked_until && new Date(user.locked_until) > new Date()) {
            return res.status(423).json({
                error: 'Account temporarily locked. Try again later.',
            });
        }

        // Kiểm tra password
        const isValid = await bcrypt.compare(password, user.password_hash);
        if (!isValid) {
            // Tăng failed attempts
            const newAttempts = user.failed_login_attempts + 1;
            const lockUntil =
                newAttempts >= MAX_LOGIN_ATTEMPTS
                    ? new Date(Date.now() + LOCK_DURATION_MINUTES * 60 * 1000)
                    : null;

            await pool.query(
                'UPDATE users SET failed_login_attempts = $1, locked_until = $2 WHERE id = $3',
                [newAttempts, lockUntil, user.id]
            );

            return res.status(401).json({ error: 'Invalid email or password' });
        }

        if (!user.is_active) {
            return res.status(403).json({ error: 'Account is deactivated' });
        }

        // Reset failed attempts & update last login
        await pool.query(
            'UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login_at = NOW() WHERE id = $1',
            [user.id]
        );

        // Lấy roles & permissions
        const rolesResult = await pool.query(
            `SELECT r.name FROM roles r
             JOIN user_roles ur ON r.id = ur.role_id
             WHERE ur.user_id = $1`,
            [user.id]
        );
        const roles = rolesResult.rows.map((r) => r.name);

        // Tạo access token (ngắn hạn)
        const accessToken = jwt.sign(
            { userId: user.id, roles },
            process.env.JWT_SECRET,
            { expiresIn: process.env.JWT_EXPIRES_IN || '15m' }
        );

        // Tạo refresh token (dài hạn)
        const refreshToken = crypto.randomBytes(64).toString('hex');
        const refreshTokenHash = crypto
            .createHash('sha256')
            .update(refreshToken)
            .digest('hex');

        await pool.query(
            `INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
             VALUES ($1, $2, NOW() + INTERVAL '7 days')`,
            [user.id, refreshTokenHash]
        );

        // Audit log
        await logAudit(req, 'LOGIN_SUCCESS', 'users', user.id, { roles });

        // Set refresh token trong httpOnly cookie
        res.cookie('refreshToken', refreshToken, {
            httpOnly: true,
            secure: true,
            sameSite: 'strict',
            maxAge: 7 * 24 * 60 * 60 * 1000, // 7 ngày
            path: '/api/auth/refresh',
        });

        res.json({
            accessToken,
            user: {
                id: user.id,
                email: user.email,
                fullName: user.full_name,
                roles,
            },
        });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * POST /api/auth/refresh
 */
router.post('/refresh', async (req, res) => {
    try {
        const refreshToken = req.cookies.refreshToken;
        if (!refreshToken) {
            return res.status(401).json({ error: 'Refresh token required' });
        }

        const tokenHash = crypto
            .createHash('sha256')
            .update(refreshToken)
            .digest('hex');

        const result = await pool.query(
            `SELECT rt.*, u.id as uid, u.email, u.is_active
             FROM refresh_tokens rt
             JOIN users u ON rt.user_id = u.id
             WHERE rt.token_hash = $1
               AND rt.expires_at > NOW()
               AND rt.revoked_at IS NULL`,
            [tokenHash]
        );

        if (!result.rows[0] || !result.rows[0].is_active) {
            return res.status(401).json({ error: 'Invalid refresh token' });
        }

        // Revoke token cũ (rotation)
        await pool.query(
            'UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = $1',
            [tokenHash]
        );

        // Tạo token mới
        const rolesResult = await pool.query(
            `SELECT r.name FROM roles r
             JOIN user_roles ur ON r.id = ur.role_id
             WHERE ur.user_id = $1`,
            [result.rows[0].uid]
        );
        const roles = rolesResult.rows.map((r) => r.name);

        const newAccessToken = jwt.sign(
            { userId: result.rows[0].uid, roles },
            process.env.JWT_SECRET,
            { expiresIn: process.env.JWT_EXPIRES_IN || '15m' }
        );

        const newRefreshToken = crypto.randomBytes(64).toString('hex');
        const newTokenHash = crypto
            .createHash('sha256')
            .update(newRefreshToken)
            .digest('hex');

        await pool.query(
            `INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
             VALUES ($1, $2, NOW() + INTERVAL '7 days')`,
            [result.rows[0].uid, newTokenHash]
        );

        res.cookie('refreshToken', newRefreshToken, {
            httpOnly: true,
            secure: true,
            sameSite: 'strict',
            maxAge: 7 * 24 * 60 * 60 * 1000,
            path: '/api/auth/refresh',
        });

        res.json({ accessToken: newAccessToken });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * POST /api/auth/logout
 */
router.post('/logout', async (req, res) => {
    try {
        const refreshToken = req.cookies.refreshToken;
        if (refreshToken) {
            const tokenHash = crypto
                .createHash('sha256')
                .update(refreshToken)
                .digest('hex');
            await pool.query(
                'UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = $1',
                [tokenHash]
            );
        }

        res.clearCookie('refreshToken', { path: '/api/auth/refresh' });
        res.json({ message: 'Logged out successfully' });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = router;
```

**Checkpoint ngày 9:** API auth hoạt động — register, login, refresh token, logout.

---

## Ngày 10–11: Code Admin Panel API

### Bước 1: Admin Routes — User Management

```javascript
// src/routes/admin/users.js
const express = require('express');
const bcrypt = require('bcrypt');
const { pool } = require('../../config/database');
const { authenticate, authorize, logAudit } = require('../../middleware/auth');

const router = express.Router();

// Tất cả routes trong file này yêu cầu authentication
router.use(authenticate);

/**
 * GET /api/admin/users — Danh sách users (phân trang)
 */
router.get('/', authorize('users', 'read'), async (req, res) => {
    try {
        const page = Math.max(1, parseInt(req.query.page) || 1);
        const limit = Math.min(100, Math.max(1, parseInt(req.query.limit) || 20));
        const offset = (page - 1) * limit;
        const search = req.query.search || '';

        let query = `
            SELECT u.id, u.email, u.full_name, u.is_active, u.email_verified,
                   u.last_login_at, u.created_at,
                   COALESCE(array_agg(r.name) FILTER (WHERE r.name IS NOT NULL), '{}') as roles
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
        `;
        const params = [];

        if (search) {
            query += ` WHERE (u.email ILIKE $1 OR u.full_name ILIKE $1)`;
            params.push(`%${search}%`);
        }

        query += ` GROUP BY u.id ORDER BY u.created_at DESC LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
        params.push(limit, offset);

        const [usersResult, countResult] = await Promise.all([
            pool.query(query, params),
            pool.query(
                `SELECT COUNT(*) FROM users${search ? ' WHERE email ILIKE $1 OR full_name ILIKE $1' : ''}`,
                search ? [`%${search}%`] : []
            ),
        ]);

        res.json({
            users: usersResult.rows,
            pagination: {
                page,
                limit,
                total: parseInt(countResult.rows[0].count),
                totalPages: Math.ceil(countResult.rows[0].count / limit),
            },
        });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * PATCH /api/admin/users/:id/roles — Gán/huỷ role cho user
 */
router.patch('/:id/roles', authorize('roles', 'assign'), async (req, res) => {
    try {
        const { id } = req.params;
        const { roles } = req.body; // Array of role names

        // Không cho phép tự thay đổi role của chính mình
        if (id === req.user.id) {
            return res.status(403).json({ error: 'Cannot modify your own roles' });
        }

        // Kiểm tra super_admin protection
        const targetRoles = await pool.query(
            `SELECT r.name FROM roles r JOIN user_roles ur ON r.id = ur.role_id WHERE ur.user_id = $1`,
            [id]
        );
        const isSuperAdmin = targetRoles.rows.some((r) => r.name === 'super_admin');

        // Chỉ super_admin mới có thể sửa super_admin khác
        const requesterRoles = await pool.query(
            `SELECT r.name FROM roles r JOIN user_roles ur ON r.id = ur.role_id WHERE ur.user_id = $1`,
            [req.user.id]
        );
        const requesterIsSuperAdmin = requesterRoles.rows.some((r) => r.name === 'super_admin');

        if (isSuperAdmin && !requesterIsSuperAdmin) {
            return res.status(403).json({ error: 'Only super_admin can modify super_admin roles' });
        }

        // Transaction: xoá roles cũ, thêm roles mới
        const client = await pool.connect();
        try {
            await client.query('BEGIN');
            await client.query('DELETE FROM user_roles WHERE user_id = $1', [id]);

            for (const roleName of roles) {
                await client.query(
                    `INSERT INTO user_roles (user_id, role_id, assigned_by)
                     SELECT $1, id, $2 FROM roles WHERE name = $3`,
                    [id, req.user.id, roleName]
                );
            }
            await client.query('COMMIT');
        } catch (err) {
            await client.query('ROLLBACK');
            throw err;
        } finally {
            client.release();
        }

        await logAudit(req, 'ASSIGN_ROLES', 'users', id, {
            new_roles: roles,
            assigned_by: req.user.id,
        });

        res.json({ message: 'Roles updated successfully' });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * PATCH /api/admin/users/:id/status — Activate/Deactivate user
 */
router.patch('/:id/status', authorize('users', 'update'), async (req, res) => {
    try {
        const { id } = req.params;
        const { isActive } = req.body;

        if (id === req.user.id) {
            return res.status(403).json({ error: 'Cannot deactivate yourself' });
        }

        await pool.query('UPDATE users SET is_active = $1, updated_at = NOW() WHERE id = $2', [
            isActive,
            id,
        ]);

        // Nếu deactivate, revoke tất cả refresh tokens
        if (!isActive) {
            await pool.query(
                'UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = $1 AND revoked_at IS NULL',
                [id]
            );
        }

        await logAudit(req, isActive ? 'ACTIVATE_USER' : 'DEACTIVATE_USER', 'users', id, {});

        res.json({ message: `User ${isActive ? 'activated' : 'deactivated'} successfully` });
    } catch (error) {
        res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * GET /api/admin/audit-logs — Xem audit logs
 */
router.get(
    '/audit-logs',
    authorize('audit_logs', 'read'),
    async (req, res) => {
        try {
            const page = Math.max(1, parseInt(req.query.page) || 1);
            const limit = Math.min(100, parseInt(req.query.limit) || 50);
            const offset = (page - 1) * limit;

            const result = await pool.query(
                `SELECT al.*, u.email as user_email
                 FROM audit_logs al
                 LEFT JOIN users u ON al.user_id = u.id
                 ORDER BY al.created_at DESC
                 LIMIT $1 OFFSET $2`,
                [limit, offset]
            );

            res.json({ logs: result.rows });
        } catch (error) {
            res.status(500).json({ error: 'Internal server error' });
        }
    }
);

module.exports = router;
```

### Bước 2: Kết nối Routes trong Server chính

```javascript
// src/server.js
const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const rateLimit = require('express-rate-limit');

const authRoutes = require('./routes/auth');
const adminUserRoutes = require('./routes/admin/users');

const app = express();

// === Security Middleware ===
app.use(helmet());
app.use(cors({
    origin: process.env.ALLOWED_ORIGINS?.split(',') || 'https://yourdomain.com',
    credentials: true,
}));
app.use(cookieParser());
app.use(express.json({ limit: '10kb' }));      // Giới hạn body size

// Global rate limit
app.use(rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 100,
    standardHeaders: true,
    legacyHeaders: false,
}));

// === Health Check (không cần auth) ===
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// === Routes ===
app.use('/api/auth', authRoutes);
app.use('/api/admin/users', adminUserRoutes);

// === Error Handler ===
app.use((err, req, res, next) => {
    console.error(err.stack);
    // KHÔNG trả về stack trace trong production
    res.status(500).json({ error: 'Internal server error' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on port ${PORT}`);
});
```

**Checkpoint ngày 11:** Admin API hoạt động — list users, assign roles, activate/deactivate, audit logs.

---

## Ngày 12: Deployment Pipeline & CI/CD Cơ Bản

```bash
# === Script deploy trên server ===
nano /home/deploy/scripts/deploy.sh
```

```bash
#!/bin/bash
# deploy.sh — Zero-downtime deployment
set -e

APP_DIR="/home/deploy/app"
cd "$APP_DIR"

echo "[$(date)] Starting deployment..."

# 1. Pull latest code
git pull origin main

# 2. Build Docker images mới
docker compose build --no-cache

# 3. Chạy database migrations
docker compose run --rm app node src/migrations/run.js

# 4. Rolling restart
docker compose up -d --remove-orphans

# 5. Chờ health check
echo "Waiting for health check..."
sleep 10
if curl -sf http://localhost:3000/health > /dev/null; then
    echo "[$(date)] Deployment successful!"
else
    echo "[$(date)] DEPLOYMENT FAILED — Rolling back..."
    docker compose down
    git checkout HEAD~1
    docker compose up -d
    exit 1
fi

# 6. Dọn dẹp Docker images cũ
docker image prune -f
```

```bash
chmod +x /home/deploy/scripts/deploy.sh
```

---

## Ngày 13: Security Testing & Penetration Test Cơ Bản

### Checklist kiểm tra bảo mật

```bash
# 1. Kiểm tra SQL Injection
# Test thủ công hoặc dùng sqlmap (chỉ test trên server của mình!)
# Parameterized queries đã được dùng → nên an toàn

# 2. Kiểm tra XSS (Cross-Site Scripting)
# Thử inject <script>alert(1)</script> vào input fields
# CSP header đã được set → nên bị chặn

# 3. Kiểm tra CSRF
# Verify SameSite cookie + CORS origin check

# 4. Kiểm tra Auth bypass
# - Thử truy cập admin routes không có token
# - Thử dùng expired token
# - Thử dùng token của user role thường vào admin route

# 5. Kiểm tra Rate Limiting
for i in {1..20}; do
    curl -s -o /dev/null -w "%{http_code}\n" https://yourdomain.com/api/auth/login \
        -X POST -H "Content-Type: application/json" \
        -d '{"email":"test@test.com","password":"wrong"}'
done
# Phải thấy 429 sau vài request

# 6. Kiểm tra password brute-force protection
# Sau 5 lần sai → account bị lock 15 phút

# 7. Docker security scan
docker scout cves app-server

# 8. Kiểm tra không có secrets trong Docker image
docker history app-server --no-trunc
```

---

## Ngày 14: Documentation & Go-Live

### Checklist cuối cùng trước Go-Live

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Ubuntu Server cập nhật + hardened | ☐ |
| 2 | SSH chỉ dùng key, port đã đổi | ☐ |
| 3 | UFW firewall chỉ mở port cần thiết | ☐ |
| 4 | Fail2Ban đang chạy | ☐ |
| 5 | Docker containers chạy non-root | ☐ |
| 6 | Database network isolated (internal) | ☐ |
| 7 | Cloudflare SSL = Full (strict) | ☐ |
| 8 | Origin Certificate đã cài | ☐ |
| 9 | Security headers score A+ | ☐ |
| 10 | Rate limiting hoạt động | ☐ |
| 11 | RBAC permissions hoạt động đúng | ☐ |
| 12 | Audit logs ghi đầy đủ | ☐ |
| 13 | Backup database tự động | ☐ |
| 14 | Deploy script hoạt động | ☐ |
| 15 | Password policy enforcement | ☐ |
| 16 | JWT refresh token rotation | ☐ |
| 17 | Account lockout sau failed attempts | ☐ |
| 18 | .env không trong Git | ☐ |
| 19 | Docker images đã scan vulnerabilities | ☐ |
| 20 | Cloudflare WAF + Bot Protection ON | ☐ |

### Lưu ý bảo trì sau Go-Live

Sau khi triển khai xong, cần duy trì các hoạt động định kỳ: cập nhật security patches hàng tuần (`sudo apt update && sudo apt upgrade`), rebuild Docker images hàng tháng để lấy base image mới nhất, kiểm tra và rotate credentials mỗi 90 ngày, review audit logs hàng tuần, test backup restore hàng tháng, và chạy lại security scan mỗi khi có thay đổi lớn.

---

> **Tài liệu này được soạn với vai trò Security Architect. Mọi quyết định kiến trúc đều ưu tiên nguyên tắc Defense in Depth — bảo mật nhiều lớp, không phụ thuộc vào một điểm bảo vệ duy nhất.**
