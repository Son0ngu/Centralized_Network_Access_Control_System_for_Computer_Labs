# SAINT RBAC - Teacher Data Filtering Design Document

## 1. Bối cảnh vấn đề

Hiện tại hệ thống có 4 controller "cũ" phục vụ data cho cả Agent API (machine-to-machine) lẫn Admin/Teacher web UI:

| Controller | Endpoint prefix | Ai gọi hiện tại |
|---|---|---|
| `GroupController` | `/api/groups` | Agent (không auth) + Web UI |
| `AgentController` | `/api/agents` | Agent (API Key/JWT) + Web UI |
| `WhitelistController` | `/api/whitelist` | Agent (JWT) + Web UI |
| `LogController` | `/api/logs` | Agent (JWT) + Web UI |

**Vấn đề**: Khi Teacher đăng nhập web UI và vào `/groups`, `/agents`, `/whitelist`, `/logs`, frontend gọi đúng các API trên và nhận về **toàn bộ data** - không phân biệt group nào do Teacher tạo hay không. Theo thiết kế RBAC, Teacher chỉ được thấy data thuộc Group mình tạo (`created_by == user._id`).

---

## 2. Nguyên tắc thiết kế

### 2.1. Zero breaking changes cho Agent API

Agent (phần mềm cài trên máy tính) giao tiếp với server qua API Key hoặc JWT token (header `Authorization: Bearer ...` hoặc `X-API-Key`). Các request từ Agent **không có cookie** và **không có claim `token_for: admin_user`**.

**Quy tắc**: Nếu request không đến từ admin_user → trả data như cũ, không filter gì.

### 2.2. Phân biệt caller bằng cơ chế đã có

Hệ thống đã có sẵn decorator `inject_current_user` trong `middleware/rbac.py`:

```
inject_current_user
├── Có cookie access_token hợp lệ với token_for == "admin_user"?
│   ├── CÓ → g.current_user = user, g.current_role = "admin" | "teacher"
│   └── KHÔNG → g.current_user = None
```

Decorator này **không block request** - chỉ gắn thông tin user vào Flask `g` context nếu có. Đây là chìa khóa để giữ Agent API hoạt động bình thường.

### 2.3. Logic filter đã có sẵn trong RBACService

`services/rbac_service.py` đã implement đầy đủ 3 phương thức filter:

| Method | Trả về cho Admin | Trả về cho Teacher |
|---|---|---|
| `get_group_query_filter(user)` | `None` (không filter) | `{"created_by": user._id}` |
| `get_agent_query_filter(user)` | `None` | `{"group_id": {"$in": [teacher_group_ids]}}` |
| `get_log_query_filter(user)` | `None` | `{"agent_id": {"$in": [agent_ids_in_teacher_groups]}}` |

### 2.4. Tóm tắt flow mới

```
Request đến controller
    │
    ├── inject_current_user chạy trước
    │
    ├── g.current_user == None? (Agent request hoặc không có cookie)
    │   └── Trả data như cũ, KHÔNG filter
    │
    ├── g.current_role == "admin"?
    │   └── Trả data như cũ, KHÔNG filter (admin toàn quyền)
    │
    └── g.current_role == "teacher"?
        └── Apply ownership filter qua RBACService
```

---

## 3. Thay đổi cần thiết

### 3.1. Tổng quan thay đổi theo file

| File | Loại thay đổi | Mức độ |
|---|---|---|
| `middleware/rbac.py` | Không đổi | - |
| `services/rbac_service.py` | Sửa nhỏ: hoàn thiện `get_log_query_filter` | Thấp |
| `controllers/group_controller.py` | Sửa: inject user + filter 4 endpoint | Trung bình |
| `controllers/agent_controller.py` | Sửa: inject user + filter 2 endpoint | Trung bình |
| `controllers/whitelist_controller.py` | Sửa: inject user + filter 3 endpoint | Trung bình |
| `controllers/log_controller.py` | Sửa: inject user + filter 2 endpoint | Trung bình |
| `services/group_service.py` | Sửa: thêm tham số `query_filter` | Thấp |
| `app.py` (`register_controllers`) | Sửa: truyền `rbac_service` vào 4 controller | Thấp |
| Frontend JS (agents.js, groups.js...) | Không đổi | - |

---

## 4. Chi tiết thiết kế từng controller

### 4.1. GroupController - `/api/groups`

**Constructor mới**: Thêm `rbac_service` parameter.

