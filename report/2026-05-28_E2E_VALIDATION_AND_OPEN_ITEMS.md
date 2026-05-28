# Cap nhat kiem thu E2E, Firewall va ton dong - 2026-05-28

## Muc dich

File nay cap nhat trang thai moi nhat sau cac dot kiem thu tren Render production va may Windows Administrator. Pham vi gom Server API/RBAC, Agent contract, GUI, Socket.IO, whitelist conflict, Windows Firewall Default Deny va cac loi frontend da phat hien sau khi mo dashboard that.

## Ket qua chinh

| Hang muc | Ket qua | Bang chung |
| --- | --- | --- |
| Full system E2E deep | Chay duoc 21 PASS, phat hien 3 van de can sua/phan loai | `test-results/saint-full-system-e2e/20260527_214919/` |
| Firewall-only packet deep sau patch | PASS sach | `test-results/saint-full-system-e2e/20260527_235108/` |
| Windows Firewall Default Deny | Bật that, ca 3 profile outbound ve `block`, restore ve `allow` | `deep_firewall_packet_matrix.passed=true` |
| Packet allowed/blocked | Allowed `1.1.1.1:443` OK khi Default Deny active; blocked `151.101.1.69:443` fail dung ky vong | `20260527_235108` JSON |
| Self-allow rules | 3 rule HTTPS/DNS UDP/DNS TCP, khong duplicate | `self_allow_idempotent` |
| Managed allow rule add/remove | Rule count `10 -> 11 -> 10` | `managed_rule_add_remove` |
| Cleanup firewall | Snapshot restore OK, residual SAINTE2E rules = 0 | cleanup `CLEANUP_OK=5` |
| Long soak 30 phut | PASS trong full deep run, 28 samples healthy | `20260527_214919` JSON |
| GUI click-by-click | PASS qua Playwright Node: login va dieu huong cac trang chinh | `deep_gui_matrix.passed=true` |
| Socket.IO realtime | PASS: connect, ping/pong, `whitelist_added` event | `deep_websocket_matrix.passed=true` |
| Classroom synthetic scale | PASS voi 24 synthetic agents chia group A/B va RBAC teacher | `deep_classroom_matrix.passed=true` |

## Cac loi da phat hien va da sua local

### 1. `/api-keys` bi loi DOM null

Hien tuong tren production:

```text
api_keys.js:74 Error loading keys: TypeError: Cannot read properties of null (reading 'style')
```

Nguyen nhan: `server/views/static/js/pages/api_keys.js` tim `#keysList` va `#emptyState`, nhung template hien tai chi co `#keysContainer`. Khi co data API key, code goi `emptyState.style.display` va bi crash.

Trang thai local:

- Da sua JS render truc tiep vao `#keysContainer`.
- Da them empty state bang HTML trong container.
- Da bo access DOM bat buoc voi filter/stat elements khi element khong ton tai.
- Da sua filter status tu `expired` thanh `expiring` cho khop logic `getKeyStatus()`.

File lien quan:

- `server/views/static/js/pages/api_keys.js`
- `server/views/templates/api_keys.html`

### 2. `favicon.ico` 404

Hien tuong:

```text
favicon.ico:1 Failed to load resource: the server responded with a status of 404
```

Trang thai local:

- Da them route `/favicon.ico` tra SVG icon nhe.
- Da them `<link rel="icon">` vao base template.

File lien quan:

- `server/routes/pages.py`
- `server/views/templates/base.html`

### 3. Agent policy heartbeat khong force sync

Hien tuong trong full deep run:

```text
Heartbeat did not request force sync for isolate
heartbeat.data.force_sync=false
heartbeat.data.policy_mode=none
```

Nguyen nhan local: `AgentService` co tham so `policy_model` de kiem tra override policy trong heartbeat, nhung container chua inject `agent_policy_model`.

Trang thai local:

- Da sua `initialize_container()` de tao `AgentService(..., policy_model=agent_policy_model)`.
- Can deploy server len Render roi rerun full deep de xac nhan production pass.

File lien quan:

- `server/bootstrap/container.py`

### 4. Firewall remove rule khong xoa ngay rule vua tao

Hien tuong trong firewall-only run truoc patch:

```text
Deep firewall remove rule did not restore managed allow rule count
```

Nguyen nhan: `RulesManager.remove_allow_rule()` dua vao read provider list rules. Trong mot lan chay, read provider tra rong/khong thay rule vua tao, nen khong goi delete rule. Cleanup cuoi van xoa sach theo prefix, nhung test add/remove bi fail.

Trang thai local:

- `RulesManager` luu map IP -> rule name khi tao rule, de remove duoc ngay ca khi read provider khong hydrate kip.
- Sua `NetSecurityFirewallProvider` JSON field `remote_addresses` de khong bi output `{}`.
- Them regression test.

File lien quan:

- `agent/firewall/rules.py`
- `agent/firewall/netsecurity_provider.py`
- `agent/tests/test_firewall_provider_writes.py`

### 5. E2E runner false positive bulk duplicate whitelist

Hien tuong: full deep bao "Bulk duplicate inserted more than one row" trong khi server thuc te insert 1 row va reject duplicate row thu 2.

Nguyen nhan: runner doc whitelist scoped gom nhieu mang response va dem trung cung mot `_id`.

Trang thai local:

- Da de-duplicate ID trong `find_whitelist_ids()`.

File lien quan:

- `tools/saint_full_system_e2e.py`

### 6. Hotfix bao mat: group/log API public sau deploy Render

Hien tuong tren production truoc hotfix:

```text
/api/groups tra 200 khi chua dang nhap va co danh sach group.
/api/logs?limit=1 tra 200 khi chua dang nhap va co log.
/api/logs/stats tra 200 khi chua dang nhap va co thong ke log.
```

Nguyen nhan: cac route web-facing dang chi dung `inject_current_user(...)`, decorator nay non-blocking nen request khong token van duoc vao controller.

Trang thai local:

- Da thay bang `require_login(...)` cho `/api/groups`, `/api/groups/<id>` GET/PATCH/DELETE va `/api/groups/<id>/teachers`.
- Route gan teacher duoc boc `require_login(require_admin(...))`.
- Da thay bang `require_login(...)` cho `/api/logs/stats`, `/api/logs` GET, `/api/logs/clear`, legacy DELETE `/api/logs`, va `/api/logs/export`.
- Agent endpoint POST `/api/logs` giu `require_jwt(...)`, khong bi doi auth flow.
- Da them regression test dam bao request chua dang nhap nhan `401 Authentication required`.

File lien quan:

- `server/controllers/group_controller.py`
- `server/controllers/log_controller.py`
- `server/tests/test_groups.py`
- `server/tests/test_whitelist_and_logs.py`

Sau khi redeploy len Render, verify production phai tra 401:

```powershell
curl.exe -i "https://firewall-controller.onrender.com/api/groups"
curl.exe -i "https://firewall-controller.onrender.com/api/logs?limit=1"
curl.exe -i "https://firewall-controller.onrender.com/api/logs/stats"
```

### 7. Hotfix log secret: khong ghi plaintext Mongo URI

Hien tuong: code boot MongoDB co log `MONGO_URI` day du. Neu Render logs da ghi connection string, can rotate credential sau khi deploy ban mask log.

Trang thai local:

- Da them `_mask_connection_uri()` de mask credential thanh `***:***`.
- `get_mongo_client()` va `validate_config()` chi log Mongo URI da mask.
- Da them regression test cho MongoDB Atlas URI co username/password.

File lien quan:

- `server/database/config.py`
- `server/tests/test_app_factory.py`

## Ket qua firewall-only deep run cuoi

Run: `20260527_235108`

