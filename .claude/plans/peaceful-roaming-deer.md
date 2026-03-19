# Plan: Tích hợp Whitelist Profiles vào trang /whitelist

## Tổng quan
Khi teacher mở `/whitelist`, hiện dropdown chọn Profile. Teacher thêm/xóa domain trực tiếp trên trang Whitelist → lưu vào profile đang chọn. Trang Whitelist trở thành editor chính cho profile domains.

## Trải nghiệm theo Role

### Admin
- Không thay đổi gì — thấy toàn bộ whitelist items (global + group) như hiện tại
- Không hiện profile selector (admin quản lý profile qua trang Group Detail)

### Teacher
- Thấy **Profile Selector Bar** phía trên Add Items Section
- Dropdown chọn: "-- Không chọn Profile --" | "Profile A (Group X)" | "Profile B (Group Y)" ...
- **Khi chưa chọn profile**: Xem danh sách whitelist read-only (global + group items), các nút Add/Remove bị ẩn
- **Khi đã chọn profile**:
  - Danh sách hiện domains CỦA PROFILE đó (không phải group base whitelist)
  - Các nút Add Domain/IP/URL thêm vào profile
  - Nút Remove xóa khỏi profile
  - Badge hiển thị "Editing: [Profile Name] in [Group Name]"
  - Bulk Import cũng lưu vào profile

## Phases

### Phase 1: Backend — API lấy danh sách profiles của teacher (across all groups)

**File: `server/controllers/whitelist_profile_controller.py`**
- Thêm endpoint mới: `GET /api/my-profiles`
  - Decorator: `require_login`
  - Logic: Lấy tất cả groups teacher có quyền → query tất cả profiles của teacher đó trong tất cả groups
  - Response: `{ success: true, data: [{ _id, name, group_id, group_name, domains, is_active, teacher_id }] }`

**File: `server/services/whitelist_profile_service.py`**
- Thêm method: `get_teacher_profiles(teacher_id, group_ids) -> List[Dict]`
  - Query: `{ teacher_id: ObjectId(teacher_id), group_id: { $in: group_ids } }`
  - Join group name vào mỗi profile

### Phase 2: Frontend — Profile Selector Bar (chỉ Teacher thấy)

**File: `server/views/templates/whitelist.html`**
- Thêm section mới giữa Stats Cards và Add Items Section:
```html
<!-- Profile Selector Bar (Teacher only) -->
<div id="profileSelectorBar" class="card mb-4" style="display:none">
  <div class="card-body">
    <div class="row align-items-center">
      <div class="col-md-6">
        <label class="fw-bold"><i class="fas fa-user-edit me-2"></i>Chọn Profile để chỉnh sửa</label>
        <select id="profileSelect" class="form-select mt-2">
          <option value="">-- Chế độ xem (Read-only) --</option>
        </select>
      </div>
      <div class="col-md-6" id="profileInfoBadge" style="display:none">
        <span class="badge bg-success fs-6">
          <i class="fas fa-edit me-1"></i>
          Đang sửa: <span id="profileEditingName"></span>
        </span>
      </div>
    </div>
  </div>
</div>
```

### Phase 3: Frontend — JS Logic thay đổi behavior khi chọn Profile

**File: `server/views/static/js/whitelist.js`**
- Thêm state vars:
  ```js
  let teacherProfiles = [];
  let selectedProfileId = '';
  let selectedProfileData = null;
  let isProfileEditMode = false;
  ```

- Thêm function `loadTeacherProfiles()`:
  - Gọi `GET /api/my-profiles`
  - Populate dropdown `#profileSelect` với format: "[Profile Name] — [Group Name]"

- Thêm handler `onProfileSelected(profileId)`:
  - Nếu `profileId == ''`: chuyển về mode xem (read-only), gọi `loadItems()` bình thường
  - Nếu có profileId: set `isProfileEditMode = true`, `selectedProfileData = ...`, render domains của profile

- Sửa `renderItems()`:
  - Nếu `isProfileEditMode`: render `selectedProfileData.domains` thay vì `itemsData`
  - Các domain hiển thị với scope badge "Profile: [name]"
  - Nút Remove gọi `removeProfileDomain()` thay vì `removeItem()`

- Sửa `addItem()` / `addItemToGroup()`:
  - Nếu `isProfileEditMode`: thay vì POST /api/whitelist hoặc PATCH group, gọi `PATCH /api/groups/{group_id}/profiles/{profile_id}` với domains mới
  - Build domains array = `selectedProfileData.domains + newDomain` → PATCH update

- Thêm function `removeProfileDomain(index)`:
  - Xóa domain tại index trong `selectedProfileData.domains`
  - PATCH update profile

- Thêm function `saveProfileDomains(domains)`:
  - `PATCH /api/groups/{group_id}/profiles/{profile_id}` body: `{ domains: [...] }`
  - Refresh profile data

- Sửa `DOMContentLoaded`:
  - Sau `loadGroups()`, check `window.SAINT_AUTH.isTeacher` → show `#profileSelectorBar`, gọi `loadTeacherProfiles()`
  - Bind event change trên `#profileSelect` → `onProfileSelected()`

### Phase 4: RBAC UI — Ẩn/hiện phù hợp

**File: `server/views/static/js/whitelist.js`**
- Khi teacher chưa chọn profile:
  - Ẩn Add Items Section (`.add-items-section`)
  - Ẩn bulk actions
  - Ẩn nút Remove trên mỗi item
  - Hiện thông báo: "Chọn 1 Profile để bắt đầu chỉnh sửa whitelist"

- Khi teacher đã chọn profile:
  - Hiện Add Items Section
  - Ẩn Scope selector trong Add Modal (luôn là profile)
  - Ẩn Group selector trong Add Modal
  - Hiện nút Remove trên mỗi domain
  - Stats cards cập nhật theo profile domains

**File: `server/views/templates/whitelist.html`**
- Add Items Section: thêm `id="addItemsSection"` để JS toggle visibility
- Scope select trong modal: thêm logic ẩn khi teacher đang edit profile

### Phase 5: Bulk Import tích hợp Profile

**File: `server/views/static/js/whitelist.js`**
- Sửa `bulkImportItems()`:
  - Nếu `isProfileEditMode`: parse lines → build domains array → merge với profile.domains hiện tại → PATCH update profile
  - Không gọi `/api/whitelist/bulk`

## Tóm tắt thay đổi files

| File | Thay đổi |
|------|----------|
| `whitelist_profile_controller.py` | +1 endpoint `GET /api/my-profiles` |
| `whitelist_profile_service.py` | +1 method `get_teacher_profiles()` |
| `whitelist.html` | +Profile Selector Bar HTML, +id cho Add Items Section |
| `whitelist.js` | +Profile state, +load/select/save profile functions, sửa addItem/removeItem/renderItems/bulkImport |

## Không thay đổi
- `whitelist_controller.py` — không cần sửa backend whitelist endpoints
- `whitelist_service.py` — không cần sửa
- Agent sync logic — không ảnh hưởng (vẫn dùng active profile override)
- Admin experience — hoàn toàn không đổi
