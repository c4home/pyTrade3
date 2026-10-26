# Kế Hoạch Tính Năng: [Tên Tính Năng / Bản Nâng Cấp]

> **Hướng dẫn sử dụng (Quy trình Tiết kiệm 75% Token):**
> 1. **Giai đoạn 1 & 2 (Làm rõ & Đóng băng phạm vi):** Hoàn thiện file kế hoạch này trước khi viết bất kỳ dòng code nào. Tra cứu số dòng tại [`docs/CODEBASE_MAP.md`](file:///Users/canhhung/Documents/pyRetrait/docs/CODEBASE_MAP.md).
> 2. **Giai đoạn 3 (Mở Phiên Chat Mới & Thực thi từng Task):** Sau khi chốt file này, bấm **New Chat** và gửi câu lệnh ngắn gọn:  
>    *"Dựa vào file `docs/plans/[ten_file].md`, hãy thực hiện **Task 1**. Chỉ dùng `replace_file_content` sửa đúng dòng đã chỉ định."*

---

## 1. Mục Tiêu & Ràng Buộc Kỹ Thuật
- **Mục tiêu nghiệp vụ**: [Mô tả ngắn gọn 2–3 câu về bài toán cần giải quyết].
- **Ràng buộc bắt buộc**:
  - 100% tính toán chạy trên trình duyệt (Vanilla JS), không đưa logic tài chính sang Backend.
  - Hỗ trợ cả Dark Mode và Light Mode bằng biến CSS (`var(--bg-card)`, `var(--text-main)`, `var(--text-muted)`).
  - Không dùng cú pháp LaTeX, không dùng icon/emoji trang trí, dùng font `var(--font-sans)` cho văn bản và công thức.
  - Nếu có thêm chữ mới trên giao diện: Bổ sung từ điển `vi`, `en`, `fr` trong `frontend/js/i18n.js` và tăng version `?v=...` trong `frontend/index.html`.

---

## 2. Các File & Vị Trí Hàm Cần Thay Đổi
- `frontend/js/engine.js` (Dòng `[X – Y]`, hàm `[tenHam]`): [Mô tả thay đổi].
- `frontend/js/ui.js` (Dòng `[X – Y]`, hàm `[tenHam]`): [Mô tả thay đổi].
- `frontend/index.html` (Dòng `[X – Y]`, thẻ `[#id]`): [Mô tả thay đổi].
- `frontend/js/i18n.js` (Từ điển `vi`, `en`, `fr`): [Danh sách các khóa dịch mới].

---

## 3. Phân Tích Rủi Ro Logic & Trường Hợp Biên (Edge Cases)
- **Trường hợp 1**: [Ví dụ: Khi người dùng nhập giá trị bằng 0 hoặc âm thì xử lý thế nào?].
- **Trường hợp 2**: [Ví dụ: Khi đổi đơn vị tiền tệ giữa EUR, VND và USD thì số liệu có tự quy đổi đúng không?].

---

## 4. Danh Sách Công Việc Cuốn Chiếu (Actionable Tasks)

- [ ] **Task 1 — Cập nhật lõi tính toán (`frontend/js/engine.js`)**:
  - Sửa hàm `[tenHam]` tại dòng `[X – Y]`.
  - Công thức kiểm chứng: `[Viết công thức dạng văn bản thường + 1 ví dụ số cụ thể]`.
- [ ] **Task 2 — Cập nhật giao diện & kết nối sự kiện (`frontend/index.html` & `frontend/js/ui.js`)**:
  - Thêm/sửa phần tử DOM tại `frontend/index.html` dòng `[X – Y]`.
  - Cập nhật hàm render tại `frontend/js/ui.js` dòng `[X – Y]`.
- [ ] **Task 3 — Đồng bộ đa ngôn ngữ & Cache-busting (`frontend/js/i18n.js` & `frontend/index.html`)**:
  - Thêm khóa dịch vào `i18n.js`.
  - Tăng tham số `?v=...` ở cuối `frontend/index.html` (dòng `27` và `4600–4609`).
- [ ] **Task 4 — Kiểm thử trọng tâm (Targeted Verification)**:
  - Kiểm tra tĩnh công thức và giao diện ở chế độ Tiếng Việt (`vi`) trên cả Dark Mode và Light Mode.