| Chi so | Ket qua |
| --- | --- |
| Steps | PASS=8, FAIL=0, SKIP=0 |
| Cleanup | CLEANUP_OK=5, cleanup_failures=0 |
| `deep_firewall_packet_matrix.passed` | true |
| Snapshot before mutation | domain/private/public = allow |
| Active Default Deny | domain/private/public = block |
| Allowed packet active | `1.1.1.1:443` OK |
| Blocked packet active | `151.101.1.69:443` blocked |
| Managed rule mutation | count `10 -> 11 -> 10` |
| Restore policy | domain/private/public = allow |
| Residual rules | 0 |
| Blocked packet after restore | `151.101.1.69:443` OK |

Ket luan: PowerShell/NetSecurity write backend da pass packet-level smoke tren mot may Windows Administrator thuc, bao gom Default Deny, self-allow, add/remove managed allow rule va restore.

## Kiem tra local da chay sau cac ban sua

| Lenh | Ket qua |
| --- | --- |
| `node --check server\views\static\js\pages\api_keys.js` | Pass |
| `.venv\Scripts\python.exe -m py_compile server\routes\pages.py` | Pass |
| `.venv\Scripts\python.exe -m py_compile server\controllers\group_controller.py server\controllers\log_controller.py` | Pass |
| `.venv\Scripts\python.exe -m py_compile server\database\config.py server\tests\test_app_factory.py` | Pass |
| `.venv\Scripts\python.exe -m pytest server\tests\test_app_factory.py -q --tb=short` | 4 passed |
| `.venv\Scripts\python.exe -m pytest server\tests\test_groups.py -q --tb=short` | 73 passed |
| `.venv\Scripts\python.exe -m pytest server\tests\test_whitelist_and_logs.py -q --tb=short` | 118 passed, 3 expected DeprecationWarning |
| `.venv\Scripts\python.exe -m pytest agent\tests -q --tb=short` | 8 passed |
| `.venv\Scripts\python.exe -m pytest server\tests\test_teacher_data_filtering.py -q --tb=short` | 81 passed |
| `.venv\Scripts\python.exe -m pytest server\tests\test_app_factory.py server\tests\test_agent_full.py server\tests\test_whitelist_and_logs.py -q --tb=short` | 184 passed, 3 expected DeprecationWarning |

## Ton dong con lai

### Can redeploy hotfix bao mat len Render

Public smoke sau deploy Render 2026-05-28 da thay `/api-keys` DOM fix va `/favicon.ico` len production, nhung production truoc hotfix van public group/log data. Can redeploy ban hien tai de dua cac sua sau len Render:

- Bat buoc login cho cac endpoint web-facing group/log.
- Mask MongoDB URI truoc khi ghi log.
- Sau deploy, verify 3 endpoint public leak o tren phai tra `401`.

Sau deploy hotfix, rerun full deep E2E de xac nhan production khong con fail policy heartbeat force sync.

### Can rerun full deep sau deploy

Chi chay khi co admin password that cua Render. Khong thu credential mac dinh.

Lenh khuyen nghi trong PowerShell Administrator:

```powershell
$AdminPassword = Read-Host "Render admin password"
powershell -ExecutionPolicy Bypass -File .\tools\saint-full-system-e2e.ps1 -ServerUrl "https://firewall-controller.onrender.com" -BootstrapAdminUsername "admin" -BootstrapAdminPassword $AdminPassword -RunRealFirewallPolicy -WriteBackend powershell -Deep -TimeoutSeconds 60 -DeepPacketTimeoutSeconds 35
Remove-Variable AdminPassword -ErrorAction SilentlyContinue
```

Neu chi can packet firewall nhanh:

