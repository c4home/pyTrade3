# Kế Hoạch Tính Năng: Chợ Kịch Bản Cộng Đồng (Community Marketplace & Smart Forking)

> **Hướng dẫn sử dụng (Quy trình Tiết kiệm 75% Token theo `QUY_TRINH_TOI_UU_TOKEN_ANTIGRAVITY.md`):**
> 1. File kế hoạch này đã đóng băng phạm vi (Scope Freeze) và định nghĩa chi tiết kiến trúc, trường hợp biên cùng danh sách công việc cuốn chiếu.
> 2. Khi bắt tay vào thực hiện từng bước, bạn chỉ cần mở phiên chat mới và gửi lệnh ngắn gọn:  
>    👉 *"Dựa vào file `docs/plans/community_marketplace_plan.md`, hãy thực hiện **Task 1**."*

---

## 1. Mục Tiêu & Ràng Buộc Kỹ Thuật

### 1.1. Mục Tiêu Nghiệp Vụ & Con Hào Kinh Tế (Moat)
- **Giải quyết bài toán chống sao chép**: Bất kỳ ai cũng có thể clone mã nguồn frontend trong vài ngày, nhưng không thể sao chép được kho dữ liệu kịch bản thực tế cùng sự tương tác sống động của cộng đồng kiều bào.
- **Ra mắt Tab 4: "Cộng đồng" (Community Marketplace)** trên thanh điều hướng chính, mở ra thư viện kịch bản đa dạng kèm câu chuyện đời thực (*Hồi hương Đà Lạt, FIRE LMNP Ngoại ô Paris, Gia đình 2 con về Đà Nẵng, Coast-FIRE IT...*).
- **Cơ chế Smart Forking (Nhân bản thông minh)**: Cho phép người dùng clone kịch bản cộng đồng với 1 cú click; hệ thống tự động giữ nguyên tỷ lệ phân bổ danh mục & mốc thời gian nhưng áp vào đúng số tiền tiết kiệm & thu nhập thực tế của người dùng.
- **Bảo vệ quyền riêng tư kép**: Tự động ẩn danh tính thật (chỉ dùng Nickname), tùy chọn chuẩn hóa dữ liệu sang Tỷ lệ % (không làm lộ tài sản thật) và kèm mục ghi chú "Hành trình đời thực".

### 1.2. Ràng Buộc Kỹ Thuật Bắt Buộc
- **Local-First & Hybrid Fallback**: Luôn đóng gói sẵn 6 kịch bản thực chiến kinh điển (`community-seed.js`) để web hoạt động đầy đủ ngay cả khi chạy offline, không có backend hoặc deploy tĩnh.
- **Backend Tối giản**: FastAPI + `sqlite3` thuần (không dùng ORM), bảng `community_templates` lưu kịch bản chia sẻ, lượt Upvote và Fork count.
- **Dual-Theme 100%**: Sử dụng hoàn toàn biến CSS (`var(--bg-card)`, `var(--text-main)`, `var(--text-muted)`, `var(--border-subtle)`). Tuyệt đối cấm hardcode nền tối hay màu chữ xám nhạt.
- **Typography & No-LaTeX**: Thống nhất font `Inter` (`var(--font-sans)`), không dùng ký hiệu LaTeX, không icon/emoji trang trí rườm rà.
- **Đa ngôn ngữ & Cache-Busting**: Khai báo đầy đủ từ điển `vi`, `en`, `fr` trong `frontend/js/i18n.js` và tăng query param `?v=...` trong `frontend/index.html`.

---

## 2. Các File & Vị Trí Cần Thay Đổi / Thêm Mới

1. **`frontend/js/community-seed.js` (Tạo mới)**:
   - Chứa mảng dữ liệu tĩnh `COMMUNITY_SEED_TEMPLATES` với 6 kịch bản kinh điển được biên tập thực chiến (đầy đủ các biến tài chính, BĐS LMNP, thuế Pháp/VN và chỉ số sức khỏe Healthspan).
2. **`frontend/js/community.js` (Tạo mới)**:
   - Module `window.CommunityMarketplace`:
     - Render danh sách thẻ kịch bản dạng Card Grid kèm bộ lọc (Quốc gia, Độ tuổi hưu, Phong cách FIRE).
     - Thuật toán `smartForkTemplate(templateId)`: Lấy cấu trúc kịch bản mẫu, map vào số dư/thu nhập của người dùng hiện tại và kích hoạt render lại biểu đồ.
     - Xử lý mở Modal "Xuất bản Kịch bản" (Publish Modal) kèm khử định danh cá nhân và chuẩn hóa tỷ lệ %.
     - Xử lý tương tác Upvote (lưu local + đồng bộ API khi có mạng).
