# `server/scripts` - Maintenance scripts

## Mục đích
Standalone scripts chạy thủ công cho setup/migration. Ngoài `seed_rbac.py`, repo có migration scripts cho whitelist/profile cleanup và `2026_migrate_group_whitelist_to_entries.py` để copy `groups.whitelist[]` sang `whitelist_entries`.

App bootstrap (`app.py`) cũng tự gọi `user_service.ensure_default_admin()` lần đầu chạy - script này dùng khi cần force tạo với username/password tuỳ chỉnh, hoặc CI/CD bootstrap database fresh.

## Public API

### `server/scripts/seed_rbac.py`

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `seed_rbac(admin_username="admin", admin_password="admin123456")` | `(str, str) -> None` | [seed_rbac.py:38](../../../server/scripts/seed_rbac.py#L38) | Connect Mongo → init `UserService` → list permissions config (info) → seed admin if none |
| `__main__` | argparse | [seed_rbac.py:85](../../../server/scripts/seed_rbac.py#L85) | CLI: `--username` `--password` |

## Cách dùng

```bash
cd server
python scripts/seed_rbac.py                                 # default admin/admin123456
python scripts/seed_rbac.py --username myadmin --password mypassword123
```

Whitelist entries migration:

```powershell
.venv\Scripts\python.exe server\scripts\migrations\2026_migrate_group_whitelist_to_entries.py
.venv\Scripts\python.exe server\scripts\migrations\2026_migrate_group_whitelist_to_entries.py --json --fail-on-invalid
.venv\Scripts\python.exe server\scripts\migrations\2026_migrate_group_whitelist_to_entries.py --write
```

Default là dry-run. `--json` in stats cho CI/runbook, `--fail-on-invalid`
thoát code 2 nếu có embedded row không migrate được. Xem
[whitelist_entries.md](whitelist_entries.md) và
[runbook cutover](../../runbooks/whitelist-firewall-cutover.md) trước khi chạy
`--write`.

Output (tham khảo):
```
SAINT RBAC Seeder
--- Step 1: Role Configuration ---
  Role: admin      | 32 permissions
  Role: teacher    | 19 permissions
--- Step 2: Seeding default admin user ---
  Admin created successfully!
  Total users in system: 1
    - admin           | role=admin    | active=Yes
```

## Ai gọi module này
- Người vận hành chạy thủ công lần đầu deploy
- Có thể tích hợp vào Dockerfile entrypoint hoặc CI step

## Module này gọi ra
- `database.config.get_config, get_database` - Mongo connection
- `models.user_model.UserModel, models.audit_model.AuditModel`
- `services.audit_service.AuditService, services.user_service.UserService.ensure_default_admin`
- `config.rbac_config.ROLE_PERMISSIONS, VALID_ROLES` - list để show info
- `dotenv` - load `.env`

## Đã có sẵn - đừng viết lại
- Cần tạo admin user mới? → script này, hoặc qua API `/api/admin/users` (cần có admin sẵn để auth)
- Cần migrate dữ liệu? → chưa có script - tạo file mới `scripts/migrate_*.py` theo pattern `seed_rbac.py` (sys.path + dotenv + connect + work)

## Gotchas
- **`sys.path.insert(0, ...)`** (line 19) chèn parent dir để `from models.X` work. PHẢI chạy từ `server/` hoặc absolute path. Nếu chạy từ root repo, import sẽ fail.
- **`load_dotenv()` không pass path** (line 22): tìm `.env` ở cwd. Cần chạy từ `server/` (cùng cấp với `.env`). Khác với `database/config.py` chỉ định path tuyệt đối.
- **`ensure_default_admin` idempotent**: nếu đã có admin nào trong DB, script log "already exists" và không tạo. Phải `db.users.deleteOne({username:"admin"})` thủ công nếu muốn re-seed.
- **Default password `admin123456`** weak - đổi ngay sau login. Script log warning cảnh báo.
- **Roles không lưu DB** - script chỉ tạo user. Permissions ở `config/rbac_config.py`. Nếu muốn seed thêm test data (groups, agents), tạo script riêng.
- **Không có tear-down script** - drop DB phải thủ công: `mongosh ... db.dropDatabase()`.
- **`pragma: no cover`** không có - không skip khi pytest --cov.