```
GroupController(group_service, rbac_service, socketio=None)
```

**Các endpoint cần sửa**:

#### GET /api/groups - `list_groups()`

Hiện tại: `self.service.list_groups()` → trả tất cả groups.

Thiết kế mới:

```
1. inject_current_user chạy trước (decorator trên method)
2. Nếu g.current_user tồn tại VÀ g.current_role == "teacher":
   - Gọi rbac_service.get_group_query_filter(g.current_user)
   - Truyền filter vào service: self.service.list_groups(query_filter=filter)
3. Nếu không (Agent hoặc Admin):
   - Gọi self.service.list_groups() như cũ
```

**Thay đổi service**: `GroupService.list_groups()` cần nhận tham số `query_filter=None`. Khi `query_filter` không None, model query thêm filter. Cụ thể `GroupModel.list_groups()` hiện gọi `collection.find()` - cần đổi thành `collection.find(query_filter or {})`.

#### POST /api/groups - `create_group()`

Hiện tại: `self.service.create_group(name, description, whitelist)` - không truyền `created_by`.

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu g.current_user tồn tại:
   - Truyền created_by=g.current_user["_id"] vào service
3. Nếu không (Agent tạo group):
   - created_by=None (giữ nguyên behavior cũ)
```

**Thay đổi service**: `GroupService.create_group()` cần nhận thêm `created_by=None` và truyền xuống `GroupModel.create_group()` (đã hỗ trợ sẵn parameter này).

#### GET /api/groups/<group_id> - `get_group()`

Hiện tại: Trả group bất kỳ.

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Lấy group từ service như cũ
3. Nếu g.current_role == "teacher":
   - Kiểm tra rbac_service.can_access_group(g.current_user, group)
   - Nếu False → 403 "Không có quyền trên Group này"
4. Nếu không → trả bình thường
```

#### PATCH /api/groups/<group_id> - `update_group()`

Thiết kế mới: Tương tự `get_group` - kiểm tra ownership trước khi cho update.

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Lấy group, kiểm tra can_access_group()
   - Nếu False → 403
3. Tiếp tục update như cũ
```

#### DELETE /api/groups/<group_id> - `delete_group()`

Thiết kế mới: Tương tự - kiểm tra ownership trước khi cho xóa.

---

### 4.2. AgentController - `/api/agents`

**Constructor mới**: Thêm `rbac_service` parameter.

```
AgentController(agent_model, agent_service, rbac_service, socketio=None)
```

**Nguyên tắc riêng**: Agent endpoints có 2 loại - endpoints cho agent gọi (register, heartbeat) dùng `require_api_key`/`require_jwt`, và endpoints cho web UI gọi (list, get, delete, update). Chỉ sửa nhóm web UI.

#### GET /api/agents - `list_agents()`

Hiện tại: `self.service.get_agents_with_status()` → trả tất cả agents, rồi filter theo `status`, `hostname`, `group_id` trên Python.

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Lấy danh sách agents như cũ
3. Nếu g.current_role == "teacher":
   - Gọi rbac_service.get_agent_query_filter(g.current_user)
     → Trả {"group_id": {"$in": ["id1", "id2", ...]}}
   - Lọc thêm agents: chỉ giữ agent có group_id nằm trong danh sách
4. Tiếp tục apply các filter cũ (status, hostname...) như bình thường
```

**Lưu ý**: Hiện tại `list_agents()` load toàn bộ agents vào memory rồi filter bằng Python (không dùng MongoDB query). Do đó filter ownership cũng thực hiện bằng Python - thêm 1 bước filter vào chuỗi `filtered_agents` hiện có. Không cần sửa service hay model.

#### GET /api/agents/statistics - `get_statistics()`

Hiện tại: Trả thống kê toàn bộ agents.

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Tính statistics CHỈ trên agents thuộc teacher's groups
   - Cách: lấy list agent_ids đã filter, tính lại stats trên list đó
3. Nếu không → trả bình thường
```

**Lưu ý**: Hiện tại `calculate_statistics()` tính trên toàn bộ DB. Để không sửa service, controller sẽ tự tính stats từ `filtered_agents` (đã có logic load agents + tính status). Hoặc đơn giản hơn: trả stats toàn cục cho agent/admin, stats filtered cho teacher.

#### GET /api/agents/<agent_id> - `get_agent()`

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Lấy agent detail như cũ
3. Nếu g.current_role == "teacher":
   - Kiểm tra agent.group_id có thuộc teacher's groups không
   - Nếu không → 403
```