3. **`frontend/index.html`**:
   - Dòng ~`140`: Thêm nút Tab 4 trên thanh điều hướng Sidebar (`data-tab="tab-community"`).
   - Dòng ~`2400`: Thêm phần thân `<section class="tab-pane" id="tab-community">` gồm Hero Banner, Thanh tìm kiếm & Bộ lọc nhanh, Lưới kịch bản (Grid), và Modal "Đóng góp kịch bản".
   - Dòng cuối file: Nhúng thẻ `<script src="js/community-seed.js?v=2.1.0"></script>` và `<script src="js/community.js?v=2.1.0"></script>`.
4. **`frontend/css/styles.css`**:
   - Thêm các class CSS cho layout Marketplace: `.community-grid`, `.community-card`, `.community-badge`, `.community-story-box`, `.fork-btn`, `.upvote-btn`, hỗ trợ hoàn hảo cả Dark Mode và Light Mode.
5. **`frontend/js/i18n.js`**:
   - Bổ sung các khóa dịch cho Tab Cộng đồng: tiêu đề, bộ lọc, các phong cách FIRE, nhãn nút Upvote, Smart Fork, và các cảnh báo riêng tư.
6. **`backend/auth.py` & `backend/main.py`**:
   - `auth.py`: Hàm `init_community_table()`, `get_community_templates()`, `publish_community_template()`, `upvote_community_template()`, `increment_fork_count()`.
   - `main.py`: Các endpoint `GET /api/community/templates`, `POST /api/community/templates`, `POST /api/community/templates/{id}/upvote`, `POST /api/community/templates/{id}/fork`.

---

## 3. Phân Tích Rủi Ro Logic & Trường Hợp Biên (Edge Cases)

- **Trường hợp 1: Chạy khi offline hoặc không có Backend**:
  - *Giải pháp*: `community.js` tự động phát hiện nếu `fetch('/api/community/templates')` lỗi thì nạp ngay `COMMUNITY_SEED_TEMPLATES`. Lượt Upvote được lưu tạm vào `localStorage` (`pyretrait_community_upvotes`) để không bị mất trải nghiệm.
- **Trường hợp 2: Smart Fork khi tiền tệ của kịch bản khác tiền tệ người dùng (EUR ↔ VND ↔ USD)**:
  - *Giải pháp*: Khi fork theo chế độ "Chuẩn hóa %", hệ thống chỉ giữ:
    - Phân bổ tài sản: Tỷ lệ % Cổ phiếu / Trái phiếu / BĐS / Tiền mặt.
    - Tỷ lệ rút vốn và chiến lược: Guyton-Klinger / Bengen 4% / VPW.
    - Mốc thời gian: Tuổi nghỉ hưu, tuổi thọ, các giai đoạn chi tiêu (Go-go, Slow-go).
    - Các tỷ lệ chi tiêu (% chi tiêu hưu trí so với chi tiêu tích lũy).
    Số tiền tuyệt đối (Savings, Income) giữ nguyên theo hồ sơ hiện tại của người dùng, tránh việc kịch bản 500,000 EUR biến thành 500,000 VND.
- **Trường hợp 3: Rò rỉ thông tin cá nhân khi xuất bản kịch bản**:
  - *Giải pháp*: Modal xuất bản chạy qua hàm lọc dữ liệu nghiêm ngặt `sanitizePlanForPublishing()`:
    - Xóa bỏ ID người dùng, email, họ tên thật, các ghi chú nhạy cảm.
    - Nếu bật "Chuẩn hóa %": Quy đổi toàn bộ số dư tuyệt đối sang cơ số chuẩn 100,000 đơn vị tiền tệ hoặc tỷ lệ %, chỉ công khai chiến lược tư duy.
- **Trường hợp 4: Kịch bản bị xóa hoặc ID không tồn tại**:
  - *Giải pháp*: Có thông báo Toast hiển thị nhã nhặn, fallback an toàn về kịch bản mặc định mà không làm đơ ứng dụng.

---

## 4. Danh Sách Công Việc Cuốn Chiếu (Actionable Tasks)

### [ ] Task 1: Xây Dựng 6 Kịch Bản Thực Chiến Offline (`frontend/js/community-seed.js`)
- Tạo file `frontend/js/community-seed.js` chứa 6 kịch bản điển hình được biên soạn sâu sắc:
  1. *Kỹ sư IT 35 tuổi ngoại ô Paris: Tích lũy PEA + BĐS LMNP, mục tiêu FIRE tuổi 48*.
  2. *Cặp đôi 42 tuổi hồi hương Đà Nẵng: Bán tài sản Pháp, chuyển đổi kiều hối, chi phí sống tối ưu*.
  3. *Chuyên gia tài chính 29 tuổi: Chiếc lược Turo Car-sharing + Thác rút tiền Livret A/Assurance-Vie*.
  4. *Gia đình 2 con về Đà Lạt: Giáo dục song ngữ, quỹ y tế dự phòng Healthspan cao*.
  5. *Độc thân 38 tuổi Coast-FIRE: Đạt điểm hòa vốn tài chính, giảm tải công việc để kéo dài tuổi trẻ*.
  6. *Hưu trí truyền thống kết hợp Lương hưu Pháp Décote + BHXH Việt Nam 2024*.