```powershell
$AdminPassword = Read-Host "Render admin password"
powershell -ExecutionPolicy Bypass -File .\tools\saint-full-system-e2e.ps1 -ServerUrl "https://firewall-controller.onrender.com" -BootstrapAdminUsername "admin" -BootstrapAdminPassword $AdminPassword -RunRealFirewallPolicy -WriteBackend powershell -Deep -FirewallOnly -SkipBuild -SkipAgentExeLaunch -TimeoutSeconds 60 -DeepPacketTimeoutSeconds 35
Remove-Variable AdminPassword -ErrorAction SilentlyContinue
```

Luu y: `-RunRealFirewallPolicy` co thay doi Windows Firewall that trong luc test va runner se cleanup/restore. Chi chay tren may canary co quyen Administrator va co duong khoi phuc mang.

### Kiem tra Render logs va secret rotation

Sau khi redeploy:

1. Mo Render Dashboard -> service `firewall-controller` -> `Logs`.
2. Trigger 3 lenh verify 401 o tren, roi tim trong Logs:
   - `path:/api/groups status_code:401`
   - `path:/api/logs status_code:401`
   - `path:/api/logs/stats status_code:401`
3. Tim cac chuoi nghi secret: `MONGO_URI`, `mongodb+srv://`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, `SECRET_KEY`, `API_KEY_HMAC_SECRET`. Khong copy secret vao chat/report.
4. Neu thay plaintext secret trong log cu: rotate sau khi da deploy ban mask log.

Secret can uu tien rotate:

- MongoDB credential trong `MONGO_URI`: tao password/user moi ben MongoDB Atlas, cap nhat Render Environment, deploy lai, sau do disable/delete credential cu.
- `SECRET_KEY`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, `API_KEY_HMAC_SECRET`: tao random secret moi, update trong Render Environment, chon deploy. Viec nay co the lam user/agent token hien tai het hieu luc, nen can dang nhap lai va cho agent refresh/re-register neu can.
- Admin password production: doi trong UI/admin flow neu credential tung bi log/chia se.

Tai lieu Render tham khao:

- Logs: https://render.com/docs/logging
- Environment variables/secrets: https://render.com/docs/configure-environment-variables
- Secret handling: https://render.com/articles/how-render-handles-secrets-and-environment-variables

### Chua test hoan toan trong 1 may nay

- Multi-machine vat ly: da test 24 synthetic agents, chua test 24 may Windows that trong cung lab.
- Reboot/service autostart: runner da tao script post-reboot check, chua tu reboot may.
- Soak dai hon 30 phut: da pass 30 phut, chua soak nhieu gio/ngay.
- Canary PowerShell backend tren nhieu may: moi pass mot may Windows Administrator.

### Van chua nen cat fallback whitelist ngay

Chua nen xoa fallback embedded whitelist/pseudo-ID tren production neu chua co:

- Backup DB production.
- Migration write da chay va verify.
- Log/metric xac nhan khong con request dung pseudo-ID `group::...`.
- It nhat mot release quan sat dual-path sau migration.

## Danh gia release readiness

| Hang muc | Trang thai |
| --- | --- |
| Server API/RBAC co ban | Tot, da duoc E2E va unit/integration test rong |
| GUI admin API Keys | Public smoke sau deploy OK, tiep tuc monitor |
| Agent/server contract | Tot voi register/JWT/heartbeat/sync/log; can rerun full deep de xac nhan policy force sync tren production |
| Firewall Default Deny PowerShell backend | Pass tren 1 may Windows admin, can canary them |
| Cleanup/rollback firewall | Pass: restore allow, residual rules 0 |
| Whitelist final cutover | Chua san sang xoa fallback production |

Ket luan ngan: he thong da dat muc smoke/E2E sau tren mot workstation Windows admin, nhung truoc khi coi la release production final can redeploy hotfix bao mat group/log + mask log secret, verify unauthenticated endpoints tra 401, rerun full deep tren Render, canary firewall PowerShell tren them may lab va chua xoa whitelist fallback cho toi khi co bang chung production khong con pseudo-ID.