#### DELETE, PATCH endpoints

Teacher không có quyền `agents:delete` (chỉ admin có), nên middleware RBAC sẽ chặn ở tầng permission nếu thêm decorator `@require_permission`. Tuy nhiên hiện tại các endpoint này chưa có auth decorator nào. Cần cân nhắc:

- `delete_agent`: Thêm ownership check - teacher chỉ xóa agent trong group mình (nếu muốn cho phép), hoặc để chỉ admin xóa (theo thiết kế hiện tại).
- `update_display_name`, `update_position`, `update_group`: Teacher có thể quản lý agent trong group mình → cần ownership check.

**Quyết định thiết kế**: Theo RBAC config, teacher có `agents:read` + `agents:detail` nhưng KHÔNG có `agents:delete`, `agents:command`. Vậy:

| Endpoint | Teacher có quyền? | Ownership check? |
|---|---|---|
| `list_agents` | Có (agents:read) | Có - filter by group |
| `get_agent` | Có (agents:detail) | Có - check group |
| `delete_agent` | Không (agents:delete) | Block hoàn toàn |
| `update_display_name` | Không rõ ràng | Block cho teacher |
| `update_position` | Không rõ ràng | Block cho teacher |
| `update_group` (move) | Có (groups:manage_agents) | Có - check cả 2 group |

---

### 4.3. WhitelistController - `/api/whitelist`

**Constructor mới**: Thêm `rbac_service` parameter.

```
WhitelistController(whitelist_model, whitelist_service, rbac_service, socketio=None)
```

**Đặc thù whitelist**: Whitelist có 2 scope - **global** (không thuộc group nào) và **group-level** (gắn với group cụ thể qua `group_id`). Theo thiết kế:
- Admin: thấy tất cả (global + mọi group).
- Teacher: thấy global (read-only) + whitelist của group mình tạo (CRUD).
- Agent: sync whitelist theo group mình thuộc (không đổi - dùng JWT, không cookie).

#### GET /api/whitelist - `list_domains()`

Hiện tại: Nếu có `group_id` param thì trả scoped whitelist, nếu không thì trả tất cả.

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu có group_id param:
   - Nếu g.current_role == "teacher":
     - Kiểm tra group_id thuộc teacher's groups → nếu không → 403
   - Trả scoped whitelist như cũ
3. Nếu không có group_id param (list tất cả):
   - Nếu g.current_role == "teacher":
     - Trả global whitelist + whitelist của teacher's groups
     - Cách: lấy list group_ids → query whitelist WHERE scope == "global" OR group_id IN [...]
   - Nếu không → trả tất cả như cũ
```

#### POST /api/whitelist - `add_domain()`

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Whitelist entry phải gắn với group_id
   - Kiểm tra group_id thuộc teacher's groups
   - Không cho phép thêm vào global scope
3. Nếu không → thêm như cũ
```

#### DELETE /api/whitelist/<domain_id> - `delete_domain()`

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Lấy domain entry từ DB
   - Nếu scope == "global" → 403 (teacher không xóa global)
   - Nếu có group_id → kiểm tra ownership
3. Nếu không → xóa như cũ
```

#### Bulk endpoints (bulk_add, bulk_update, bulk_delete)

Tương tự logic trên - teacher chỉ thao tác trên whitelist entries thuộc group mình.

#### GET /api/whitelist/agent-sync

**Không đổi** - endpoint này dùng `@require_jwt` (JWT của agent, không phải admin token). Agent gọi endpoint này để sync whitelist. Không bị ảnh hưởng.

#### GET /api/whitelist/statistics

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Tính stats CHỈ trên entries thuộc teacher's groups + global
3. Nếu không → trả full stats
```

---

### 4.4. LogController - `/api/logs`

**Constructor mới**: Thêm `rbac_service` parameter.

```
LogController(log_model, log_service, rbac_service, socketio=None)
```

**Đặc thù logs**: Logs được gửi từ agent, mỗi log có `agent_id`. Teacher chỉ thấy logs từ agents thuộc group mình tạo.

#### GET /api/logs - `list_logs()`

Hiện tại: `self.service.get_all_logs(filters, limit, offset)` → trả tất cả.

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Lấy danh sách agent_ids thuộc teacher's groups (qua rbac_service)
   - Thêm filter: {"agent_id": {"$in": [...]}}
   - Merge vào filters hiện tại
