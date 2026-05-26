# `server/config/rbac_config.py` - Role hierarchy + Permissions table

## Mục đích
Định nghĩa **roles** và **permissions** dạng `resource:action` cho toàn hệ thống. 2 roles: `admin` (full) và `teacher` (limited). Permissions tổng hợp ở 2 list: `TEACHER_PERMISSIONS` + `ADMIN_EXTRA_PERMISSIONS`. Admin inherit toàn bộ Teacher perms + extras.

Không có database table cho permissions - đây là **source of truth tĩnh**. Sửa quyền ⇒ sửa file này ⇒ restart.

## Public API

| Symbol | Signature | Vị trí | Mô tả |
|---|---|---|---|
| `ROLE_HIERARCHY` | `Dict[str, int]` | [rbac_config.py:11](../../../server/config/rbac_config.py#L11) | `{admin: 100, teacher: 50}`. Số càng cao quyền càng cao (chưa dùng cho compare, chỉ tham khảo) |
| `VALID_ROLES` | `List[str]` | [rbac_config.py:16](../../../server/config/rbac_config.py#L16) | `["admin", "teacher"]` - dùng để validate role khi tạo user |
| `TEACHER_PERMISSIONS` | `List[str]` | [rbac_config.py:22](../../../server/config/rbac_config.py#L22) | 19 quyền cho teacher |
| `ADMIN_EXTRA_PERMISSIONS` | `List[str]` | [rbac_config.py:56](../../../server/config/rbac_config.py#L56) | 13 quyền chỉ admin |
| `ROLE_PERMISSIONS` | `Dict[str, List[str]]` | [rbac_config.py:83](../../../server/config/rbac_config.py#L83) | `teacher` → `TEACHER_PERMISSIONS`. `admin` → `TEACHER + EXTRA` |
| `ALL_PERMISSIONS` | `List[str]` (sorted) | [rbac_config.py:89](../../../server/config/rbac_config.py#L89) | Union de-dup. Dùng cho UI list quyền |
| `get_all_permissions(role)` | `(str) -> List[str]` | [rbac_config.py:97](../../../server/config/rbac_config.py#L97) | Lookup, fallback `[]` |
| `check_permission(role, permission)` | `(str, str) -> bool` | [rbac_config.py:102](../../../server/config/rbac_config.py#L102) | `permission in get_all_permissions(role)` |
| `can_access_group(user, group)` | `(Dict, Dict) -> bool` | [rbac_config.py:107](../../../server/config/rbac_config.py#L107) | Admin True. Teacher: `user._id ∈ group.teacher_ids` HOẶC `group.created_by == user._id` (legacy) |
| `is_admin(role)` | `(str) -> bool` | [rbac_config.py:124](../../../server/config/rbac_config.py#L124) | `role == "admin"` |

## Permissions table chi tiết

### Teacher permissions (19)

| Permission | Mô tả |
|---|---|
| `profile:read` | Đọc profile bản thân |
| `profile:change_password` | Đổi password |
| `dashboard:read` | Vào dashboard |
| `groups:read` | Xem groups được assign |
| `groups:update` | Sửa metadata group (name, description, layout) |
| `groups:manage_agents` | Move agent giữa groups thuộc về mình |
| `whitelist_profile:create` | Tạo profile whitelist riêng |
| `whitelist_profile:update` | Sửa profile của mình |
| `whitelist_profile:delete` | Xoá profile (chưa active) |
| `whitelist_profile:activate` | Activate profile (deactivate cái khác trong cùng group) |
| `agents:read` | List agents trong groups của mình |
| `agents:detail` | Xem detail 1 agent |
| `whitelist:read` | Đọc whitelist (global + groups của mình) |
| `whitelist:create` | Tạo entry trong groups của mình |
| `whitelist:update` | Sửa entry |
| `whitelist:delete` | Xoá entry |
| `whitelist:sync` | Trigger sync xuống agent |
| `logs:read` | Đọc logs từ agents trong groups của mình |

### Admin-only extras (13)

| Permission | Mô tả |
|---|---|
| `users:create` | Tạo user mới (admin/teacher) |
| `users:read` | List users |
| `users:update` | Sửa user (role, email, is_active) |
| `users:delete` | Xoá user (không xoá last admin) |
| `users:reset_password` | Reset password teacher |
| `agents:delete` | Xoá agent |
| `agents:command` | Gửi command tới agent (policy, isolate, ...) |
| `api_keys:read` | List API keys |
| `api_keys:create` | Tạo API key mới |
| `api_keys:revoke` | Revoke key |
| `logs:export` | Export logs (CSV/JSON) |
| `logs:delete` | Xoá logs |
| `system:config` | Sửa config hệ thống |
| `audit:read` | Xem audit logs |

## Ai gọi module này
- `server/middleware/rbac.py` - `check_permission`, `is_admin` cho decorators
- `server/services/rbac_service.py` - wrap thành OO API
- `server/services/admin_auth_service.py` - `get_all_permissions(role)` cho login response (UI dùng để show/hide menu)
- `server/services/user_service.py` - `VALID_ROLES` validate khi tạo user
- `server/scripts/seed_rbac.py` - list permissions khi seed admin
- Tests - assert permission logic

## Module này gọi ra
Không. Pure data + helpers - stdlib only.

## Đã có sẵn - đừng viết lại
- Cần check user có quyền X không? → `check_permission(role, "resource:action")`
- Cần list quyền của role? → `get_all_permissions(role)`
- Cần check admin? → `is_admin(role)` - **đừng** `role == "admin"` rải rác
- Cần check teacher access group? → `can_access_group(user, group)` (helper đầy đủ, đã handle legacy `created_by`)
- Cần validate role khi tạo user? → `role in VALID_ROLES`

## Gotchas
- **Permission là tĩnh** - không có DB. Thêm permission mới ⇒ thêm vào list ⇒ deploy. Không có UI quản lý permissions.
- **`ROLE_HIERARCHY` không được dùng để compare** trong code hiện tại. Chỉ là gợi ý nếu sau này muốn thêm `manager` role giữa admin và teacher.
- **`can_access_group` ở config (rbac_config.py:107)** TRÙNG logic với `RBACService.can_access_group` (rbac_service.py:60). Cả 2 cùng implement - service version có thể call config version, nhưng hiện duplicate. Sửa logic phải đồng bộ cả 2.
- **Legacy `created_by` fallback** (rbac_config.py:121): tương thích DB cũ chưa migrate sang `teacher_ids` list. Nếu chắc chắn migrate xong → có thể xoá fallback.
- **`teacher_ids` là `List[ObjectId]`** trong DB - `can_access_group` so sánh `str(tid)`. Đừng pass list `str` thẳng vào `$in` query - phải dùng ObjectId. Xem [models.md](models.md) GroupModel.
- **Permission naming `resource:action`** - convention. Nếu thêm permission mới, giữ convention (vd `reports:export`). Không có enforce code-level.
- **`admin` inherit Teacher perms** (line 85) - danh sách admin phải chứa toàn bộ teacher perms. Nếu xoá perm khỏi Teacher mà quên cập nhật Admin, admin sẽ mất quyền đó. Hiện list được tự inherit bằng `+`, an toàn.
- **Không có super-admin** - admin là cao nhất. Lockout last-admin được handle ở `UserService.toggle_active` và `UserService.delete_user`.