- Mỗi kịch bản có đầy đủ metadata: `id`, `title`, `authorNickname`, `avatarSeed`, `targetAge`, `location`, `tags`, `story`, `upvotes`, `forks`, và `planData`.

### [ ] Task 2: Dựng Giao Diện Tab 4 "Cộng Đồng" & Hệ Thống CSS Dual-Theme (`index.html` & `styles.css`)
- Sửa `frontend/index.html`:
  - Thêm nút Tab 4 vào `<aside class="sidebar">` (ngang hàng với *Dòng tiền*, *Sức khỏe*, *Tối ưu thuế*).
  - Thêm thẻ `<section class="tab-pane" id="tab-community">`:
    - Hero Header giới thiệu Thư viện Kịch bản Kiều bào.
    - Cụm điều khiển: Ô tìm kiếm từ khóa, thanh lọc Tag (`Tất cả`, `Hồi hương VN`, `Bất động sản Pháp`, `Gia đình có con`, `Coast-FIRE`).
    - Khung lưới `community-grid` để render các thẻ kịch bản.
    - Nút mở Modal "Chia sẻ Kịch bản Của Bạn".
- Sửa `frontend/css/styles.css`:
  - Viết style cho `.community-grid`, `.community-card`, `.badge-tag`, `.story-quote`, `.btn-fork`, `.btn-upvote`.
  - Đảm bảo tương phản hoàn hảo trên cả Dark Mode và Light Mode (chữ đậm trên nền trắng ở Light Mode, chữ sáng neon trên nền tối ở Dark Mode).

### [ ] Task 3: Phát Triển Engine Quản Lý Kịch Bản & Thuật Toán "Smart Fork" (`frontend/js/community.js`)
- Tạo file `frontend/js/community.js` với các chức năng chính:
  - `initCommunityMarketplace()`: Nạp kịch bản từ backend (hoặc fallback seed), gán sự kiện tìm kiếm và lọc tag.
  - `renderTemplateCards(templates)`: Render động danh sách kịch bản ra DOM.
  - `smartForkTemplate(templateId)`: Thuật toán trích xuất chiến lược cốt lõi và áp vào kế hoạch đang mở của người dùng, hiển thị thông báo chúc mừng và chuyển ngay sang Tab Dòng tiền để xem biểu đồ mới.
  - `handleUpvote(templateId)`: Tăng điểm tín nhiệm, lưu trạng thái tránh spam vote.
  - `openPublishModal()` & `submitPublishPlan()`: Khử định danh dữ liệu và gửi kịch bản lên cộng đồng.

### [ ] Task 4: Triển Khai Backend SQLite & API Endpoint (`backend/auth.py` & `backend/main.py`)
- Sửa `backend/auth.py`:
  - Thêm bảng `community_templates` trong SQLite (`id`, `title`, `author_name`, `tags`, `story`, `plan_data`, `upvotes`, `forks`, `created_at`).
  - Viết các hàm query lấy danh sách, thêm kịch bản mới, tăng upvote và tăng fork.
- Sửa `backend/main.py`:
  - Thêm các endpoint REST API:
    - `GET /api/community/templates` (hỗ trợ lọc theo tag/search).
    - `POST /api/community/templates` (lưu kịch bản mới).
    - `POST /api/community/templates/{id}/upvote` (tăng lượt thích).
    - `POST /api/community/templates/{id}/fork` (tăng lượt fork).

### [ ] Task 5: Đa Ngôn Ngữ, Cache-Busting & Kiểm Thử Hoàn Tất
- Sửa `frontend/js/i18n.js`:
  - Bổ sung từ điển dịch đầy đủ cho 3 ngôn ngữ: Tiếng Việt (`vi`), Tiếng Anh (`en`), Tiếng Pháp (`fr`).
- Sửa `frontend/index.html`:
  - Tăng tham số phiên bản `?v=2.1.0` tại các thẻ script và stylesheet.
- Kiểm thử toàn diện:
  - Kiểm tra chế độ Tiếng Việt (`vi`) trên Dark Mode & Light Mode.
  - Thử nghiệm Smart Fork một kịch bản và kiểm tra biểu đồ dòng tiền cập nhật chính xác.
  - Thử ngắt kết nối backend để kiểm tra cơ chế Offline Fallback hoạt động trơn tru.