3. Truyền filters vào service.get_all_logs()
```

**Thay đổi RBACService**: `get_log_query_filter()` hiện tại có TODO comment - cần hoàn thiện. Logic đúng:

```
get_log_query_filter(user):
    1. Nếu admin → return None
    2. Lấy teacher's group_ids (groups WHERE created_by == user._id)
    3. Lấy agent_ids trong các groups đó (agents WHERE group_id IN group_ids)
    4. Return {"agent_id": {"$in": agent_ids}}
```

Hiện tại bước 3 chưa hoàn thiện - đang return `group_id` filter thay vì `agent_id` filter. Cần sửa để query agents collection lấy đúng agent_ids.

#### GET /api/logs/stats - `get_statistics()`

Thiết kế mới:

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - Tính stats CHỈ trên logs từ agents thuộc teacher's groups
   - Truyền agent filter vào service
3. Nếu không → trả full stats
```

#### POST /api/logs - `receive_logs()`

**Không đổi** - endpoint này dùng `@require_jwt` (JWT của agent). Agent gửi logs qua endpoint này. Không bị ảnh hưởng.

#### DELETE /api/logs - `clear_logs()`

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - CHẶN → 403 (teacher không có quyền logs:delete theo RBAC config)
3. Nếu không → xóa như cũ
```

#### GET /api/logs/export - `export_logs()`

```
1. inject_current_user chạy trước
2. Nếu g.current_role == "teacher":
   - CHẶN → 403 (teacher không có quyền logs:export)
3. Nếu không → export như cũ
```

---

## 5. Chi tiết sửa RBACService

### 5.1. Hoàn thiện `get_log_query_filter()`

Hiện tại method này trả `{"group_id": {"$in": [...]}}` - sai vì logs collection dùng field `agent_id`, không phải `group_id`.

Cần sửa thành:

```
def get_log_query_filter(self, user):
    if admin → return None

    # Bước 1: Lấy group_ids của teacher
    group_ids = [g._id for g in groups WHERE created_by == user._id]

    # Bước 2: Lấy agent_ids trong các groups đó
    agents = agents_collection.find(
        {"group_id": {"$in": group_ids}},  # ObjectId dạng string
        {"agent_id": 1}
    )
    agent_ids = [a["agent_id"] for a in agents]

    # Bước 3: Return filter cho logs collection
    return {"agent_id": {"$in": agent_ids}}
```

**Cần inject thêm `agent_model`** vào `RBACService` constructor:

```
RBACService(group_model, agent_model=None)
```

### 5.2. Thêm helper method `get_teacher_group_ids()`

Để tránh duplicate logic, thêm:

```
def get_teacher_group_ids(self, user):
    """Trả list string group_ids mà teacher tạo."""
    if admin → return None (nghĩa là tất cả)
    groups = group_model.collection.find({"created_by": user._id}, {"_id": 1})
    return [str(g["_id"]) for g in groups]
```

### 5.3. Thêm method `get_whitelist_query_filter()`

Chưa có - cần thêm:

```
def get_whitelist_query_filter(self, user):
    if admin → return None
    group_ids = self.get_teacher_group_ids(user)
    # Teacher thấy: global + entries trong groups mình
    return {"$or": [
        {"scope": "global"},
        {"group_id": {"$in": group_ids}}
    ]}
```

---

## 6. Sửa `app.py` - Wiring

### 6.1. Truyền rbac_service vào 4 controller

Trong `register_controllers()`, thay đổi khởi tạo controller:

```
# Hiện tại:
group_controller = GroupController(group_service)
agent_controller = AgentController(agent_model, agent_service, socketio)
whitelist_controller = WhitelistController(whitelist_model, whitelist_service, socketio)
log_controller = LogController(log_model, log_service, socketio)

# Sau khi sửa:
group_controller = GroupController(group_service, rbac_service, socketio)
agent_controller = AgentController(agent_model, agent_service, rbac_service, socketio)
whitelist_controller = WhitelistController(whitelist_model, whitelist_service, rbac_service, socketio)
log_controller = LogController(log_model, log_service, rbac_service, socketio)
```

### 6.2. Sửa RBACService constructor

```
# Hiện tại:
rbac_service = RBACService(group_model)

# Sau khi sửa:
rbac_service = RBACService(group_model, agent_model)
```

---

## 7. Pattern code chung cho mỗi endpoint

Để giữ code sạch và nhất quán, mỗi controller sẽ có 1 helper method nội bộ:

```python
def _get_ownership_context(self):
    """
    Trả (is_teacher, user) nếu request đến từ teacher.
    Trả (False, None) nếu agent request hoặc admin.
    """
    user = getattr(g, 'current_user', None)
    if user and user.get('role') == 'teacher':
        return True, user
    return False, user
```

Mỗi endpoint sẽ dùng:

```python
@inject_current_user
def list_groups(self):
    is_teacher, user = self._get_ownership_context()
    if is_teacher:
        query_filter = self.rbac_service.get_group_query_filter(user)
    else:
        query_filter = None
    groups = self.service.list_groups(query_filter=query_filter)
    ...
```

---

## 8. Ma trận endpoint đầy đủ

### 8.1. Tổng hợp thay đổi cho tất cả endpoint

| Endpoint | Agent request | Admin request | Teacher request |
|---|---|---|---|
| **GROUPS** | | | |
| `GET /api/groups` | Tất cả (như cũ) | Tất cả | Chỉ groups có created_by == user._id |
| `POST /api/groups` | Tạo bình thường (created_by=None) | Tạo bình thường (created_by=user._id) | Tạo với created_by=user._id |
| `GET /api/groups/<id>` | Như cũ | Như cũ | Kiểm tra ownership → 403 nếu sai |
| `PATCH /api/groups/<id>` | Như cũ | Như cũ | Kiểm tra ownership → 403 nếu sai |
| `DELETE /api/groups/<id>` | Như cũ | Như cũ | Kiểm tra ownership → 403 nếu sai |
| **AGENTS** | | | |
| `POST /api/agents/register` | Require API Key (không đổi) | - | - |
| `POST /api/agents/heartbeat` | Require JWT (không đổi) | - | - |
| `GET /api/agents` | Tất cả (như cũ) | Tất cả | Chỉ agents trong teacher's groups |
| `GET /api/agents/statistics` | Tất cả (như cũ) | Tất cả | Stats chỉ tính trên filtered agents |
| `GET /api/agents/<id>` | Như cũ | Như cũ | Kiểm tra group ownership → 403 |
| `DELETE /api/agents/<id>` | Như cũ | Như cũ | **Block** (không có quyền agents:delete) |
| `PATCH .../display-name` | Như cũ | Như cũ | Block hoặc ownership check |
| `PATCH .../position` | Như cũ | Như cũ | Block hoặc ownership check |
| `PATCH .../group` (move) | Như cũ | Như cũ | Ownership check cả source và target group |
| **WHITELIST** | | | |
| `GET /api/whitelist/agent-sync` | Require JWT (không đổi) | - | - |
| `GET /api/whitelist` | Tất cả (như cũ) | Tất cả | Global (read-only) + teacher's groups |
| `POST /api/whitelist` | Như cũ | Như cũ | Chỉ thêm vào group mình, không thêm global |
| `DELETE /api/whitelist/<id>` | Như cũ | Như cũ | Chỉ xóa entry trong group mình |
| `POST .../bulk` | Như cũ | Như cũ | Chỉ trong group mình |
| `POST .../bulk-update` | Như cũ | Như cũ | Chỉ trong group mình |
| `POST .../bulk-delete` | Như cũ | Như cũ | Chỉ trong group mình |
| `GET .../statistics` | Như cũ | Như cũ | Stats filtered |
| `GET .../export` | Như cũ | Như cũ | Export filtered |
| `POST .../import` | Như cũ | Như cũ | Import chỉ vào group mình |
| **LOGS** | | | |
| `POST /api/logs` | Require JWT (không đổi) | - | - |
| `GET /api/logs` | Tất cả (như cũ) | Tất cả | Chỉ logs từ agents trong teacher's groups |
| `GET /api/logs/stats` | Tất cả (như cũ) | Tất cả | Stats filtered |
| `DELETE /api/logs` | Như cũ | Như cũ | **Block** (không có quyền logs:delete) |
| `GET /api/logs/export` | Như cũ | Như cũ | **Block** (không có quyền logs:export) |

### 8.2. Tóm tắt hành vi theo role

| Hành vi | Admin | Teacher |
|---|---|---|
| Xem groups | Tất cả | Chỉ group mình tạo |
| Tạo group | Có (created_by = admin._id) | Có (created_by = teacher._id) |
| Sửa/Xóa group | Tất cả | Chỉ group mình tạo |
| Xem agents | Tất cả | Chỉ agents trong group mình |
| Xóa agent | Có | Không |
| Di chuyển agent | Có | Chỉ giữa groups mình tạo |
| Xem whitelist | Tất cả | Global (read-only) + group mình |
| Thêm/Sửa/Xóa whitelist | Tất cả | Chỉ trong group mình |
| Xem logs | Tất cả | Chỉ logs từ agents trong group mình |
| Xóa/Export logs | Có | Không |

---

## 9. Thứ tự triển khai (đề xuất)

### Phase 1: Infrastructure (ít rủi ro nhất)

1. Sửa `RBACService`: thêm `agent_model`, hoàn thiện `get_log_query_filter()`, thêm `get_whitelist_query_filter()`, thêm `get_teacher_group_ids()`
2. Sửa `app.py`: truyền `agent_model` vào `RBACService`, truyền `rbac_service` vào 4 controller

### Phase 2: GroupController (nền tảng)

3. Sửa `GroupController` + `GroupService.list_groups()` + `GroupModel.list_groups()`
4. Test: Agent tạo group → vẫn hoạt động, Teacher list groups → chỉ thấy group mình

### Phase 3: AgentController

5. Sửa `AgentController` (list, get, statistics, move)
6. Test: Agent register/heartbeat không ảnh hưởng, Teacher list agents → filtered

### Phase 4: WhitelistController

7. Sửa `WhitelistController` (list, add, delete, bulk, stats)
8. Test: Agent sync không ảnh hưởng, Teacher thao tác whitelist → scoped

### Phase 5: LogController

9. Sửa `LogController` (list, stats, clear, export)
10. Test: Agent gửi logs không ảnh hưởng, Teacher xem logs → filtered

---

## 10. Rủi ro và giải pháp

### 10.1. Agent request bị filter nhầm

**Rủi ro**: Nếu agent request vô tình mang cookie (không thể xảy ra vì agent là phần mềm, không phải browser).

**Giải pháp**: `inject_current_user` kiểm tra `token_for == "admin_user"` - agent JWT không có claim này → `g.current_user` sẽ là `None` → không filter.

### 10.2. Performance khi query teacher's groups

**Rủi ro**: Mỗi request của teacher cần query groups collection để lấy group_ids, rồi query agents collection để lấy agent_ids.

**Giải pháp**:
- Đã có index `created_by` trên groups collection
- Số lượng groups/teacher thường nhỏ (vài chục, không phải hàng ngàn)
- Có thể cache teacher_group_ids trong `g` context trong 1 request cycle
- Nếu cần tối ưu hơn: cache trong session hoặc Redis (tương lai)

### 10.3. Group không có `created_by` (data cũ)

**Rủi ro**: Groups tạo trước khi có RBAC không có field `created_by` → teacher sẽ không thấy.

**Giải pháp**:
- Đây là hành vi **đúng** - groups cũ không thuộc teacher nào
- Admin vẫn thấy tất cả
- Có thể thêm migration script gán `created_by` cho groups cũ nếu cần

### 10.4. Dashboard page

**Lưu ý**: Dashboard (`/`) hiện hiển thị stats tổng hợp (total agents, total groups...). Sau khi apply filter, teacher sẽ thấy stats **chỉ thuộc về mình** - đây là hành vi đúng theo thiết kế.

Frontend dashboard JS cần gọi đúng các API đã filtered - vì cùng endpoint, data trả về sẽ tự động filtered nếu teacher đăng nhập.

---

## 11. Test plan

| Test case | Expected |
|---|---|
| Agent gọi `GET /api/groups` (không cookie) | Trả tất cả groups (như cũ) |
| Admin gọi `GET /api/groups` (cookie admin) | Trả tất cả groups |
| Teacher gọi `GET /api/groups` (cookie teacher) | Chỉ groups có `created_by == teacher._id` |
| Teacher gọi `GET /api/agents` | Chỉ agents trong teacher's groups |
| Teacher gọi `DELETE /api/agents/<id>` | 403 (không có quyền) |
| Teacher gọi `POST /api/whitelist` không có group_id | 400 (phải chỉ định group) |
| Teacher gọi `POST /api/whitelist` với group_id của người khác | 403 |
| Teacher gọi `DELETE /api/logs` | 403 |
| Teacher gọi `GET /api/logs` | Chỉ logs từ agents trong teacher's groups |
| Agent gọi `POST /api/agents/register` | Hoạt động bình thường (không bị filter) |
| Agent gọi `GET /api/whitelist/agent-sync` | Hoạt động bình thường |
