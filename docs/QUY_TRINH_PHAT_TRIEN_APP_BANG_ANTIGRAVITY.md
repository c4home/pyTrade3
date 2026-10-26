# Cẩm Nang Toàn Diện: Quy Trình Phát Triển App Bằng Antigravity (Tối Ưu Token, Kiến Trúc, Bảo Mật & Pháp Lý)

> **Đo hiệu suất tự động (1 lệnh):** `./benchmark.sh "ghi chú"` — tự đo số dòng, dung lượng, test và ghi vào `docs/BENCHMARK_LOG.md` (xem Phần VI).

Tài liệu này là **cẩm nang hợp nhất duy nhất** của dự án `pyRetrait`, được sắp xếp **theo đúng trình tự thời gian từ lúc khởi tạo dự án (Giai đoạn 0), vận hành thực tế (Giai đoạn 6), đến chiến lược bảo trì dài hạn (Phần V)**. Mọi kiến thức có liên kết với nhau (Kiến trúc & Schema Migration, Quy chuẩn UI & Tương thích Mobile, Thi công & Gỡ lỗi 2-Strike, Bảo mật OWASP, Pháp lý GDPR và Cẩm nang Bảo trì bền vững) đều được đặt cạnh nhau tại đúng vị trí, giúp bạn tra cứu tức thì, **tiết kiệm 65% – 85% lượng token tiêu thụ** và **ngăn ngừa 95% lỗi hồi quy, ảo giác cũng như rủi ro kỹ thuật dài hạn**.

---

## Phần I. Nền Tảng Cốt Lõi: Vì Sao Token Bị Tiêu Tốn Nhanh & 10 Nguyên Tắc Thao Tác Hàng Ngày

### 1. Ba Nguyên Nhân Gây Đốt Token Nhanh Nhất

1. **Hiệu Ứng Tuyết Lăn Của Ngữ Cảnh (Cumulative Context):**
   - Mỗi khi bạn gửi một tin nhắn mới, hệ thống không chỉ gửi riêng câu nói đó mà phải **đóng gói và gửi lại toàn bộ lịch sử từ đầu phiên chat**, bao gồm:
     - Quy tắc hệ thống (`.agents/rules/GEMINI.md`).
     - Toàn bộ các câu hỏi – đáp trước đó.
     - Lịch sử các công cụ đã chạy (`view_file`, `grep_search`, lệnh terminal).
     - Ảnh chụp màn hình từ Browser Subagent (mỗi ảnh ngốn hàng ngàn token).
   - **Hệ quả:** Ở lượt chat thứ 1, một câu lệnh ngắn chỉ tốn ~5.000 token. Nhưng đến lượt chat thứ 30, **cùng một câu lệnh 5 chữ ("sửa tiếp chỗ này") có thể ngốn 150.000 – 250.000 token** vì phải cõng toàn bộ lịch sử phía trước!

2. **Mò Mẫm Tìm Kiếm Trong File Khổng Lồ (Context Hunting):**
   - Trước đây `ui.js` từng dài hơn 8.200 dòng, nay đã được tách thành **bộ 6 file UI theo từng Tab độc lập** (`ui.js`, `ui-tab1-charts.js`, `ui-tab1-streams.js`, `ui-tab2-health.js`, `ui-tab3-taxes.js`, `ui-modals.js`) cùng với `frontend/index.html` (~4.614 dòng) và `frontend/css/styles.css` (~8.500+ dòng).
   - Kết hợp với bản đồ chỉ mục dòng code (`docs/CODEBASE_MAP.md`), mỗi lần bạn yêu cầu sửa 1 nút bấm hay 1 hàm ở Tab nào, AI chỉ cần mở đúng file của Tab đó và nhảy thẳng tới đúng 50–100 dòng cần sửa, giảm 90% token đọc file!

3. **Vòng Lặp Thử – Sai Mù Quáng & Gửi Tin Nhắn Vụn Vặt (Micro-Prompts):**
   - Yêu cầu code ngay khi chưa chốt thiết kế hoặc gửi liên tiếp 3–4 tin nhắn ngắn rời rạc (*"đổi chữ A"*, rồi lại *"xóa dòng B"*, rồi lại *"cho mục C xuống dòng"*) khiến AI phải nạp lại toàn bộ lịch sử 100k+ token nhiều lần liên tiếp.

---

### 2. Bốn Lệnh Slash Commands Đặc Quyền Của Antigravity (Dùng Đúng Thời Điểm)

Hãy tận dụng tối đa 4 lệnh nội bộ của Antigravity tương ứng với từng giai đoạn phát triển:

| Lệnh Slash | Thời điểm vàng để gõ lệnh | Tác dụng thực tế |
| :--- | :--- | :--- |
| **`/grill-me`** | **Giai đoạn 1** (Khi mới có ý tưởng lớn nhưng chưa rõ hết các góc khuất) | AI sẽ đóng vai Kiến trúc sư trưởng phỏng vấn ngược lại bạn từng câu ngắn gọn, giúp phát hiện các trường hợp biên (edge cases) trước khi viết 1 dòng code nào. |
| **`/plan`** | **Giai đoạn 4** (Khi bắt đầu chia nhỏ tính năng lớn thành các bước thực thi) | Kích hoạt chế độ lập kế hoạch có cấu trúc chặt chẽ trước khi chạm vào code. |
| **`/compact`** | **Giai đoạn 5** (Khi đang làm dở việc mà cuộc trò chuyện đã qua 10–12 lượt) | Nén toàn bộ lịch sử dài phía trước thành bản tóm tắt tinh gọn, giải phóng 85% bộ nhớ ngữ cảnh để làm tiếp mượt mà. |
| **`/learn`** | **Sau khi bạn vừa sửa lưng AI hoặc tìm ra 1 quy tắc hay** | Ra lệnh cho Antigravity đúc kết bài học vừa rồi và ghi nhớ vĩnh viễn vào quy tắc dự án/hệ thống để **không bao giờ mắc lại lỗi đó lần thứ 2**. |

---

### 3. Mười Ba Nguyên Tắc Vàng Trong Thao Tác Hàng Ngày

1. **Nguyên Tắc "1 Nhiệm Vụ = 1 Phiên Chat Mới" (Quan Trọng Số 1):**
   - **Bắt buộc bấm `New Chat (+)` khi:** (a) Vừa hoàn thành xong 1 Task trong file kế hoạch hoặc sửa xong 1 bug lớn; (b) Chuẩn bị chuyển từ việc sửa thuật toán (`engine.js`) sang việc chỉnh giao diện (`index.html`, `styles.css`); (c) Phiên chat đã chạm ngưỡng **10 – 12 lượt đối thoại**.
   - Nếu đang làm dở việc mà hội thoại bắt đầu dài: Gõ lệnh **`/compact`** để AI tóm tắt gọn ngữ cảnh trước khi làm tiếp.

2. **Kỹ Thuật Gộp Yêu Cầu (Prompt Batching — Không Gửi Lắt Nhắt):**
   - Thay vì gửi 3–4 tin nhắn ngắn nối tiếp nhau, hãy gom tất cả các chỉnh sửa giao diện/văn bản vào **1 danh sách đánh số duy nhất** rồi gửi 1 lần:
     > **❌ Cách tốn gấp 3 lần token (Gửi 3 lượt rời rạc):**
     > - Lượt 1: *"Xóa chữ (rút 4%/năm)..."*
     > - Lượt 2: *"Đổi tiêu đề Cách Tính Mục Tiêu thành Điều Kiện..."*
     > - Lượt 3: *"Mục 3 phải cùng cỡ chữ với mục 2 và xuống dòng..."*
     >
     > **✅ Cách chuẩn tiết kiệm token (Gom vào 1 lượt duy nhất):**
     > *"Đọc `@docs/CODEBASE_MAP.md` và sửa trong `frontend/index.html` (khu vực Tab 1) các điểm sau:*
     > *1. Đổi tiêu đề thẻ 'Cách Tính...' thành 'Điều Kiện...'*
     > *2. Xóa các đoạn chữ '(rút 4%/năm)'*
     > *3. Đổi chấm tròn '• Đạt chuẩn an toàn' thành '3. Đạt chuẩn an toàn', cùng cỡ chữ với mục 2 và ngắt dòng nội dung bên dưới."*

3. **Luôn Đính Kèm Bản Đồ Dòng Code (`@docs/CODEBASE_MAP.md`) Khi Sửa File Lớn:**
   - Khi cần sửa các file UI (`ui-tab1-charts.js`, `ui-tab1-streams.js`, `ui-tab2-health.js`, `ui-tab3-taxes.js`, `ui-modals.js`, `ui.js`), `styles.css`, `index.html`, `patrimoine.js`, `engine.js` hoặc `i18n.js`, hãy nhắc tên hàm/thẻ hoặc đính kèm `@docs/CODEBASE_MAP.md`. AI sẽ nhảy thẳng tới đúng 80 dòng liên quan thay vì đọc mò hàng ngàn dòng.

4. **Kiểm Soát Chặt `browser_subagent` — Ưu Tiên Kiểm Thử Bằng `./verify_js.sh`:**
   - Một lần gọi `browser_subagent` mở trình duyệt và chụp 5 tấm ảnh màn hình tiêu tốn **40.000 – 90.000 token** (đắt gấp 10–15 lần một lượt sửa code).
   - Trong `.agents/rules/GEMINI.md`, AI đã **bị cấm tự ý bật `browser_subagent`** nếu bạn không yêu cầu rõ. Thay vào đó, AI dùng `./verify_js.sh` (kiểm tra cú pháp 16 file JS, chạy thử công thức toán học và cập nhật `CODEBASE_MAP.md` trong **0.15 giây**, tốn **~150 token**).
   - Khi thực sự cần kiểm tra bố cục phức tạp bằng trình duyệt, bạn chỉ cần thêm cụm từ *"kiểm tra bằng browser"* vào cuối câu lệnh (AI sẽ chỉ kiểm tra trên Tiếng Việt `vi`, chụp 1 ảnh rồi đóng ngay).

5. **Đóng Bớt Các Tab File Lớn Không Dùng Đến Trên Editor:**
   - Antigravity tự động đính kèm metadata của các file đang mở (Active & Open Tabs) vào mỗi lượt chat. Khi đã sửa xong file nào, hãy đóng bớt tab của nó trên IDE.

6. **Chọn Mô Hình (Model Tier) Phù Hợp Với Độ Khó:**
   - **Flash / Medium Thinking:** Nhanh, tiết kiệm hạn ngạch, phù hợp cho **85% công việc hàng ngày** (sửa HTML/CSS, thêm từ điển `i18n.js`, nối biến DOM, sửa hàm nhỏ đã có sẵn công thức).
   - **Pro / High Thinking:** Chỉ bật khi thiết kế kiến trúc lớn (`PROJECT_BLUEPRINT.md`), phản biện (`/grill-me`, `/plan`) hoặc gỡ lỗi toán học đa biến phức tạp.

7. **Hạn Chế Dán Ảnh Chụp Màn Hình Khi Chỉ Sửa Chữ / Nhãn Hiển Thị:**
   - Mỗi tấm ảnh dán (`Cmd+V`) vào ô chat sẽ bị gửi lặp lại ở mọi câu hỏi tiếp theo trong phiên đó (~1.500 – 3.000 token × số lượt chat).
   - Nếu chỉ sửa câu chữ/số liệu: Hãy **copy dòng chữ đó dạng văn bản (text)** dán vào chat (tốn ~20 token và giúp AI định vị dòng code nhanh gấp 5 lần). Nếu bắt buộc phải dán ảnh để chỉ lỗi lệch khung, hãy bấm **`New Chat (+)`** ngay sau khi sửa xong bức ảnh đó.

8. **Không Đính Kèm (`@mention`) Cùng Lúc Nhiều Tài Liệu Nghiên Cứu Dài (`DOCS_*.md`):**
   - Trong các phiên lập trình hàng ngày, **chỉ cần đính kèm `@PROJECT_BLUEPRINT.md` và `@docs/CODEBASE_MAP.md`**. Chỉ chỉ định đọc các file `DOCS_*.md` (20–40 KB/file) khi thực sự cần tra cứu lại một quy định thuế/lương hưu chuyên biệt.

9. **Quy Tắc "Cấm Đọc Lại File Vừa Sửa" & "Cập Nhật Đa Ngôn Ngữ (`i18n.js`) Trong 1 Lượt":**
   - Khi `replace_file_content` đã thành công và `./verify_js.sh` báo `[OK]`, AI không gọi thêm `view_file` chỉ để "nhìn lại đoạn vừa sửa".
   - Nhờ `docs/CODEBASE_MAP.md` đã đánh chỉ mục chính xác dòng bắt đầu/kết thúc của cả 3 khối `vi`, `en`, `fr` trong `frontend/js/i18n.js`, AI sẽ chèn bản dịch cho cả 3 ngôn ngữ trong cùng 1 lượt.

10. **Tự Động Hóa 100% Việc Cập Nhật `docs/CODEBASE_MAP.md` (Tốn 0 Token):**
    - Bạn không bao giờ cần nhắc AI sửa file `docs/CODEBASE_MAP.md` bằng tay. Mọi thao tác quét lại số dòng mới đều được tích hợp tự động bên trong `./verify_js.sh` (chạy bằng Python hệ thống trong 0.05 giây, **tốn 0 token**).

11. **Kiểm Thử Kịch Bản UI Tĩnh Bằng Mock DOM Trong Node.js (0-Token UI Runner):**
    - Khi kiểm tra tương tác UI động (đổi quốc gia thì thẻ nào ẩn/hiện, chọn độc thân thì ẩn bạn đời, cưới thì hiện 2 cột song song), **tuyệt đối không bật browser để click từng nút**.
    - Tích hợp mock DOM tối giản (`document.getElementById`, `classList`, `style.display`) vào `./verify_js.sh` để chạy tự động hàng chục kịch bản giao diện (ví dụ: bộ 42 test cases) trong **0.25 giây**, phát hiện lỗi logic giao diện tức thì mà **tốn 0 token browser**.

12. **Kỷ Luật Quản Lý Versioning Toàn Diện (Asset, Schema, SemVer & Git Tagging):**
    - **Asset Cache-Busting (`?v=...`):** Mỗi khi sửa file JavaScript hoặc CSS, bắt buộc phải tăng query version parameter (`?v=YYYYMMDD_vNNN`) trong thẻ `<link>` và `<script>` của `index.html`. Tránh tuyệt đối tình trạng người dùng/tester mở web vẫn dính cache cũ và lầm tưởng code AI bị lỗi.
    - **Data Schema Versioning (`_schemaVersion`):** Mọi đối tượng lưu trữ (`localStorage`, JSON backup, SQLite) bắt buộc có số phiên bản dữ liệu (`_schemaVersion: 1, 2, 3...`). Khi nâng cấp app, luôn có pipeline chuyển đổi tuần tự (migration) để dữ liệu cũ không bao giờ bị hỏng hay mất.
    - **Semantic Release Versioning (`SemVer`):** Đánh số phiên bản phát hành (`vMAJOR.MINOR.PATCH`) hiển thị rõ trên UI và gắn Git tag để dễ dàng truy vết và rollback tức thì trong 1 giây nếu gặp sự cố.

13. **Quy Chuẩn "Vòng Lặp Khép Kín 4 Điểm" Chống Biến Nhập Liệu Ma (Anti-Orphan Input Protocol):**
    - **Tuyệt đối cấm tạo ô input trên UI chỉ để "cho đẹp" hoặc "để dành sau này":** Mọi ô nhập liệu (`<input>`, `<select>`, `<button>`, slider, checkbox) trên giao diện hoặc Modal bắt buộc phải đi trọn vẹn một vòng đời khép kín 4 điểm:
      1. *UI Element:* Có ID rõ ràng, có nhãn label và đa ngôn ngữ `data-i18n`.
      2. *Two-Way State Binding:* Có hàm nạp từ State ra UI (`input.value = plan.foo ?? default`) và sự kiện lưu từ UI vào State (`plan.foo = parse(input.value); savePlan()`).
      3. *Schema Contract:* Được khai báo chính thức trong `PROJECT_BLUEPRINT.md` và hàm di trú/bảo vệ `ensurePlanDefaults(plan)`.
      4. *Engine Consumption:* Phải được đọc và tham gia trực tiếp vào ít nhất 1 phép tính toán trong Core Engine (`engine.js`, `taxOptimizer.js`, `patrimoine.js`).
    - Nếu người dùng chỉnh một ô input mà kết quả đầu ra không hề thay đổi, đó là "Biến Ma" (Ghost/Orphan Input) làm xói mòn lòng tin của người dùng và gây rác ngữ cảnh mã nguồn.

---

## Phần II. Quy Trình Khép Kín Phát Triển Ứng Dụng Từ Con Số 0 Đến Khi Vận Hành Thực Tế (Giai Đoạn 0 ➔ Giai Đoạn 6)

Để một ứng dụng web vừa **kiến trúc sạch, không lỗi vặt, bảo mật cao & tuân thủ pháp lý**, vừa **tiết kiệm 70–85% token** trong suốt vòng đời phát triển, hãy đi theo đúng trình tự **từ Giai đoạn 0 đến Giai đoạn 6** dưới đây:

```mermaid
flowchart TD
    G0["Giai đoạn 0: Khởi Tạo Dự Án Mới, Bộ 5 File Xương Sống & Khóa Chính Sách Versioning (Day-0 Bootstrap)"] --> G1["Giai đoạn 1: Khai Phá Ý Tưởng, Phản Biện (/grill-me) & Phác Thảo Sơ Bộ"]
    G1 --> G2["Giai đoạn 2: Chốt Kiến Trúc, Đóng Băng Schema (PROJECT_BLUEPRINT.md) & Migration Pipeline"]
    G2 --> G3["Giai đoạn 3: Thiết Lập Quy Chuẩn UI/UX, Chia Nhỏ File & Mobile-First (.agents/rules/GEMINI.md)"]
    G3 --> G4["Giai đoạn 4: Bẻ Nhỏ Lộ Trình Thành Từng Task Độc Lập (docs/plans/*.md & /plan)"]
    G4 --> G5["Giai đoạn 5: Thi Công Cuốn Chiếu (Engine -> UI), Test ./verify_js.sh, Cache-Busting & Git Checkpoint"]
    G5 --> G6["Giai đoạn 6: Kiểm Duyệt Pháp Lý, Bảo Mật, SemVer Release, UI Version Badge & Deploy"]
```

---

### Giai Đoạn 0: Khởi Tạo Dự Án Mới — Bắt Đầu Bằng Một Platform / Framework Chuẩn Thay Vì Xây Từ Con Số 0 (Platform-First & Day-0 Bootstrap)

#### 0.1. Nguyên Tắc Sống Còn: Luôn Bắt Đầu Bằng Một Platform / Framework Chuẩn Thay Vì Viết Thuần Từ Con Số 0 (Platform-First vs Scratch)
- **Sai lầm kinh điển ("Bẫy Xây Từ Con Số 0" — Reinventing the Wheel):**
  - Khi dự án còn nhỏ (500 dòng code), viết bằng HTML/Vanilla JS thuần từ con số 0 có vẻ nhanh và đơn giản. Nhưng khi ứng dụng lớn lên thành **20.000 – 45.000 dòng code** (nhiều Tab, 12 hộp thoại Modal, đa ngôn ngữ, phân quyền, đồng bộ đám mây, hàng trăm biến trạng thái), việc không có một Platform chuẩn sẽ đẩy bạn vào cơn ác mộng:
    1. **Phình to file `index.html` lên 6.000+ dòng** vì HTML thuần không có cơ chế tách Component (`<AppHeader />`, `<TabProjections />`) tự nhiên.
    2. **Phải tự chế lại bánh xe (Reinventing State, Router & Reactivity):** Phải viết hàng nghìn dòng lệnh `document.getElementById(...).innerText = ...`, tự viết Event Bus, tự quản lý đóng/mở Modal, dễ dẫn đến lỗi quên cập nhật UI hoặc rò rỉ sự kiện.
    3. **Tốn gấp 3–5 lần Token khi làm việc với AI:** AI phải đọc cả file HTML/JS khổng lồ thay vì chỉ đọc đúng 1 file `.vue` / `.tsx` dài 80–200 dòng của component cần sửa.
- **Quy chuẩn bắt buộc cho mọi dự án mới — Khởi đầu ngay trên nền Platform hiện đại:**
  - **Frontend Platform:** Khởi tạo ngay bằng **Vue 3 + Vite + Pinia + Vue Router** (`npm create vite@latest` hoặc `npm create vue@latest`) hoặc **Next.js / Nuxt** ngay từ ngày đầu tiên (Day 0).
    - Có sẵn **Single-File Components (`.vue`)** giúp mỗi thẻ, mỗi Tab, mỗi Modal nằm gọn trong một file độc lập dưới 300 dòng.
    - Có sẵn **Pinia Reactive Store** tự động cập nhật giao diện ngay khi biến số thay đổi mà không cần viết hàm `getElementById` thủ công.
    - Có sẵn **Vite HMR & Code-Splitting** giúp phản hồi tức thì trên trình duyệt và đóng gói tối ưu khi lên production.
  - **Backend Platform:** Sử dụng **FastAPI** (kết hợp Pydantic validation, JWT Auth mẫu, SQLite/PostgreSQL migration chuẩn) hoặc **Supabase / PocketBase** nếu muốn có sẵn Auth + Database + Realtime ngay lập tức mà không phải viết lại từ đầu.
  - **Tách biệt rạch ròi giữa Platform UI và Core Domain Engine:** Dù dùng Vue/React làm Platform giao diện, toàn bộ công thức toán học/nghiệp vụ cốt lõi vẫn đặt trong các module thuần (`src/engine/*.js`) để chạy kiểm thử độc lập siêu tốc bằng Node.js (`./verify_js.sh`) mà không phụ thuộc DOM.

#### 0.2. Thiết Lập Bộ 5 File Hạ Tầng Chống Đốt Token Ngay Sau Khi Tạo Platform (Day-0 Bootstrap)
Sau khi khởi tạo khung Platform (ví dụ `frontend-vue/` + `backend/`), **tuyệt đối không bảo AI viết tính năng ngay**. Việc tiếp theo là thiết lập **Bộ 5 File Xương Sống Kèm Khóa Chính Sách Versioning Ngay Từ Ngày Đầu Tiên** để bảo vệ token và duy trì kỷ luật kiến trúc tự động:

| File hạ tầng | Vai trò bảo vệ Token & Kỷ luật Kiến trúc |
| :--- | :--- |
| **1. `.agents/rules/GEMINI.md`** | Khóa cứng quy tắc giao tiếp Tiếng Việt, kiến trúc tách 3 tầng chống file khổng lồ, quy chuẩn biến màu Dark/Light Mode, ngôn ngữ đại chúng, kỷ luật versioning và cấm tự ý bật `browser_subagent`. |
| **2. `PROJECT_BLUEPRINT.md`** | Bản thiết kế gốc chứa mục tiêu, những thứ cố tình không làm (Out-of-Scope), đơn vị chuẩn nội bộ, quy ước SemVer ứng dụng (`v1.0.0`) và **Bảng JSON Schema dữ liệu duy nhất** (khóa cứng `_schemaVersion: 1`). |
| **3. `docs/CODEBASE_MAP.md`** | **Bản đồ tọa độ dòng code (`StartLine` – `EndLine`) tự động 100%** của mọi hàm, thẻ HTML, phân mục CSS và khối từ điển. Giúp AI nhảy thẳng tới đúng 50–100 dòng cần sửa. |
| **4. `./verify_js.sh`** | **Công cụ kiểm thử & đồng bộ chỉ mục tự động (tốn 0 token cập nhật map, chạy 100% trong Sandbox):** Kiểm tra cú pháp toàn bộ file JS, chạy thử công thức toán học, quét rò rỉ API Key/từ vựng pháp lý, kiểm tra tính hợp lệ của schema version và tự động cập nhật `docs/CODEBASE_MAP.md` trong 0.15 giây. |
| **5. `.antigravityignore`, `CHANGELOG.md` & `deploy.sh`** | `.antigravityignore` chặn công cụ tìm kiếm quét vào file nhị phân SQLite (`*.db`), thư viện nén (`*.min.js`), cache; `CHANGELOG.md` theo dõi lịch sử phiên bản phát hành; `deploy.sh` đẩy code lên VPS an toàn và tự động sao lưu database. |

- **Câu lệnh Khởi Tạo Dự Án Mới Trên Nền Platform Chuẩn (Day-0 Platform Bootstrap Prompt — Copy & Paste):**
  ```text
  Tôi bắt đầu một dự án mới tên là [Tên Dự Án].
  Mục tiêu cốt lõi của ứng dụng: [Mô tả ngắn gọn 3-5 câu về bài toán cần giải quyết và đối tượng người dùng].
  Platform bắt buộc (không xây thủ công từ con số 0):
  - Frontend: Vue 3 (<script setup>) + Vite + Pinia + Vue Router (hoặc Next.js/React).
  - Backend: FastAPI + SQLite/PostgreSQL.

  Khoan viết tính năng chi tiết. Hãy khởi tạo khung Platform chuẩn và Bộ 5 File Xương Sống sau đây:
  1. Khởi tạo cấu trúc thư mục Vue 3 + Vite (src/components/, src/views/, src/stores/, src/engine/, src/assets/css/) để mỗi thành phần giao diện là một Single-File Component (.vue) nhỏ gọn dưới 300 dòng, tuyệt đối không dồn thành 1 file index.html khổng lồ.
  2. .agents/rules/GEMINI.md: Khóa cứng quy tắc giao tiếp Tiếng Việt, kiến trúc tách 3 tầng (Tầng 1 Core Engine thuần JS trong src/engine/ độc lập DOM, Tầng 2 Pinia Store & State Sync trong src/stores/, Tầng 3 Vue SFC Components theo từng Tab), hỗ trợ Dark/Light Mode bằng biến CSS, cấm tự ý bật browser_subagent.
  3. PROJECT_BLUEPRINT.md: Định nghĩa mục tiêu, những thứ cố tình không làm (Out-of-Scope), đơn vị chuẩn nội bộ, chính sách SemVer (v1.0.0) và Bảng JSON Schema dữ liệu duy nhất (kèm trường _schemaVersion: 1).
  4. CHANGELOG.md & .antigravityignore: Chặn các thư mục/file nặng (*.db, *.min.js, node_modules/, dist/, __pycache__, .git, data/).
  5. verify_js.sh (chmod +x): Script chạy 100% trong Sandbox giúp (a) kiểm tra cú pháp toàn bộ file code, (b) tự động quét vị trí dòng code của mọi Vue Component, Pinia Store, Engine JS & CSS để sinh ra docs/CODEBASE_MAP.md tốn 0 token, (c) quét rò rỉ API Key/Secret và từ vựng pháp lý.
  6. deploy.sh: Script tự động chạy test, build gói production (vite build) và rsync đẩy code lên Server VPS an toàn (tự động backup database trên server trước khi restart).
  ```

---

### Giai Đoạn 1: Khai Phá Ý Tưởng, Phản Biện Nghiệp Vụ (`/grill-me`) & Xem Sơ Bộ Giao Diện (Chưa Sửa Code Chính)

Khi bạn vừa nảy ra một ý tưởng mới hoặc một phân hệ lớn, bạn có thể gõ lệnh **`/grill-me`** để AI hỏi ngược lại các trường hợp biên, sau đó dùng **1 trong 3 cấp độ Xem Sơ Bộ Giao Diện (Visual Prototyping)** dưới đây để nhìn thấy ngay hình hài tính năng mà **không làm xáo trộn hay tốn token đọc các file lớn của dự án**:

#### Cấp độ 1 — Phác Thảo Khung Bố Cục Ngay Trong Chat (ASCII Wireframe — Tốn ~300 Token, Nhanh 3 Giây)
- **Khi nào dùng:** Khi bạn mới có ý tưởng sơ khởi, muốn hình dung nhanh có mấy cột, gồm những ô nhập nào và kết quả gì để phát hiện ngay thông tin còn thiếu.
- **Câu lệnh Prompt ví dụ (Copy & Paste):**
  ```text
  Tôi muốn thêm tính năng [Ví dụ: So sánh Thuế Thừa Kế Pháp - Việt cho BĐS và Danh mục cổ phiếu].
  Tuyệt đối khoan sửa code dự án. Hãy làm 2 việc:
  1. Vẽ sơ đồ khung bố cục giao diện bằng ASCII Wireframe (chia rõ Cột Trái: các ô nhập liệu, Cột Phải: các thẻ kết quả & biểu đồ).
  2. Chỉ ra 5 thông số hoặc trường hợp thực tế mà người dùng hay quên nhưng rất quan trọng để tôi bổ sung vào giao diện.
  ```
- **Kết quả AI trả về ngay trong chat (~300 token):**
  ```text
  +-------------------------------------------------------------------------+
  | [Tiêu đề Thẻ: Lưới An Toàn Y Tế Pháp - Việt]          [Trạng thái: Đạt] |
  +------------------------------------+------------------------------------+
  | CỘT TRÁI: THÔNG SỐ ĐẦU VÀO         | CỘT PHẢI: KẾT QUẢ DỰ PHÓNG         |
  | - Nơi nghỉ hưu: [Pháp / Việt Nam]  | - Chi phí y tế tự trả: 1.200 €/năm |
  | - Bảo hiểm CFE: [x] Có tham gia    | - Tỷ lệ bảo vệ:        92%         |
  | - Quỹ dự phòng: [ 30.000 € ]       | [Thanh mức độ an toàn: ████████░░] |
  +------------------------------------+------------------------------------+
  ```
- **Câu lệnh Prompt chỉnh sửa tiếp theo (nếu thấy thiếu):**
  ```text
  Khung này dễ hình dung rồi. Hãy sửa lại khung ASCII một chút:
  1. Cột trái thêm ô nhập "Số người con nhận thừa kế" và "Độ tuổi trao tặng (trước hay sau 70 tuổi)".
  2. Cột phải thêm dòng hiển thị "Số tiền thuế tiết kiệm được nếu tặng trước 70 tuổi".
  Vẽ lại khung ASCII đã chốt để chuẩn bị đưa vào kế hoạch.
  ```

#### Cấp độ 2 — Tạo 1 File Nháp Giao Diện Độc Lập (`frontend/preview.html` — Tốn ~1.500 Token, Đẹp Giống Thật 100%)
- **Khi nào dùng:** Khi bạn muốn **nhìn màu sắc thật, thẻ Card thật, font chữ thật và bấm thử trên trình duyệt** ở cả Dark Mode & Light Mode mà không chạm vào các file lớn của dự án.
- **Câu lệnh Prompt — Bước 1: Tạo bản nháp (Copy & Paste):**
  ```text
  Tôi muốn xem trước giao diện thực tế của tính năng [Tên tính năng] để dễ hình dung những điều còn thiếu.
  Tuyệt đối KHÔNG đọc hay sửa index.html, ui.js hay i18n.js lúc này.
  Hãy tạo duy nhất 1 file nháp độc lập tại frontend/preview.html:
  1. Nhúng sẵn <link rel="stylesheet" href="css/styles.css"> của dự án và có nút bấm chuyển đổi Dark/Light Mode ở góc trên.
  2. Dựng đầy đủ bố cục thẻ Card, các ô nhập, bảng kết quả và điền sẵn các con số giả lập mẫu (hardcode số mẫu hợp lý).
  3. Không gọi browser_subagent — tôi sẽ tự mở http://localhost:8000/preview.html trên trình duyệt của tôi để xem.
  ```
- **Câu lệnh Prompt — Bước 2: Tinh chỉnh trên bản nháp (sau khi xem trên trình duyệt):**
  ```text
  Tôi đã xem localhost:8000/preview.html, nhìn rất rõ ràng! Hãy sửa nhanh trong file frontend/preview.html 3 điểm sau:
  1. Chuyển 2 ô nhập [A] và [B] lên cùng 1 hàng ngang cho gọn.
  2. Thêm 1 hộp giải thích công thức tính ở cuối cột phải.
  3. Đổi màu viền thẻ kết quả sang màu xanh ngọc (emerald).
  ```
- **Câu lệnh Prompt — Bước 3: Chốt & Lập kế hoạch ghép vào dự án chính:**
  ```text
  Giao diện trong frontend/preview.html đã hoàn hảo 100% đúng ý tôi rồi!
  Bây giờ hãy dựa trên giao diện chuẩn của frontend/preview.html, @PROJECT_BLUEPRINT.md và @docs/CODEBASE_MAP.md để:
  1. Lập kế hoạch ghép tính năng này vào dự án chính trong file docs/plans/[ten_tinh_nang].md (chia Task: viết hàm tính trong engine.js trước -> ghép HTML/JS vào Tab thật -> thêm từ điển i18n.js).
  2. Sau khi ghép xong ở bước thực thi thì xóa file nháp frontend/preview.html.
  ```

#### Cấp độ 3 — Dựng Khung HTML Tĩnh Trên Trang Chính Trước, Khoan Viết Logic & Đa Ngôn Ngữ (UI Skeleton First)
- **Khi nào dùng:** Khi bạn muốn đặt thử thẻ mới nằm ngay bên trong Tab thật của ứng dụng (`index.html`) để xem nó đứng cạnh các thẻ hiện có trông có cân đối không.
- **Câu lệnh Prompt — Bước A: Chỉ dựng khung HTML tĩnh (Copy & Paste):**
  ```text
  Tra cứu @docs/CODEBASE_MAP.md để tìm vị trí cuối Tab 2 (#tab-estate) trong frontend/index.html.
  Hãy chèn thử khung HTML tĩnh (kèm số liệu mẫu bằng Tiếng Việt) cho thẻ [Tên thẻ mới] vào đúng vị trí đó để tôi F5 trình duyệt ngắm bố cục tổng thể.
  Lưu ý bắt buộc để tiết kiệm token:
  - Khoan viết hàm tính toán trong engine.js.
  - Khoan viết sự kiện DOM trong ui-tab2-health.js.
  - Khoan thêm bản dịch tiếng Anh/Pháp vào i18n.js.
  - Không gọi browser_subagent.
  ```
- **Câu lệnh Prompt — Bước B: Nối công thức & hoàn thiện 1 lần duy nhất (sau khi F5 thấy ưng mắt):**
  ```text
  Tôi đã F5 xem khung HTML trên trang chính, bố cục rất đẹp rồi!
  Bây giờ hãy hoàn thiện trọn gói tính năng cho khung HTML vừa tạo:
  1. Viết hàm tính toán vào frontend/js/engine.js và kiểm chứng bằng ./verify_js.sh.
  2. Nối sự kiện input và hiển thị kết quả trong frontend/js/ui-tab2-health.js.
  3. Bổ sung đầy đủ từ điển vi / en / fr vào frontend/js/i18n.js trong 1 lượt.
  ```

---

### Giai Đoạn 2: Thiết Kế Kiến Trúc, Đóng Băng Schema (`PROJECT_BLUEPRINT.md`) & Bảo Toàn Dữ Liệu Cũ (Schema Migration)

90% lỗi đập đi xây lại (tốn hàng triệu token) xuất phát từ việc **vừa viết giao diện vừa tự bịa tên biến**, hoặc **khi nâng cấp tính năng mới (`v2`) làm hỏng cấu trúc dữ liệu cũ (`v1`) của người dùng đang lưu trong `localStorage` / `SQLite`**.

#### 1. Bốn Trụ Cột Bất Biến Trong `PROJECT_BLUEPRINT.md`
1. **Nguyên tắc Kiến trúc:** Ví dụ Local-First (100% tính toán ở trình duyệt, offline-ready) kết hợp FastAPI + SQLite đồng bộ đám mây.
2. **Chuẩn hóa Đơn vị Nội bộ (Internal Canonical Units):** Mọi số tiền lưu trong bộ nhớ đều quy về `EUR/năm` (hoặc `USD` cho kịch bản Mỹ), tỷ lệ phần trăm lưu thống nhất (`4.0` nghĩa là `4%`). Chỉ khi hiển thị ra màn hình mới nhân tỷ giá.
3. **Bảng Schema Dữ Liệu Duy Nhất (Single Source of Truth JSON Schema):** Liệt kê đầy đủ tên trường (`camelCase`), kiểu dữ liệu, giá trị mặc định của toàn bộ đối tượng dữ liệu (User, Plan, Asset, Health...).
4. **Hợp Đồng Toàn Diện Vòng Đời Biến (Full-Lifecycle Variable Contract — Chống Biến Ma / Biến Rác):** Mọi trường dữ liệu đưa vào Schema bắt buộc phải xác định rõ 3 điểm neo trước khi viết code:
   - *UI Element:* Ô nhập/select nào trên UI hoặc Modal sẽ cho người dùng chỉnh biến này?
   - *State Binding:* Hàm nào trong `state.js` sẽ nạp/lưu và cấp default value an toàn trong `ensurePlanDefaults()`?
   - *Engine Calculation:* Hàm nào trong Tầng 1 (`engine.js`, `taxOptimizer.js`, `patrimoine.js`...) sẽ đọc biến này và nó trực tiếp làm thay đổi kết quả gì?
   - *Quy tắc thép:* Tuyệt đối cấm khai báo biến vào Schema chỉ để "dự phòng" mà không có bất kỳ dòng code tính toán nào trong Engine tiêu thụ biến đó.

#### 2. Chiến Lược Quản Lý Versioning Dữ Liệu & Đường Ống Di Trú Tuần Tự (Zero-Data-Loss Schema Versioning & Sequential Migration Pipeline)

Một trong những thảm họa lớn nhất khi phát triển app là **nâng cấp tính năng mới (`v2`, `v3`) làm vỡ nát dữ liệu cũ của người dùng** đang lưu trong `localStorage` hoặc cơ sở dữ liệu. Để đảm bảo ứng dụng đạt chuẩn thương mại bền vững qua nhiều năm tháng, hãy áp dụng quy chuẩn Versioning Dữ Liệu 4 lớp sau:

1. **Định danh phiên bản dữ liệu bằng trường bắt buộc `_schemaVersion`:**
   - Mọi đối tượng lưu trữ (`Plan`, `Patrimoine`, `Settings`) khi lưu vào `localStorage`, JSON export/backup hay SQLite đều bắt buộc phải có thuộc tính `_schemaVersion: 1`, `2`, `3`...
   - Đây là "chứng minh thư" của gói dữ liệu, giúp code biết chính xác cấu trúc dữ liệu đang ở thế hệ nào.

2. **Đường ống di trú tuần tự theo bậc thang (`Sequential Migration Chain`):**
   - **Tuyệt đối KHÔNG viết rẽ nhánh nhảy cóc** (`if (v === 1) {...} else if (v === 2) {...}`), vì khi app lên `v5`, `v10` sẽ sinh ra hàng chục nhánh rẽ hỗn loạn, dễ bỏ sót biến.
   - **Bắt buộc dùng chuỗi nâng cấp tuần tự theo từng nấc thang:**
     ```javascript
     function migratePlan(rawPlan) {
       let plan = { ...rawPlan };
       let v = plan._schemaVersion || 1;
       
       // Bước 1: Nâng từ v1 lên v2 (Ví dụ: Thêm quốc gia làm việc & Hôn nhân)
       if (v < 2) {
         plan.workCountry = plan.workCountry || 'FR';
         plan.maritalStatus = plan.maritalStatus || 'single';
         plan.taxParts = (plan.maritalStatus === 'married' ? 2.0 : 1.0);
         v = 2;
       }
       // Bước 2: Nâng từ v2 lên v3 (Ví dụ: Thêm Lương hưu Đức & BHXH VN cho 2 người)
       if (v < 3) {
         plan.germanPensionDetails = plan.germanPensionDetails || {
           spouse1: { grossAnnualSalary: 45000, yearsContributed: 35, claimAge: 67 },
           spouse2: { grossAnnualSalary: 38000, yearsContributed: 35, claimAge: 67 }
         };
         v = 3;
       }
       plan._schemaVersion = v;
       return ensurePlanDefaults(plan); // Bù đắp an toàn các giá trị biên
     }
     ```
   - **Lợi ích vàng:** Dù người dùng không mở app suốt 2 năm hoặc nhập lại file backup từ ngày đầu tiên (`v1`), hệ thống vẫn tự động chạy tuần tự `v1 ➔ v2 ➔ v3`, nâng cấp trơn tru lên bản mới nhất mà **không mất 1 byte dữ liệu nào**!

3. **Tương thích ngược & xuôi với File Sao Lưu Dự Phòng (`Backup & Restore Compatibility`):**
   - Khi xuất file sao lưu JSON (`export.js`): Bắt buộc đính kèm `_schemaVersion: N` và `appVersion: "x.y.z"`.
   - Khi người dùng bấm *"Nhập dữ liệu dự phòng"* (Import Restore): Đọc `_schemaVersion` của file tải lên, chạy qua pipeline `migratePlan()` để chuẩn hóa trước khi ghi đè vào `state.js`. Không bao giờ quăng lỗi `undefined` hay làm đơ giao diện.

4. **Quản trị phiên bản SQLite Backend bằng `PRAGMA user_version` (Safe Migration):**
   - SQLite có sẵn thanh ghi nội bộ siêu nhẹ: `PRAGMA user_version`.
   - Khi Backend khởi động (`backend/database.py`), kiểm tra phiên bản hiện tại. Nếu `current_version < TARGET_DB_VERSION`:
     - Chạy tuần tự các câu lệnh `ALTER TABLE ... ADD COLUMN ... DEFAULT ...` an toàn.
     - Nâng số `PRAGMA user_version = TARGET_DB_VERSION`.
     - **Tuyệt đối CẤM dùng `DROP TABLE` trên môi trường thật**.

---

#### 3. Các Câu Lệnh Prompt Hiệu Quả Ở Giai Đoạn 2 (Copy & Paste)

- **Tình huống 2A — Khi khởi tạo dự án mới (Tạo mới `PROJECT_BLUEPRINT.md` kèm Schema Version 1):**
  ```text
  Dựa trên ý tưởng và khung giao diện sơ bộ vừa thống nhất ở Giai đoạn 1, hãy tạo file PROJECT_BLUEPRINT.md làm nguồn chân lý duy nhất (Single Source of Truth) cho dự án.
  Tuyệt đối KHOAN viết code tính năng lúc này. Hãy thiết kế đầy đủ 4 phần sau trong PROJECT_BLUEPRINT.md:
  1. Nguyên tắc Kiến trúc & Phạm vi: Xác định rõ kiến trúc (ví dụ: Local-First 100% tính toán ở client + FastAPI/SQLite đồng bộ), chính sách Semantic Versioning ứng dụng (SemVer v1.0.0), và liệt kê rõ những thứ cố tình KHÔNG làm (Out-of-Scope) để tránh phình dự án.
  2. Đơn vị Chuẩn Nội Bộ (Internal Canonical Units): Quy định thống nhất đơn vị lưu trữ trong bộ nhớ (ví dụ: tiền tệ luôn quy về EUR/năm, tỷ lệ % lưu dạng số thực 4.0 hay 0.04, ngày tháng theo chuẩn ISO) — chỉ khi hiển thị ra UI mới đổi tỷ giá/đơn vị.
  3. Bảng JSON Schema Dữ Liệu Đóng Băng: Liệt kê chính xác tên biến (camelCase), kiểu dữ liệu, giá trị mặc định (default) và giới hạn min/max của mọi đối tượng dữ liệu, bắt buộc khóa cứng trường _schemaVersion: 1.
  4. Sơ đồ Luồng Dữ Liệu (Data Flow): Mô tả ngắn gọn dữ liệu đi từ Ô nhập UI -> State (localStorage) -> Core Engine -> Render Biểu đồ/Bảng như thế nào.
  ```

- **Tình huống 2B — Khi thêm tính năng mới vào dự án đang chạy (Nâng cấp Schema Version & Viết Migration Pipeline):**
  ```text
  Tôi chuẩn bị thêm tính năng [Tên tính năng mới, ví dụ: Mô phỏng Thuế Thừa Kế / Bảo hiểm nhân thọ / Mở rộng PPP Đa quốc gia].
  Khoan sửa code giao diện. Hãy đọc @PROJECT_BLUEPRINT.md hiện tại và thực hiện:
  1. Đề xuất các trường dữ liệu mới cần thêm vào Schema (tên biến tiếng Anh chuẩn camelCase, kiểu dữ liệu, đơn vị tính, giá trị mặc định an toàn) và kiểm tra không trùng lặp tên biến cũ.
  2. Cập nhật trực tiếp các trường mới vào @PROJECT_BLUEPRINT.md và tăng _schemaVersion từ [N] lên [N+1].
  3. Thiết kế pipeline nâng cấp tuần tự trong state.js: viết hàm di trú if (v < N+1) để tự động bù đắp giá trị mặc định an toàn cho người dùng cũ hoặc khi người dùng import file JSON backup từ phiên bản trước.
  4. Nếu cần lưu thêm trên SQLite: đề xuất câu lệnh ALTER TABLE ADD COLUMN an toàn kèm DEFAULT, tuyệt đối không DROP TABLE.
  ```

---

### Giai Đoạn 3: Thiết Lập Quy Chuẩn Chia Nhỏ File, UI/UX & Tương Thích Điện Thoại (`.agents/rules/GEMINI.md`)

Trước khi bắt tay vào viết code hoặc khi mở rộng phân hệ mới, hãy khóa các quy tắc thiết kế trong `.agents/rules/GEMINI.md` để AI tự động tuân thủ ở mọi phiên chat:

#### 1. Quy Tắc Chống File Khổng Lồ (Anti-Monolith Rule — Kiến Trúc 3 Tầng)
Không bao giờ gom toàn bộ code vào 1 file `ui.js` hay `styles.css` dài gần 9.000 dòng. Mỗi file không vượt quá **800 – 2.200 dòng**, tách bạch thành 3 tầng rõ rệt:
- **Tầng 1 — Core Engine (Logic & Toán học thuần túy):** Chỉ nhận vào JSON và trả ra JSON (`engine.js`, `taxOptimizer.js`, `monteCarlo.js`, `patrimoine.js`, `scenarios.js`). Tuyệt đối không chứa `document.getElementById` để có thể kiểm thử tự động trong 0.1 giây bằng terminal!
- **Tầng 2 — State, Sync & I18n (`state.js`, `i18n.js`, `auth.js`, `geminiAdvisor.js`, `export.js`):** Quản lý dữ liệu `localStorage`, đồng bộ API, kết nối AI và từ điển đa ngôn ngữ.
- **Tầng 3 — Giao diện tách theo từng Tab độc lập (`ui.js`, `ui-tab1-charts.js`, `ui-tab1-streams.js`, `ui-tab2-health.js`, `ui-tab3-taxes.js`, `ui-modals.js`, `community.js`):** Khi sửa Tab nào chỉ cần mở đúng file của Tab đó, tiết kiệm 90% token đọc file!

#### 2. Quy Chuẩn Hệ Thống Thiết Kế (Design System & Plain Language)
- **Dark Mode & Light Mode chuẩn WCAG AA:** Khai báo 100% bảng biến màu CSS (`--bg-app`, `--bg-card`, `--text-main`, `--text-muted`, `--border-subtle`). Cấm hardcode nền tối `rgba(0,0,0,...)` hay màu chữ xám nhạt cố định.
- **Đồng nhất Typography (`--font-sans`):** Không dùng font `monospace` cho văn bản đa ngôn ngữ hay công thức giải thích; tách riêng con số và đơn vị đo lường.
- **Ngôn ngữ đại chúng:** Dễ hiểu cho 100.000+ người dùng phổ thông, không dùng thuật ngữ hàn lâm và cấm dùng cú pháp LaTeX.

#### 3. Quy Chuẩn "Bất Tử Hóa Giao Diện Khi Mạng Yếu & Tương Thích Điện Thoại 100%" (Resilience & Mobile-First)
70% người dùng cuối mở ứng dụng trên điện thoại hoặc mạng 4G chập chờn. Mọi tính năng UI đều phải thỏa mãn 3 tiêu chuẩn Defensive UI:
1. **Chống treo đơ khi gọi API/AI bên thứ ba (Timeout & Graceful Fallback):** Mọi hàm `fetch()` phải có `AbortController` giới hạn thời gian chờ (15–20 giây) và khối `try / catch / finally` để luôn tắt vòng quay loading, hiện thông báo thân thiện kèm nút *"Thử lại"*.
2. **Chống vỡ khung trên màn hình điện thoại (`375px` Viewport Rule):** Mọi lưới nhiều cột (`grid-template-columns`) phải tự thu về 1 cột dọc ở màn hình dưới `768px`; bảng nhiều cột bọc trong `overflow-x: auto`; dùng `max-width: 600px; width: 100%` thay vì chiều rộng cố định.
3. **Bảo vệ ô nhập số liệu trước dữ liệu lạ (Input Sanitization & Clamping):** Luôn bọc `Number.isFinite(val) ? val : defaultVal` và giới hạn `Math.max(min, Math.min(max, val))` để người dùng để trống ô hoặc gõ số âm vô lý cũng không bao giờ sinh ra `NaN` hay `Infinity`.

#### 4. Khử Ràng Buộc Chéo Giữa Các Tab UI (Cross-Tab Decoupling & Central State)
Khi chia nhỏ giao diện thành các module Tab độc lập (`ui-tab1-streams.js`, `ui-tab2-health.js`, `ui-tab3-taxes.js`, `ui-modals.js`), nếu các Tab gọi trực tiếp biến hoặc hàm nội bộ của nhau sẽ dẫn đến "Spaghetti Code" và lỗi vỡ trang (`ReferenceError`) khi thứ tự tải script trong HTML thay đổi:
- **Giao tiếp qua Single Source of Truth:** Mọi Tab con chỉ đọc trạng thái kế hoạch từ `getActivePlan()` trong Tầng 2 (`state.js`).
- **Nhạc trưởng điều phối (`ui.js`):** Khi một Tab làm thay đổi dữ liệu (ví dụ: đổi quốc gia làm việc, đổi tình trạng hôn nhân từ Cá nhân sang Vợ chồng), Tab đó chỉ ghi dữ liệu vào `plan` và gọi hàm điều phối trung tâm của `ui.js` (hoặc Event Bus) để re-render đồng bộ toàn bộ các Tab liên quan, tuyệt đối không truy cập trực tiếp biến cục bộ của Tab khác.

#### 5. Quy Hoạch Tham Số Địa Phương Tập Trung (Localized Profile Configuration)
Mọi thông số mang tính địa phương (chi phí sinh hoạt PPP, chi phí y tế theo độ tuổi `healthCostBase`, chính sách hỗ trợ gia đình/CAF, biểu thuế lũy tiến) rất dễ bị hardcode rải rác nếu không có quy hoạch từ đầu:
- **Bảng Hằng Số Tập Trung:** Toàn bộ dữ liệu quốc gia phải được quy hoạch trong một cấu hình duy nhất (ví dụ: `COUNTRY_PPP_PROFILES` trong `taxOptimizer.js`).
- **Tra cứu nhất quán:** Mọi module UI (Tab 1 dòng tiền, Tab 2 sức khỏe, Tab 3 thuế) và Engine chỉ việc tra cứu theo `plan.workCountry` hoặc `plan.retireCityKey`, đảm bảo thay đổi hệ số ở một nơi là toàn bộ ứng dụng tự động phản ánh chính xác.

#### 6. Nguyên Tắc Kỹ Thuật Trung Thực (Anti-Hallucination & Honest Fallback Principle)
Khi ứng dụng mở rộng ra phạm vi quốc tế hoặc nhiều nghiệp vụ phức tạp, AI hoặc lập trình viên rất dễ mắc bẫy **"tự bịa công thức chung/generic phỏng đoán"** (ví dụ: lấy bừa 50% lương làm lương hưu cho mọi nước chưa có luật tự động):
- **Tuyệt đối không đoán mò số liệu tài chính:** Trong ứng dụng tài chính cá nhân, y tế hay pháp lý, việc đoán mò sẽ làm sai lệch hoàn toàn kế hoạch cả đời của người dùng.
- **Khối thông báo minh bạch (`#callout-...-unsupported`):** Khi người dùng chọn quốc gia chưa được lập trình mô hình hưu trí tự động, hệ thống ẩn toàn bộ các thẻ tự động và hiển thị một thông báo trang nhã, minh bạch: giải thích rõ hệ thống chưa hỗ trợ mô hình tự động cho nước này, và hướng dẫn người dùng tự ước tính độc lập rồi thêm qua nút `[+ Thêm Thu Nhập]`.

#### 7. Các Câu Lệnh Prompt Hiệu Quả Ở Giai Đoạn 3 (Copy & Paste)

- **Tình huống 3A — Khi thiết lập quy chuẩn cho dự án mới (Tạo `.agents/rules/GEMINI.md`):**
  ```text
  Dựa trên @PROJECT_BLUEPRINT.md, hãy tạo file quy tắc hệ thống tại .agents/rules/GEMINI.md để khóa cứng kỷ luật kỹ thuật và UI/UX cho toàn bộ dự án:
  1. Kiến trúc 3 Tầng Chống File Khổng Lồ (Anti-Monolith):
     - Tầng 1 (Core Engine): Hàm thuần túy (pure functions) chỉ nhận/trả JSON, tuyệt đối cấm gọi DOM (document.getElementById) để test được bằng dòng lệnh trong 0.1 giây.
     - Tầng 2 (State & I18n): Quản lý localStorage, đồng bộ API, hàm migrateState() bảo vệ dữ liệu cũ và từ điển đa ngôn ngữ.
     - Tầng 3 (UI tách theo từng Tab): Mỗi Tab giao diện nằm ở 1 file JS riêng biệt (tối đa 1.500 dòng/file), ui.js chỉ làm nhạc trưởng điều phối.
  2. Quy chuẩn UI/UX, Mobile-First & Resilience:
     - Hỗ trợ song song Dark Mode & Light Mode bằng 100% biến CSS (--bg-app, --bg-card, --text-main, --text-muted, --border-subtle). Cấm hardcode màu nền tối rgba(0,0,0,...) hay màu chữ xám nhạt cố định.
     - Dùng 100% font giao diện chính (--font-sans) cho văn bản và công thức giải thích; ngôn ngữ đại chúng, cấm dùng LaTeX.
     - Tương thích màn hình điện thoại 375px, bọc kiểm tra NaN/Infinity cho mọi ô input và có timeout khi gọi API.
  3. Kỷ luật Bảo vệ Token & Pháp lý:
     - Cấm tự ý bật browser_subagent nếu người dùng không yêu cầu rõ; ưu tiên kiểm thử bằng ./verify_js.sh.
     - Cấm đọc lại file ngay sau khi vừa replace_file_content thành công.
     - Luôn bọc escapeHtml() cho dữ liệu người dùng nhập và tuân thủ miễn trừ trách nhiệm pháp lý.
  ```

- **Tình huống 3B — Khi dự án mở rộng hoặc cần siết lại quy chuẩn UI/Module (Cập nhật `.agents/rules/GEMINI.md`):**
  ```text
  Tôi thấy file [Tên file, ví dụ: frontend/js/ui-tab3-taxes.js hoặc styles.css] đang bắt đầu dài ra, hoặc chuẩn bị có thêm phân hệ giao diện mới [Tên phân hệ].
  Hãy đọc @.agents/rules/GEMINI.md và @docs/CODEBASE_MAP.md để:
  1. Quy hoạch rõ trách nhiệm của các file module hiện tại trong .agents/rules/GEMINI.md: hàm nào thuộc Engine (Tầng 1), hàm nào thuộc State (Tầng 2), hàm render nào thuộc file UI Tab nào (Tầng 3).
  2. Bổ sung quy tắc kiểm soát cụ thể cho tính năng mới (quy chuẩn màu sắc Light/Dark Mode, chống vỡ khung Mobile 375px, và quy tắc đa ngôn ngữ i18n) vào .agents/rules/GEMINI.md để các phiên chat thi công sau cứ thế tuân theo 100%.
  ```

- **💡 Mẹo Kết Hợp "Gộp Giai Đoạn 2 + 3 Trong 1 Lượt" (Tiết Kiệm Token Nhất — Copy & Paste):**
  ```text
  Ý tưởng và bố cục ở Giai đoạn 1 đã chốt. Bây giờ hãy thực hiện đồng thời Giai đoạn 2 và Giai đoạn 3 (khoan viết code tính năng):
  1. Cập nhật @PROJECT_BLUEPRINT.md: Khai báo đầy đủ JSON Schema dữ liệu mới (tên trường camelCase, kiểu dữ liệu, đơn vị chuẩn nội bộ, giá trị mặc định an toàn cho dữ liệu cũ).
  2. Cập nhật @.agents/rules/GEMINI.md: Phân bổ rõ các hàm dự kiến sẽ nằm ở file nào theo đúng kiến trúc 3 tầng (Engine / State / UI từng Tab) để không làm phình file, và khóa quy chuẩn hiển thị Dark/Light Mode cho phân hệ này.
  ```

---

### Giai Đoạn 4: Lập Kế Hoạch Thực Thi Chia Nhỏ Theo Từng Task (`docs/plans/*.md` & `/plan`)

Khi đã có `PROJECT_BLUEPRINT.md` và `.agents/rules/GEMINI.md`, hãy mở một phiên chat (có thể kết hợp lệnh **`/plan`**) để lập danh sách công việc cụ thể cho tính năng sắp làm:

- **Câu lệnh Prompt mẫu Giai đoạn 4 (Copy & Paste):**
  ```text
  Dựa trên @PROJECT_BLUEPRINT.md và @docs/CODEBASE_MAP.md, hãy lập kế hoạch triển khai chi tiết vào file docs/plans/[ten_ke_hoach].md.
  Yêu cầu:
  1. Chia thành các Task nhỏ độc lập theo đúng thứ tự: (Task 1) Core Engine & Schema Migration -> (Task 2) Giao diện HTML/CSS & DOM -> (Task 3) Đa ngôn ngữ i18n.js. Mỗi Task chỉ sửa tối đa 2-3 file để thực hiện trọn vẹn trong 1 phiên chat.
  2. Với mỗi Task, ghi rõ: File cần sửa, tọa độ dòng code dự kiến, công thức/logic đầu vào - đầu ra, và biểu thức kiểm thử bằng ./verify_js.sh.
  3. Tuyệt đối chưa viết code ở bước này.
  ```
- Sau khi AI xuất file `docs/plans/[ten_ke_hoach].md`, bạn có thể đọc lướt và chỉnh sửa trực tiếp trên file Markdown nếu muốn đổi thông số (tốn **0 token**).

---

### Giai Đoạn 5: Thi Công Cuốn Chiếu ("Engine Trước – Giao Diện Sau"), Kiểm Thử Toán Học & Gỡ Lỗi Thông Minh

Đây là giai đoạn viết code thực tế. Hãy luôn tuân thủ quy trình **"Xây Lõi Tính Toán trước ➔ Kiểm thử đúng 100% số học ➔ Nối vào Giao diện HTML/DOM sau ➔ Đóng dấu Git Checkpoint"**.

#### 1. Quy Trình Chạy Từng Task & Đóng Dấu An Toàn (`Git Checkpoints`)
1. **Bấm `New Chat (+)`** để bắt đầu với bộ nhớ trống 100%.
2. **Chạy từng Task một** bằng câu lệnh ngắn gọn (Copy & Paste):
   ```text
   Đọc @docs/plans/[ten_ke_hoach].md và @docs/CODEBASE_MAP.md.
   Hãy thực thi duy nhất Task 1.
   Chỉ đọc đúng khoảng dòng đã ghi, sửa bằng replace_file_content, chạy ./verify_js.sh để kiểm chứng toán học và tự động cập nhật CODEBASE_MAP, đánh dấu [x] vào Task 1 rồi dừng lại.
   ```
3. **Đóng dấu Git Checkpoint ngay sau mỗi Task hoàn chỉnh:**
   - Ngay khi `./verify_js.sh` báo `[OK]`, hãy lưu điểm an toàn để bất cứ lúc nào thử nghiệm tiếp theo không ưng ý cũng có thể quay lại trong 1 giây:
     ```bash
     git add -A && git commit -m "checkpoint: hoan thanh [ten_task]"
     ```

#### 2. Quy Trình Kiểm Tra Tính Đúng Đắn Của Công Thức Toán & Tài Chính (`./verify_js.sh`)
Thay vì bật `browser_subagent` (tốn 50.000 token và không biết lỗi do công thức hay do lấy sai ID ô input HTML), mọi hàm trong Tầng 1 (`engine.js`, `taxOptimizer.js`, `monteCarlo.js`, `patrimoine.js`) đều được kiểm chứng trực tiếp bằng `./verify_js.sh "<biểu_thức>"` trong **0.15 giây (chỉ tốn ~150 token)**:

- **Các lệnh kiểm tra mẫu thông dụng:**
  ```bash
  # 1. Kiểm tra Thuế lũy tiến Pháp hoặc Việt Nam
  ./verify_js.sh "window.TaxOptimizer.calculateProgressiveTax(45000, 'FR')"

  # 2. Kiểm tra Lương hưu Pháp & Phạt Décote quý thiếu (Lương 3.500€, 160/172 quý, nghỉ hưu tuổi 64)
  ./verify_js.sh "window.TaxOptimizer.calculateFrenchPension(3500, 160, 172, 64)"

  # 3. Kiểm tra định giá Khấu hao Chung cư vs Nhà mặt đất
  ./verify_js.sh "computeApartmentMetrics({ price: 200000, monthlyRent: 850, loanTermYears: 20, interestRate: 0.035 })"

  # 4. Kiểm tra Lợi suất danh mục theo tỷ lệ phân bổ tài sản
  ./verify_js.sh "window.RetirementEngine.calculateWeightedReturn({ stocks: 60, bonds: 30, real_estate: 10 })"

  # 5. In chi tiết biến trung gian của 1 năm cụ thể (ví dụ năm 65 tuổi) trong dự phóng 40 năm
  ./verify_js.sh "(() => { const res = window.RetirementEngine.runProjection(plan); return res.timeline.find(y => y.age === 65); })()"
  ```

- **Phương pháp 3 bước đối chiếu "Ground Truth" (Số liệu chuẩn):**
  1. *Trường hợp cực hạn (Edge Cases):* Tài sản = 0 (không được ra `NaN`/`Infinity`), Tuổi hiện tại = Tuổi nghỉ hưu, Lạm phát = 0%.
  2. *Kiểm chuẩn bài toán mẫu (Benchmark):* Đối chiếu với bài toán kinh điển đã biết trước kết quả (ví dụ: Quy tắc 4% trên 1.000.000€ năm đầu rút đúng 40.000€; đối chiếu biểu thuế với `impots.gouv.fr`).
  3. *In giá trị trung gian (Intermediate Trace):* Kiểm tra từng biến con (`grossIncome`, `taxes`, `livingExpenses`, `netSavings`, `portfolioBalance`).

- **Câu lệnh Prompt mẫu khi nhờ AI kiểm chứng công thức mới (Copy & Paste):**
  ```text
  Hãy kiểm tra công thức tính [tên_công_thức] trong frontend/js/engine.js. Chạy ./verify_js.sh với 2 trường hợp: (1) Người độc thân thu nhập 35.000€, (2) Trường hợp có 2 người phụ thuộc + trường hợp biên tài sản = 0. Phân tích kết quả in ra xem từng con số đã khớp chuẩn chưa.
  ```

#### 3. Quy Trình Chống Biến Nhập Liệu "Ma" (Anti-Orphan Input Protocol & Delta Sensitivity Test)

Một trong những lỗi gây mất uy tín sản phẩm và lãng phí token nhất là **"Biến Nhập Liệu Ma" (Ghost / Orphan Input Variables)**:
- Người dùng tỉ mỉ nhập số liệu vào ô trên màn hình hoặc Modal, nhưng kết quả tính toán tài chính bên dưới **không hề nhúc nhích 1 đồng**!
- Điều này tạo cảm giác ứng dụng "lừa đảo" hoặc bị lỗi, trong khi mã nguồn tích tụ biến rác không ai dám xóa.

##### A. Ba Căn Nguyên Sinh Ra Biến Nhập Liệu Ma
1. **Đứt gãy DOM ➔ State (UI Ghost Input):** Thẻ HTML có ô nhập (`<input id="kidUniMonthly">`) nhưng trong file UI Tab không viết sự kiện `addEventListener('input'/'change')` để đọc `value` lưu vào `plan`, hoặc đọc nhầm ID khác.
2. **Đứt gãy State ➔ Core Engine (Disconnected State Field):** Biến được lưu vào State (`plan.kidUniMonthly = 900`) nhưng trong toàn bộ các file Tầng 1 (`engine.js`, `taxOptimizer.js`, `patrimoine.js`...), **không có bất kỳ dòng code nào đọc đến `plan.kidUniMonthly`**!
3. **Biến Xác Sống Sau Refactor (Zombie Field):** Thuật toán phiên bản cũ từng dùng biến này, nhưng khi nâng cấp công thức mới, lập trình viên/AI đã thay bằng công thức khác nhưng quên xóa ô nhập trên UI và quên xóa trường trong Schema.

##### B. Bài Test Độ Nhạy Biến Thiên (Delta Sensitivity Test — Tốn ~150 Token)
Làm sao để chứng minh 100% một biến đầu vào thực sự có tác động đến kết quả? **Hãy thử nghiệm độ nhạy (Delta Test):**
- **Quy tắc thực hiện:** Chạy hàm Core Engine 2 lần với 2 giá trị cực hạn khác nhau của biến cần thử (ví dụ giá trị Min và Max):
  ```bash
  # Ví dụ: Kiểm tra xem biến 'kidCostMonthly' có thực sự tác động đến dòng tiền không
  ./verify_js.sh "(() => {
    const p1 = window.AppState.getActivePlan();
    const planA = { ...p1, familyPlan: { ...p1.familyPlan, kidCostMonthly: 100 } };
    const planB = { ...p1, familyPlan: { ...p1.familyPlan, kidCostMonthly: 1500 } };
    const resA = window.RetirementEngine.runProjection(planA);
    const resB = window.RetirementEngine.runProjection(planB);
    const delta = resA.finalPortfolio - resB.finalPortfolio;
    return { hasImpact: delta !== 0, deltaSavings: delta };
  })()"
  ```
- **Tiêu chuẩn nghiệm thu:**
  - Nếu `hasImpact: true` và `delta !== 0`: **[PASS]** Biến có tác động số học thực sự đến dòng tiền.
  - Nếu `hasImpact: false` hoặc `delta === 0`: **[FAIL — BIẾN MA PHÁT LỘ]** Thuật toán trong `engine.js` đang bỏ rơi biến này hoặc công thức bị đứt đoạn!

##### C. Script Quét Tĩnh Phát Hiện Biến State Không Dùng Đến (Orphan State Detector)
Để rà soát nhanh toàn bộ dự án xem có biến nào được khai báo trong State mà không bao giờ được Core Engine đọc tới:
```bash
# Quét tìm những thuộc tính của plan trong state.js nhưng không xuất hiện trong engine.js/taxOptimizer.js
python3 -c "
import re
with open('frontend/js/state.js') as f:
    state_keys = set(re.findall(r'plan\.([a-zA-Z0-9_]+)\s*=', f.read()))
with open('frontend/js/engine.js') as f1, open('frontend/js/taxOptimizer.js') as f2:
    engine_code = f1.read() + f2.read()
orphan = [k for k in state_keys if not re.search(r'plan\.' + k + r'\b', engine_code)]
print('[CẢNH BÁO BIẾN MA]:', orphan if orphan else 'Sạch 100% không có biến ma!')
"
```

#### 4. Chiến Thuật "Thoát Vòng Lặp Tử Thần Khi AI Sửa Lỗi Mãi Không Xong" (2-Strike Anti-Spiral Protocol)
Khi gặp một bug khó, nếu AI đoán mò sửa lần 1 không trúng, sửa lần 2 đẻ thêm lỗi mới, đến lần 4–5 thì cả phiên chat dày tới 200.000 token mà code lại rối tung. Hãy áp dụng **Quy tắc Quá 2 Lần Thử Là Dừng Ngay (The 2-Strike Rule)**:
1. **Bước 1 — Khôi phục code sạch (Clean Rollback):** Nếu AI sửa **2 lượt liên tiếp** cho cùng một lỗi mà chưa khỏi, **DỪNG NGAY** việc gõ *"vẫn lỗi, sửa lại đi"*. Chạy `git checkout -- <tên_file_vừa_sửa_hỏng>` (hoặc bảo AI hoàn tác đoạn vừa sửa) để đưa code về điểm Checkpoint ổn định trước đó.
2. **Bước 2 — Mở `New Chat (+)` và dùng "Prompt Cô Lập Nguyên Nhân Gốc Rễ" (Root-Cause Isolation — Copy & Paste):**
   ```text
   Tôi đang gặp lỗi sau: [Mô tả đúng hiện tượng: Khi bấm X hoặc nhập số A thì chỉ số Y hiển thị Z thay vì lý thuyết phải là W].
   Tuyệt đối KHOAN SỬA CODE lúc này.
   Hãy tra @docs/CODEBASE_MAP.md và làm 2 việc để tìm nguyên nhân gốc rễ:
   1. Liệt kê 3 giả thuyết có khả năng cao nhất gây ra lỗi này (do công thức trong Engine, do lấy sai ID ô input HTML, hay do thứ tự sự kiện DOM?).
   2. Chạy ./verify_js.sh với biểu thức in ra các biến trung gian của hàm tính toán để kiểm chứng xem con số bị lệch ở tầng Engine hay tầng UI. Sau khi tìm ra đúng 100% thủ phạm thì mới đề xuất dòng cần sửa.
   ```

#### 5. Kiểm Thử Tĩnh Tương Tác UI Bằng Mock DOM Trong Runner (UI Static Assertion 0-Token)
Kiểm tra tương tác UI động (đổi dropdown thì thẻ nào ẩn/hiện, chọn độc thân thì ẩn bạn đời, kết hôn thì hiện 2 cột song song) **hoàn toàn có thể tự động hóa 100% bằng dòng lệnh** mà không cần mở trình duyệt:
- **Mock DOM Siêu Nhẹ Trong Node.js:** Nhúng một mock object tối giản vào script test runner (`./verify_js.sh`):
  ```javascript
  const document = {
    getElementById: (id) => ({
      value: '', style: {}, classList: { add(){}, remove(){} },
      addEventListener(){}, innerText: '', innerHTML: ''
    }),
    querySelector: () => null,
    querySelectorAll: () => []
  };
  ```
- **Kiểm Thử 40+ Trường Hợp Giao Diện Trong 0.25 Giây:**
  - Nhóm 1: Tình trạng hôn nhân & Bố cục gia đình (Cá nhân vs Vợ chồng).
  - Nhóm 2: Giới tính & Tuổi nghỉ hưu theo luật (Nam 62t, Nữ 60t).
  - Nhóm 3: Quốc gia làm việc & Nơi nghỉ hưu (bật/tắt thẻ độc lập theo `workCountry` / `retireCountry`).
  - Nhóm 4: Ràng buộc logic Popup & Ngân sách tự động điều chỉnh theo PPP.
- **Hiệu quả:** Toàn bộ 42 bài test UI chạy xong trong **0.25 giây**, tốn **0 token browser**, đảm bảo giao diện vững chắc trước khi người dùng kịp mở trình duyệt.

#### 6. Quy Trình Versioning Khi Hoàn Thành Task (Asset Cache-Busting, Git Commit & Rollback Safety Net)

Mỗi khi thi công xong 1 Task, hãy thực hiện quy trình chốt Version 3 lớp để đảm bảo code sạch, trình duyệt nhận file mới ngay và có lưới an toàn khôi phục:

1. **Lớp 1 — Asset Cache-Busting Versioning (`?v=...`):**
   - **Vì sao bắt buộc:** Trình duyệt web luôn chủ động lưu bộ nhớ đệm (cache) cho các file tĩnh (`.css`, `.js`). Nếu bạn sửa code mà không tăng query version, người dùng hoặc tester mở web vẫn chạy trên file cache cũ trong máy, dẫn đến lỗi giao diện hoặc tính toán sai, khiến dev/AI lầm tưởng code vừa sửa bị hỏng!
   - **Quy tắc thực hiện:** Mỗi khi sửa đổi bất kỳ file nào trong `frontend/css/` hoặc `frontend/js/`, bước cuối cùng của Task bắt buộc phải **tăng query version parameter trong `frontend/index.html`**:
     ```html
     <link rel="stylesheet" href="css/styles.css?v=20261019_v169">
     <script src="js/engine.js?v=20261019_v169"></script>
     <script src="js/ui-tab1-streams.js?v=20261019_v169"></script>
     ```
   - **Quy ước đặt tên version:** `?v=YYYYMMDD_vNNN` (ví dụ `20261019_v169` nghĩa là ngày 19/10/2026, bản build số 169). Chỉ sau khi tăng version và chạy `./verify_js.sh` báo `[OK]`, mới chuyển sang bước đóng dấu Git.

2. **Lớp 2 — Git Commit Convention & Checkpoint An Toàn:**
   - Chuẩn hóa tiền tố thông điệp commit để dễ tra cứu lịch sử:
     - `checkpoint: [tên_task]` — Đóng dấu an toàn sau khi hoàn thành 1 task nhỏ trong kế hoạch.
     - `feat: [tên_tính_năng]` — Hoàn thành một tính năng mới.
     - `fix: [tên_lỗi]` — Sửa lỗi tính toán hoặc lỗi hiển thị giao diện.
     - `refactor: [nội_dung]` — Tái cấu trúc, tách nhỏ file, tối ưu mã nguồn không đổi logic.
     - `docs: [tên_tài_liệu]` — Cập nhật blueprint, cẩm nang quy trình hoặc codebase map.

3. **Lớp 3 — Lưới An Toàn Rollback Trong 1 Giây:**
   - Nếu commit vừa rồi gặp lỗi bất ngờ hoặc thử nghiệm không như ý, bạn có thể đưa mã nguồn quay về điểm an toàn trước đó ngay lập tức:
     ```bash
     # Hoàn tác đoạn code vừa sửa trong file
     git checkout -- frontend/js/engine.js
     # Hoặc quay lại commit checkpoint trước
     git reset --hard HEAD~1
     ```

---

### Giai Đoạn 6: Kiểm Duyệt Pháp Lý, Bảo Mật OWASP, Hoàn Thiện Thương Mại & Triển Khai (`./deploy.sh`)

Sau khi hoàn thành toàn bộ các Task tính năng, trước và sau khi đưa ứng dụng lên Server VPS cho người dùng thực tế, hãy thực hiện trọn vẹn 5 bước khóa chốt dưới đây:

#### Bước 6.1 — Kiểm Tra Nhanh Giao Diện Bằng Mắt Thường & Checklist Hoàn Thiện Sản Phẩm Thương Mại (Product Polish)
1. **Kiểm tra giao diện bằng mắt thường (Tốn 0 Token):** Tự mở `http://localhost:8000` trên máy, bấm thử tính năng mới ở cả **Dark Mode & Light Mode** (tiết kiệm 60.000 token so với `browser_subagent`). Gom các chỉnh sửa nhỏ vào 1 danh sách đánh số (Prompt Batching) để sửa 1 lần.
2. **4 tiêu chuẩn biến Code thành Sản phẩm Thương mại hoàn chỉnh:**
   - **Thẻ chia sẻ mạng xã hội & SEO (`OpenGraph` / `meta` tags trong `index.html`):** Đầy đủ `og:title`, `og:description`, `og:image`, `favicon` để khi dán link lên Facebook, Zalo, Telegram, LinkedIn luôn hiện thẻ giới thiệu sắc nét.
   - **Trải nghiệm 10 giây đầu tiên (Onboarding & Default Demo Data):** Người dùng mới mở web thấy ngay dữ liệu mẫu sinh động hoặc *Quick Setup Wizard 4 bước*, không bao giờ đối mặt với màn hình trắng trơn.
   - **Sao lưu & Khôi phục hồ sơ cá nhân (`JSON Backup / Restore` trong `export.js`):** Cho phép tải file dự phòng `.json` và nhập lại bất cứ lúc nào ngay cả khi không đăng ký tài khoản.
   - **Cơ chế tự phục hồi trên Server (`Healthcheck` & `Auto-Restart`):** Backend có `GET /health` trả về `{"status": "ok"}` và dịch vụ VPS cấu hình `Restart=always`.

---

#### Bước 6.1B — Quản Lý Phiên Bản Ứng Dụng (SemVer), Hiển Thị UI Version Badge & Nhật Ký Phát Hành (`CHANGELOG.md`)

Để vận hành ứng dụng chuyên nghiệp phục vụ hàng trăm ngàn người dùng, việc đánh số phiên bản phát hành và minh bạch hóa lịch sử là tiêu chuẩn bắt buộc:

1. **Chuẩn Semantic Versioning (SemVer: `vMAJOR.MINOR.PATCH`):**
   - **MAJOR (x.0.0):** Khi có thay đổi kiến trúc mang tính bước ngoặt, tái cấu trúc schema dữ liệu lớn có thể gây xung đột nếu không tương thích (Breaking Changes).
   - **MINOR (0.x.0):** Khi phát hành phân hệ tính năng mới (ví dụ: Chế độ Vợ chồng song hành, Mô hình PPP Đa quốc gia, Thẩm định BĐS LMNP) nhưng vẫn giữ tương thích ngược 100%.
   - **PATCH (0.0.x):** Khi sửa lỗi nhỏ (bug fixes), chỉnh sửa màu sắc CSS, bổ sung từ vựng dịch trong `i18n.js` hoặc tối ưu hiệu năng tính toán.

2. **Huy Hiệu Phiên Bản Trực Quan Trên Giao Diện (UI Version Badge):**
   - Đặt thẻ hiển thị phiên bản trang nhã ở chân trang (Footer) hoặc trong Hộp thoại Giới thiệu / Modal Thông tin:
     ```html
     <span class="version-badge">pyRetrait v2.4.0 • Build 20261019_v169</span>
     ```
   - **Ý nghĩa sống còn:**
     - *Hỗ trợ gỡ lỗi người dùng (Bug Reporting):* Khi người dùng gặp sự cố và chụp ảnh màn hình gửi hỗ trợ, đội ngũ kỹ thuật nhìn thấy ngay phiên bản họ đang dùng. Loại bỏ hoàn toàn sự cố hiểu lầm do người dùng đang mở tab cũ chưa tải bản cập nhật mới.
     - *Minh chứng tính mới:* Người dùng ngay lập tức biết họ đang được thụ hưởng bản cập nhật mới nhất với những cải tiến gì.

3. **Duy Trì Nhật Ký Phiên Bản Minh Bạch (`CHANGELOG.md` chuẩn Keep a Changelog):**
   - Mọi phiên bản phát hành đều được ghi lại trong `CHANGELOG.md` theo 5 mục chuẩn hóa:
     - `Added`: Tính năng mới đưa vào hệ thống.
     - `Changed`: Thay đổi trong chức năng hiện có.
     - `Deprecated`: Tính năng sắp dừng hỗ trợ trong các bản tới.
     - `Fixed`: Các lỗi đã được xử lý triệt để.
     - `Security`: Nâng cấp bảo mật, vá lỗ hổng hoặc cập nhật thư viện an toàn.
   - Giúp các phiên chat AI trong tương lai nắm bắt trọn vẹn lịch sử tiến hóa của phần mềm mà không cần đọc lại hàng ngàn dòng git log.

4. **Gắn Thẻ Phát Hành Git Tag & Quy Trình Rollback 30 Giây Trên Server VPS:**
   - Khi chuẩn bị upload bản phát hành ổn định lên Server VPS:
     ```bash
     git tag -a v2.4.0 -m "Release v2.4.0: Ho tro vo chong song hanh & PPP da quoc gia"
     git push origin v2.4.0
     ```
   - **Quy trình Khôi phục Khẩn cấp (Emergency Rollback):** Nếu bản deploy mới trên VPS gặp lỗi bất ngờ:
     1. Chạy `git checkout v2.3.0` để đưa mã nguồn về bản ổn định trước đó.
     2. Nếu cấu trúc DB bị xung đột: lấy ngay file sao lưu SQLite tương ứng từ thư mục `backups/` mà `./deploy.sh` đã tự động lưu trước lúc deploy.
     3. Khởi động lại dịch vụ bằng `sudo systemctl restart pyretrait` ➔ Hệ thống trở lại bình thường trong **30 giây**.

---

#### Bước 6.2 — Kiểm Duyệt Pháp Lý, GDPR & AI Tự Động (`Compliance-as-Code`)

Dự án `pyRetrait` hoạt động tại giao điểm của **Tài chính - Thuế, Y tế - Sức khỏe, và Dữ liệu cá nhân / AI** tại Pháp (EU), Việt Nam và Mỹ. Hệ thống kiểm soát **5 rủi ro pháp lý trọng yếu** thông qua **4 bài kiểm tra tự động**:

1. **5 Nguyên Tắc Bảo Vệ Pháp Lý Bắt Buộc Trong Mã Nguồn:**
   - **Ranh giới "Mô phỏng toán học" vs "Tư vấn Tài chính/Thuế trái phép" (AMF/ORIAS Pháp, SEC Mỹ, UBCKNN VN):** Định vị xuyên suốt `pyRetrait` là *"Công cụ phần mềm mô phỏng toán học & giáo dục tài chính cá nhân"*. Mọi nhãn hiển thị và AI chỉ dùng ngôn từ *"Mô phỏng kịch bản / Ước tính tham khảo"*, nghiêm cấm khuyến nghị mua/bán mã cổ phiếu/crypto cụ thể và nghiêm cấm cam kết lợi nhuận.
   - **Miễn trừ trách nhiệm Y khoa (Tab 2 — `ui-tab2-health.js`, chuẩn EU MDR):** Các chỉ số *Tuổi sinh học (Bio-Age)*, *Healthspan* và gợi ý lối sống luôn kèm tuyên bố chỉ mang tính ước tính thống kê phục vụ dự phóng tài chính, không thay thế chẩn đoán bác sĩ.
   - **Bảo vệ Dữ liệu Cá nhân (GDPR / CNIL Pháp & Nghị định 13/2023/NĐ-CP VN):**
     - Khi chạy Offline/Local (`state.js`): Dữ liệu chỉ nằm trong `localStorage` máy người dùng.
     - Khi bật Đồng bộ Cloud (`backend/main.py`, `backend/auth.py`): Đảm bảo đủ 3 quyền GDPR gồm *Đồng thuận (Consent)*, *Trích xuất dữ liệu JSON/CSV (Điều 20 GDPR - `export.js`)* và *Quyền được lãng quên / Xóa vĩnh viễn tài khoản & dữ liệu SQLite (Điều 17 GDPR)*.
     - Khi gọi Gemini AI (`geminiAdvisor.js`) hoặc chia sẻ Cộng đồng (`community.js`): **Ẩn danh hóa 100% (Data Anonymization)** — lọc bỏ hoàn toàn email, tên, token (PII) trước khi gửi payload.
   - **Đạo luật AI Châu Âu (EU AI Act — `geminiAdvisor.js`):** Gắn nhãn minh bạch *"Phân tích tham khảo bởi AI"* và khóa cứng System Prompt Guardrails từ chối phím mã chứng khoán, trốn thuế hoặc kê đơn y tế.
   - **Luật LCEN Pháp & Bản quyền Mã nguồn mở:** Chân trang (Footer) có đủ *Mentions Légales / CGU*; toàn bộ thư viện (`FastAPI`, `Uvicorn`, `PyJWT`, `Pydantic`, `Chart.js`) giữ nguyên giấy phép thương mại tự do (**MIT / BSD / Apache 2.0**), không dính GPL/AGPL.

2. **4 Bài Kiểm Tra Pháp Lý Tự Động (Tích hợp trong `./verify_js.sh`):**
   - *Bài Test 1 (Automated Legal Wording Linter):* Quét tĩnh `i18n.js` và `ui-*.js`, báo `[FAIL]` ngay nếu phát hiện cụm từ cấm (`"cam kết lợi nhuận"`, `"đảm bảo 100% có lãi"`, `"guaranteed return"`, `"rendement garanti"`) hoặc thiếu Guardrail trong `geminiAdvisor.js`.
   - *Bài Test 2 (Disclaimer Presence Check):* Kiểm tra sự hiện diện của Disclaimer tại 4 vị trí: Chân trang `index.html` & Modal Pháp lý, từ điển `i18n.js` (`vi`/`en`/`fr`), bản xuất báo cáo PDF (`export.js`) và khung kết quả AI (`geminiAdvisor.js`).
   - *Bài Test 3 (Privacy & GDPR Test):* Kiểm tra hàm tạo prompt AI không rò rỉ `email`/`username`/`token` và API xóa tài khoản xóa sạch 100% bản ghi trong `users`, `user_plans`, `user_patrimoine`.
   - *Bài Test 4 (License Audit):* Kiểm tra `requirements.txt` và thư viện JS đảm bảo 100% chuẩn MIT/BSD/Apache.

- **Câu lệnh Prompt để AI chạy Kiểm duyệt Pháp lý & GDPR (Copy & Paste):**
  ```text
  Hãy thực hiện Kiểm duyệt Pháp lý & Tuân thủ GDPR (Legal & Compliance Audit) cho dự án:
  1. Kiểm tra từ điển frontend/js/i18n.js (vi/en/fr) và frontend/js/geminiAdvisor.js xem có câu chữ nào vi phạm quy định tư vấn tài chính/thuế/y tế trái phép (cam kết lợi nhuận, khuyên mua mã cụ thể) hoặc thiếu System Prompt Guardrail không.
  2. Kiểm tra sự hiện diện của Tuyên bố miễn trừ trách nhiệm (Disclaimer Tài chính - Thuế - Y tế) tại chân trang frontend/index.html, bản in frontend/js/export.js và hộp thoại AI.
  3. Kiểm tra GDPR & Quyền riêng tư: Đảm bảo payload gửi sang Gemini API trong geminiAdvisor.js đã ẩn danh hóa (không lộ email/tên/token) và backend có đủ cơ chế xóa sạch dữ liệu tài khoản theo Điều 17 GDPR.
  4. Báo cáo kết quả từng mục [PASS]/[WARN]/[FAIL] và đề xuất sửa ngay các mục còn thiếu.
  ```

---

#### Bước 6.3 — Khóa Chốt 7 Lớp Phòng Thủ Bảo Mật OWASP Trước Khi Upload Lên Server VPS

Dự án đã tích hợp sẵn các chốt chặn tự động trong `./verify_js.sh`, `deploy.sh` và `backend/main.py` gồm **7 lớp bảo vệ chuẩn OWASP**:

1. **Lớp 1 — Chống Rò Rỉ Khóa Bí Mật (`Secret Leak Scanner` trong `./verify_js.sh`):** Tự động quét toàn bộ code (`frontend/js/*.js`, `frontend/*.html`, `backend/*.py`) đảm bảo không có khóa `AIzaSy...` hay `sk-...` nào bị viết cứng (hardcode).
2. **Lớp 2 — Cách Ly File Nhạy Cảm & Tự Động Sao Lưu DB Khi Upload (`deploy.sh`):**
   - Lệnh `rsync` trong `./deploy.sh` khóa cứng `--exclude` đối với `.env`, `data/pyretrait.db*`, `data/settings.json`, `data/plans.json`, `frontend/preview.html` và `.agents/`.
   - Trước khi khởi động lại dịch vụ trên VPS, `deploy.sh` tự động sao lưu file SQLite (`data/pyretrait.db`) kèm nhãn thời gian vào thư mục `backups/` trên Server (giữ 10 bản gần nhất).
3. **Lớp 3 — Khóa Ký JWT Mạnh & Băm Mật Khẩu Chuẩn Quân Đội (`backend/config.py` & `backend/auth.py`):** Trên VPS, `.env` bắt buộc khai báo `PYRETRAIT_SECRET_KEY` dài tối thiểu 48 ký tự ngẫu nhiên (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`). Mật khẩu băm bằng `PBKDF2-HMAC-SHA256` kèm `salt` riêng và `hmac.compare_digest`.
4. **Lớp 4 — Ẩn Tài Liệu API Nội Bộ & Khóa Chặt CORS Trên Production (`backend/main.py`):** Đặt `ENV=production` trong `.env` để tự động tắt `/docs`, `/redoc`, `/openapi.json`; đặt `CORS_ORIGINS=https://ten-mien-cua-ban.com`.
5. **Lớp 5 — Gia Cố OWASP HTTP Security Headers & Chống Tràn Bộ Nhớ (`backend/main.py`):** Tự động gắn 4 header (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`) và giới hạn payload tối đa **2MB** (`MAX_PAYLOAD_BYTES = 2MB`).
6. **Lớp 6 — Chống Độc Mã XSS Trên Giao Diện (`escapeHtml`):** Mọi chuỗi do người dùng nhập khi vẽ ra HTML đều đi qua `escapeHtml()`; không lưu mật khẩu trong `localStorage`.
7. **Lớp 7 — Kích Hoạt Ổ Khóa HTTPS Chuẩn Quốc Tế Miễn Phí 100% (Xóa Cảnh Báo *"Votre connexion n'est pas sécurisée"*):**
   - **Nguyên nhân:** Truy cập trực tiếp bằng IP trần (`http://144.217.95.231:8080`) qua giao thức `http://` không được Let's Encrypt cấp chứng chỉ SSL.
   - **Giải pháp A — Nếu CHƯA mua tên miền (Miễn phí 100% trong 1 phút với `sslip.io` + Caddy):**
     ```bash
     sudo apt install -y caddy
     sudo bash -c 'cat > /etc/caddy/Caddyfile <<EOF
     144-217-95-231.sslip.io {
         reverse_proxy 127.0.0.1:8080
     }
     EOF'
     sudo systemctl reload caddy
     ```
     Sau đó truy cập bằng **`https://144-217-95-231.sslip.io`** ➔ Có ngay ổ khóa HTTPS hợp lệ 100%.
   - **Giải pháp B — Nếu ĐÃ có tên miền riêng (`fire.ten-mien.com`):** Trỏ DNS `A Record` về IP VPS, dùng Nginx Reverse Proxy hoặc Caddy và cấp chứng chỉ Let's Encrypt tự động.

- **Câu lệnh Prompt để AI Kiểm duyệt Bảo mật Mã nguồn trước khi chạy `./deploy.sh` (Pre-Deploy Audit — Copy & Paste):**
  ```text
  Tôi chuẩn bị chạy ./deploy.sh để upload phiên bản mới lên Server VPS.
  Hãy thực hiện kiểm duyệt bảo mật trước khi deploy (Pre-Deploy Security Audit):
  1. Chạy ./verify_js.sh để kiểm tra cú pháp toàn bộ 16 file JS và quét rò rỉ API Key/Secret.
  2. Kiểm tra các đoạn code vừa mới thêm gần đây xem có chỗ nào nối chuỗi HTML trực tiếp từ dữ liệu người dùng nhập mà quên bọc escapeHtml() (nguy cơ XSS), thiếu kiểm tra NaN/Infinity hoặc lộ thông tin nhạy cảm ra console.log không.
  3. Kiểm tra file index.html đã tăng số phiên bản ?v=... cho các file CSS/JS vừa sửa chưa.
  4. Báo cáo ngắn gọn kết quả [AN TOÀN ĐỂ DEPLOY] hoặc các điểm cần khóa lại ngay.
  ```

---

#### Bước 6.4 — Bắn 7 Bài Test Tấn Công Bảo Mật Trực Tiếp Trên Đường Link Web Thật (`Post-Deploy Live Penetration Test`)

Sau khi đã upload lên Server và có đường link web thật, bạn **KHÔNG CẦN mở `browser_subagent`**. Bộ công cụ **`./verify_js.sh --live <ĐƯỜNG_LINK_WEB>`** sẽ tự động bắn **7 bài test tấn công giả lập** vào đường link thật trong 1.5 giây (chỉ tốn **~200 token**):
1. Kiểm tra chứng chỉ HTTPS/SSL.
2. Kiểm tra 4 OWASP Security Headers thực tế trả về từ Server.
3. Thử tấn công đọc trộm các file nhạy cảm (`/.env`, `/.git/config`, `/data/pyretrait.db`, `/data/settings.json`, `/backend/main.py`).
4. Kiểm tra xem trang tài liệu API nội bộ (`/docs`, `/openapi.json`) đã được khóa ẩn chưa.
5. Giả lập trang web độc hại (`Origin: https://evil-hacker-domain.com`) gọi trộm API để test tường lửa CORS.
6. Thử gửi Token giả mạo (`Bearer fake.jwt.token`) vào `/api/auth/me` và `POST /api/patrimoine` xem Server có chặn `401 Unauthorized` không.
7. Thử tấn công SQL Injection (`' OR '1'='1' --`) vào API đăng nhập `/api/auth/login`.

- **Câu lệnh Prompt sau khi đã có link Web thật (Copy & Paste):**
  ```text
  Web của tôi đã chạy trên server tại địa chỉ: http://144.217.95.231:8080 (hoặc https://144-217-95-231.sslip.io).
  Không mở browser_subagent. Hãy chạy lệnh ./verify_js.sh --live <đường_link_trên> để thực hiện 7 bài test tấn công bảo mật trực tiếp trên web thật, phân tích kết quả từng mục [PASS]/[WARN]/[FAIL] và hướng dẫn tôi đóng kín mọi lỗ hổng còn cảnh báo.
  ```

---

## Phần III. Bảng Tra Cứu Nhanh Các Câu Lệnh Mẫu Toàn Diện (Theo Đúng Thứ Tự Giai Đoạn 0 ➔ 6 — Copy & Paste)

| Giai đoạn / Tình huống | Câu lệnh mẫu tối ưu Chất lượng, Bảo mật, Pháp lý & Token nhất |
| :--- | :--- |
| **Giai đoạn 0. Khởi tạo dự án mới tinh từ con số 0 (Day-0 Bootstrap & Khóa Versioning)** | *"Tôi bắt đầu dự án mới [Tên App] giải quyết bài toán [X] bằng [Tech Stack]. Khoan viết tính năng, hãy khởi tạo ngay **Bộ 5 File Xương Sống**: `.agents/rules/GEMINI.md`, `PROJECT_BLUEPRINT.md` (kèm Schema `_schemaVersion: 1`), `CHANGELOG.md` (SemVer v1.0.0), `.antigravityignore`, `./verify.sh` (tự động sinh `docs/CODEBASE_MAP.md` tốn 0 token) và `deploy.sh`."* |
| **Giai đoạn 1A. Lên ý tưởng & Xem khung bố cục chữ (300 token)** | *"Tôi muốn làm tính năng [X]. Khoan sửa code. Hãy vẽ **khung bố cục ASCII Wireframe** (các cột, ô nhập, kết quả hiển thị) và chỉ ra 5 điểm thực tế dễ bị thiếu nhất để tôi hình dung."* |
| **Giai đoạn 1B. Xem thử giao diện thật trên file nháp (1.500 token)** | *"Tạo 1 file giao diện nháp độc lập tại `frontend/preview.html` (nhúng sẵn `css/styles.css`, nút đổi Dark/Light Mode và số liệu mẫu) cho tính năng [X]. Không sửa các file chính và không mở `browser_subagent` — tôi sẽ tự mở `localhost:8000/preview.html` xem."* |
| **Giai đoạn 1C. Dựng khung HTML tĩnh trên trang chính trước** | *"Tra `@docs/CODEBASE_MAP.md`, chỉ chèn khung HTML tĩnh kèm số mẫu của thẻ [X] vào `#tab-estate` trong `frontend/index.html` để tôi F5 xem bố cục. Khoan viết `engine.js`, `ui-*.js` và `i18n.js`."* |
| **Giai đoạn 2. Chốt Kiến trúc, Đóng băng Schema & Migration Pipeline (`PROJECT_BLUEPRINT.md`)** | *"Tôi chuẩn bị làm tính năng [X]. Khoan sửa code JS/HTML. Hãy đọc `@PROJECT_BLUEPRINT.md`, cập nhật JSON Schema mới, tăng `_schemaVersion` từ [N] lên [N+1] và viết hàm di trú tuần tự trong `state.js` để dữ liệu cũ của người dùng hoặc file backup cũ luôn được tự động nâng cấp an toàn."* |
| **Giai đoạn 3. Thiết lập Quy chuẩn UI/UX, Chia nhỏ File & Mobile (`.agents/rules/GEMINI.md`)** | *"Đọc `@.agents/rules/GEMINI.md` và `@PROJECT_BLUEPRINT.md`, quy hoạch rõ trách nhiệm file theo kiến trúc 3 tầng (Engine thuần túy / State / UI từng Tab tối đa 1.500 dòng), khóa quy chuẩn biến màu Dark/Light Mode, chống vỡ khung Mobile 375px và cấm tự bật `browser_subagent`."* |
| **Giai đoạn 3 (Đa quốc gia). Quy hoạch Tham số Tập trung & Minh bạch Dữ liệu** | *"Khi mở rộng đa quốc gia [X], hãy tập trung cấu hình vào `COUNTRY_PPP_PROFILES` trong Tầng 1. Đối với các nước chưa có mô hình luật tự động, tuyệt đối không đoán mò công thức generic; hãy tạo khối `#callout-unsupported` hướng dẫn người dùng tự thêm qua `[+ Thêm Thu Nhập]`."* |
| **Giai đoạn 2+3 (Gộp). Chốt Schema & Quy chuẩn File trong 1 lượt** | *"Ý tưởng Giai đoạn 1 đã chốt. Hãy đồng thời: (1) Cập nhật `@PROJECT_BLUEPRINT.md` thêm JSON Schema dữ liệu mới kèm `_schemaVersion` và migration pipeline an toàn; (2) Cập nhật `@.agents/rules/GEMINI.md` phân bổ hàm vào đúng file 3 tầng và khóa quy chuẩn Dark/Light Mode. Khoan viết code."* |
| **Giai đoạn 4. Lập kế hoạch thực thi chia nhỏ Task (`docs/plans/`)** | *"Dựa trên `@PROJECT_BLUEPRINT.md` và `@docs/CODEBASE_MAP.md`, hãy lập kế hoạch vào `docs/plans/[ten_file].md` chia thành các Task độc lập (Engine trước, UI sau, kèm tương thích dữ liệu cũ Migration), ghi rõ tọa độ dòng code cần sửa. Chưa viết code."* |
| **Giai đoạn 5A. Thi công từng Task trong kế hoạch** | *"Đọc `@docs/plans/[ten_file].md` và `@docs/CODEBASE_MAP.md`. Thực hiện duy nhất **Task 1**, kiểm tra bằng `./verify_js.sh`, đánh dấu `[x]` vào file plan rồi dừng lại."* |
| **Giai đoạn 5B. Sửa nhanh nhiều điểm giao diện `.vue` / CSS / chữ (Prompt Batching)** | *"Tra cứu `@docs/CODEBASE_MAP.md`, mở đúng component trong `frontend-vue/src/components/[Tên_File.vue]` (hoặc `styles.css`) và sửa 3 điểm sau: 1... 2... 3... Bổ sung từ điển vào `i18n.js` trong 1 lượt rồi chạy `./verify_js.sh`."* |
| **Giai đoạn 5C. Kiểm tra lỗi tính toán khi thấy số liệu lạ** | *"Trong Tab X, khi tôi chỉnh biến A từ 0% lên 10% thì kết quả B nhảy từ X lên Y bất thường. Hãy tra `@docs/CODEBASE_MAP.md` để kiểm tra hàm tính trong `frontend/js/engine.js`, sửa lại và chạy `./verify_js.sh` với biểu thức kiểm chứng."* |
| **Giai đoạn 5D. Thoát vòng lặp khi AI sửa 2 lần chưa hết lỗi (2-Strike Rule)** | *"Dừng sửa code! Hãy hoàn tác đoạn vừa sửa hỏng, liệt kê 3 giả thuyết nguyên nhân gốc rễ gây lỗi [X] và dùng `./verify_js.sh` in ra giá trị biến trung gian để tìm đúng 100% thủ phạm trước khi sửa lại."* |
| **Giai đoạn 5E. Kiểm tra Chống Biến Ma & Test Độ Nhạy (Delta Sensitivity)** | *"Hãy kiểm tra tính năng [X]: (1) Rà soát toàn bộ ô input trên UI xem đã nối 2 chiều với State chưa; (2) Chạy Delta Sensitivity Test bằng `./verify_js.sh` (thay đổi giá trị input từ min lên max xem kết quả trong Engine có biến thiên tương ứng không) để chứng minh 100% không có biến nhập liệu ma (orphan variable) bị bỏ rơi."* |
| **Giai đoạn 5F. Kiểm thử toàn diện 40+ kịch bản UI bằng Mock DOM & Tăng `?v=...`** | *"Chạy `./verify_js.sh` để test tự động toàn bộ 42 kịch bản UI, tăng query version parameter `?v=YYYYMMDD_vNNN` trong `index.html` cho các file CSS/JS vừa sửa, và đóng commit checkpoint."* |
| **Giai đoạn 6A. Kiểm duyệt Pháp lý, Miễn trừ trách nhiệm & GDPR** | *"Thực hiện Kiểm duyệt Pháp lý & GDPR: kiểm tra từ vựng cam kết trái phép trong `i18n.js`, guardrail trong `geminiAdvisor.js`, sự hiện diện của Disclaimer (Tài chính/Thuế/Y tế) trên UI & bản in PDF, và kiểm tra ẩn danh hóa PII khi gọi AI."* |
| **Giai đoạn 6B. Đóng dấu Release SemVer, Cập nhật UI Badge & CHANGELOG.md** | *"Chuẩn bị phát hành phiên bản mới [vX.Y.Z]: (1) Cập nhật huy hiệu UI Version Badge trong `index.html`; (2) Ghi chép các thay đổi (Added, Changed, Fixed) vào `CHANGELOG.md`; (3) Kiểm tra bảo mật và sẵn sàng gắn Git Tag `vX.Y.Z`."* |
| **Giai đoạn 6C. Kiểm duyệt Bảo mật & Chống sập trước khi Upload** | *"Tôi chuẩn bị upload lên Server. Hãy chạy `./verify_js.sh`, rà soát các code mới thêm xem có nguy cơ XSS (thiếu `escapeHtml`), thiếu `NaN/Infinity` guard, lộ API Key hay quên tăng `?v=...` trong `index.html` không, rồi báo cáo trạng thái sẵn sàng deploy."* |
| **Giai đoạn 6D. Test tấn công Bảo mật trực tiếp trên Link Web thật (200 token)** | *"Web thật đang chạy tại `http://144.217.95.231:8080`. Không mở `browser_subagent`, hãy chạy `./verify_js.sh --live http://144.217.95.231:8080` để bắn 7 bài test bảo mật thực tế và báo cáo kết quả."* |
| **Khi phiên chat đã dài 10–12 lượt hoặc vừa rút ra kinh nghiệm mới** | Gõ `/compact` (nếu đang dở việc), gõ `/learn` (để AI nhớ vĩnh viễn quy tắc vừa dạy), hoặc bấm **`New Chat (+)`** (nếu đã xong việc). |

---

## Phần IV. Chiến Lược Mô-Đun Hóa (Modularity Architecture) & Quy Trình Hợp Tác Đa Lập Trình Viên / Đa AI (Zero-Conflict Team Collaboration)

### 1. Nỗi Đau Thực Tế: Vì Sao "Làm Một Mình Với AI Rất Mệt" & Nỗi Sợ Khi Có Người Khác Cùng Làm?

Khi bạn tự mình dùng AI xây dựng một ứng dụng từ con số 0, ở giai đoạn đầu tốc độ phát triển cực kỳ nhanh. Nhưng khi ứng dụng lớn dần lên (hàng ngàn dòng code, nhiều phân hệ logic, nhiều tab giao diện):
- **Bạn bắt đầu kiệt sức vì làm "một mình gánh tất":** Vừa phải nghĩ nghiệp vụ, vừa ra prompt cho AI, vừa kiểm thử số liệu, vừa rà soát giao diện và canh chừng token. Bạn muốn san sẻ công việc cho lập trình viên khác, đối tác, freelancer hoặc mở nhiều phiên AI Agent làm song song cùng lúc.
- **Nhưng bạn lại vấp phải nỗi sợ "Khủng hoảng Ghép Code" (Merge & Integration Nightmare):**
  - Sợ người khác (hoặc AI khác) sửa vào file làm hỏng những tính năng bạn đã dày công hoàn thiện trước đó.
  - Sợ xung đột mã nguồn gay gắt (Git Merge Conflicts) trên các file khổng lồ dùng chung như `index.html`, `styles.css` hay `i18n.js`.
  - Sợ lệch tên biến trong dữ liệu (Data Schema Drifting) khiến người này lưu `retirement_age` còn người kia đọc `retireAge`, dẫn đến ứng dụng lăn ra lỗi `undefined` hoặc `NaN`.
  - Sợ vỡ giao diện CSS do đặt trùng tên class (ví dụ cả 2 người cùng đặt class `.card` hay `.item` nhưng với hai màu nền và viền trái ngược nhau).

Để giải quyết triệt để vấn đề này và chuyển hóa dự án từ **"Một mình gánh vác"** thành **"Cỗ máy hợp tác trơn tru"**, ứng dụng bắt buộc phải được thiết kế theo **Mô hình Mô-Đun Hóa 5 Lớp Chống Xung Đột (The 5-Layer Zero-Conflict Modularity Framework)** dưới đây:

```mermaid
flowchart TD
    subgraph L1["Lớp 1: Đóng Băng Hợp Đồng Dữ Liệu (Contract-First Schema)"]
        S1["PROJECT_BLUEPRINT.md chốt Schema"] --> S2["Mỗi Module sở hữu 1 Namespace riêng biệt"]
    end
    subgraph L2["Lớp 2: Kiến Trúc Phân Lập Code & DOM (Decoupled Isolation)"]
        D1["DOM: Container ID Độc Lập (#mod-health-root)"]
        D2["CSS: Tiền Tố Namespace Scoping (.hlth-*, .tax-*)"]
        D3["Logic: Giao tiếp qua Event Bus (Pub/Sub)"]
    end
    subgraph L3["Lớp 3: Mô-Đun Hóa Đa Ngôn Ngữ Tự Đăng Ký (Decentralized i18n)"]
        I1["I18n.registerModule('health', dict)"] --> I2["Không sửa chung file i18n.js"]
    end
    subgraph L4["Lớp 4: Hồ Sơ Nhiệm Vụ Khép Kín Cho Người Khác (Task Brief)"]
        T1["White-list: File & Biến được phép sửa"]
        T2["Black-list: Vùng cấm địa (Core Engine, Shared DOM)"]
    end
    subgraph L5["Lớp 5: Trọng Tài Tự Động Hóa & Git Ghép Nhánh (Gatekeeper CI)"]
        G1["Feature Branch -> ./verify_js.sh tự động test"] --> G2["Merge vào main trong 3 phút không xung đột"]
    end
    L1 --> L2 --> L3 --> L4 --> L5
```

---

### 2. Lớp 1 — Đóng Băng Hợp Đồng Dữ Liệu & Phân Quyền Namespace (Contract-First Schema)

Nguyên tắc số 1 để nhiều người cùng làm mà không giẫm chân lên nhau: **Không ai được phép tự ý bịa thêm biến vào State chung mà chưa có sự đồng thuận trên bản thiết kế.**

1. **Phân chia Không Gian Tên Dữ Liệu (Data Namespacing):**
   - Thay vì để mọi biến phẳng lỳ trong đối tượng `plan` (dễ bị ghi đè lẫn nhau), mỗi phân hệ tính năng phải có một "ngăn kéo" riêng biệt:
     ```javascript
     // Cấu trúc phân quyền dữ liệu rõ ràng trong PROJECT_BLUEPRINT.md
     const plan = {
       // --- Dữ liệu nền tảng cốt lõi (Core Engine sở hữu, chỉ đọc) ---
       id: "plan_123",
       currentAge: 35,
       retireAge: 62,
       
       // --- Namespace của Nhóm Tab 1 (Dòng tiền & Tài sản) ---
       streams: { monthlySavings: 1500, expenses: 2000, ... },
       
       // --- Namespace của Nhóm Tab 2 (Sức khỏe & Tuổi thọ) ---
       health: { bioAge: 33, healthspanScore: 85, lifestyleFactors: {...} },
       
       // --- Namespace của Nhóm Tab 3 (Thuế & Bất động sản LMNP) ---
       taxes: { taxParts: 2.0, lmnpProperties: [...], foreignAccounts: [...] }
     };
     ```
2. **Quy tắc Sở Hữu Dữ Liệu (Data Ownership Rule):**
   - Người phụ trách Tab 2 **chỉ có quyền ghi vào `plan.health`**, tuyệt đối không được sửa đổi trực tiếp vào `plan.taxes` hay `plan.streams`.
   - Nếu Tab 2 cần dùng tuổi nghỉ hưu, họ chỉ được **đọc** `plan.retireAge`, không được thay đổi giá trị của nó.

---

### 3. Lớp 2 — Kiến Trúc Phân Lập Giao Diện & Giao Tiếp Bằng Event Bus (Decoupled DOM & Event-Driven)

Nguyên nhân lớn nhất gây xung đột khi ghép code là các lập trình viên **gọi trực tiếp hàm nội bộ của nhau** hoặc **cùng sửa chung vào một khối thẻ HTML / class CSS**.

#### 2.1. Phân Lập Khung HTML Bằng Container ID Độc Lập
- Trên trang chính `index.html`, bạn (với vai trò Kiến trúc sư trưởng / Tech Lead) chỉ cần tạo ra các "vùng đất cắm cọc" trống:
  ```html
  <!-- Khu vực do Người A phụ trách -->
  <section id="module-cashflow-root" class="tab-pane active"></section>

  <!-- Khu vực do Người B phụ trách -->
  <section id="module-health-root" class="tab-pane"></section>

  <!-- Khu vực do Người C phụ trách -->
  <section id="module-taxes-root" class="tab-pane"></section>
  ```
- Người làm Tab B chỉ render HTML bên trong `#module-health-root`, hoàn toàn không chạm vào các dòng HTML của Người A hay Người C. Khi ghép code, `index.html` chỉ cần thêm đúng 1 dòng `<script src="js/ui-tab2-health.js"></script>` là xong!

#### 2.2. Quy Chuẩn Đặt Tên CSS Có Tiền Tố Riêng (CSS Namespace Scoping)
- Để tránh việc 2 người cùng đặt tên class `.title`, `.badge`, `.metric-value` nhưng ghi đè style của nhau, bắt buộc áp dụng quy tắc tiền tố theo module:
  - Tab 1: `.cf-*` (Cash Flow — ví dụ `.cf-card`, `.cf-metric-row`).
  - Tab 2: `.hlth-*` (Health — ví dụ `.hlth-bioage-card`, `.hlth-badge-safe`).
  - Tab 3: `.tax-*` (Taxes & Real Estate — ví dụ `.tax-lmnp-table`, `.tax-deduction-chip`).
- Tách file CSS theo từng phân hệ: Thay vì nhét 9.000 dòng vào `styles.css`, chia thành `css/modules/tab1-streams.css`, `css/modules/tab2-health.css`... Người nào làm tính năng nào chỉ sửa đúng file CSS của phân hệ đó.

#### 2.3. Giao Tiếp Giữa Các Module Bằng Event Bus (Loose Coupling via Pub/Sub)
- **Tuyệt đối cấm:** Tab 2 gọi trực tiếp `window.Tab1Streams.renderChart()` hoặc gọi hàm của Tab 3. Nếu Tab 1 đổi tên hàm, Tab 2 sẽ sập ngay lập tức!
- **Chuẩn giao tiếp bằng Custom Event:**
  - Khi một module làm thay đổi dữ liệu (ví dụ: người dùng cập nhật tuổi nghỉ hưu hoặc tình trạng hôn nhân), module đó chỉ cần bắn ra 1 sự kiện:
    ```javascript
    // Tab 1 hoặc Quick Setup Wizard thông báo dữ liệu đã đổi
    window.dispatchEvent(new CustomEvent('pyretrait:plan-updated', {
      detail: { planId: activePlan.id, timestamp: Date.now() }
    }));
    ```
  - Các module khác (Tab 2, Tab 3) chỉ việc lắng nghe sự kiện này và tự kích hoạt hàm render nội bộ của chính mình:
    ```javascript
    // Trong ui-tab2-health.js
    window.addEventListener('pyretrait:plan-updated', () => {
      const plan = window.AppState.getActivePlan();
      renderHealthTab(plan);
    });
    ```
  - **Lợi ích vàng:** Bạn có thể tháo rời, nâng cấp, viết lại toàn bộ Tab 2 hoặc tắt bỏ tạm thời Tab 3 mà toàn bộ phần còn lại của ứng dụng vẫn chạy 100% bình thường, không sinh ra bất kỳ lỗi `undefined is not a function` nào!

---

### 4. Lớp 3 — Mô-Đun Hóa Đa Ngôn Ngữ Tự Đăng Ký (Decentralized i18n Registration)

File `i18n.js` thường là "điểm nóng xung đột Git" (Merge Conflict Hotspot) lớn nhất vì tính năng nào cũng cần dịch Tiếng Việt, Tiếng Anh, Tiếng Pháp. Nếu 3 người cùng chèn thêm chữ vào file này, Git sẽ báo xung đột dòng liên tục.

- **Giải pháp: Cơ chế Tự Đăng Ký Từ Điển (`Dynamic Translation Registration`):**
  - Trong `i18n.js`, cung cấp một hàm mở rộng:
    ```javascript
    window.I18n = {
      // ... từ điển nền tảng dùng chung (header, footer, nút bấm chung) ...
      registerTranslations: function(namespace, translationsByLang) {
        // translationsByLang: { vi: {...}, en: {...}, fr: {...} }
        ['vi', 'en', 'fr'].forEach(lang => {
          if (translationsByLang[lang]) {
            Object.assign(DICTIONARY[lang], translationsByLang[lang]);
          }
        });
        // Kích hoạt render lại chữ trên màn hình nếu cần
        window.I18n.applyTranslations();
      }
    };
    ```
  - Người làm Tab 2 hoặc AI phụ trách phân hệ mới chỉ cần khai báo từ điển ngay đầu file của họ (`ui-tab2-health.js`) hoặc trong 1 file con `i18n-tab2.js`:
    ```javascript
    // Tự đăng ký từ vựng riêng của Tab Sức Khỏe, không cần đụng vào file i18n.js gốc!
    window.I18n.registerTranslations('health', {
      vi: { 'hlth.bioAge': 'Tuổi sinh học', 'hlth.safe': 'Dẻo dai' },
      en: { 'hlth.bioAge': 'Biological Age', 'hlth.safe': 'Resilient' },
      fr: { 'hlth.bioAge': 'Âge Biologique', 'hlth.safe': 'Résistant' }
    });
    ```
  - Khi ghép code: **Không ai đụng vào `i18n.js` gốc**, loại bỏ hoàn toàn 100% nguy cơ merge conflict về ngôn ngữ!

---

### 5. Lớp 4 — Hồ Sơ Nhiệm Vụ Khép Kín Khi Phân Việc Cho Người Khác / AI Khác (Self-Contained Task Brief)

Khi bạn muốn san sẻ một tính năng cho một lập trình viên khác (hoặc bật một cửa sổ AI Agent mới), **sai lầm lớn nhất** là giao việc bằng miệng hoặc nói chung chung: *"Làm giúp tôi tính năng tính khấu hao BĐS LMNP nhé"*. Người đó sẽ bắt đầu đọc mò vào toàn bộ dự án, sửa lung tung vào các file lõi và làm hỏng hệ thống.

Hãy dùng **Mẫu Hồ Sơ Nhiệm Vụ Khép Kín (Task Brief Contract)** dưới đây gửi cho họ (Copy & Paste):

```markdown
# HỒ SƠ NHIỆM VỤ ĐỘC LẬP: TÍNH NĂNG [TÊN TÍNH NĂNG]

## 1. Mục Tiêu & Yêu Cầu Nghiệp Vụ
- Mô tả ngắn gọn: [Tính toán và hiển thị bảng khấu hao căn hộ LMNP Pháp].
- Tham khảo giao diện mẫu: Xem ASCII Wireframe hoặc file nháp `frontend/preview.html`.

## 2. Phạm Vi Quyền Hạn File (White-List vs Black-List — Cực Kỳ Quan Trọng)
- **VÙNG ĐƯỢC PHÉP TẠO MỚI / CHỈNH SỬA (White-list):**
  - Tạo mới file logic: `frontend/js/ui-tab3-lmnp.js` (không quá 1.000 dòng).
  - Tạo mới file CSS: `frontend/css/modules/lmnp.css` (dùng tiền tố `.lmnp-*`).
  - Viết hàm kiểm thử trong: `tests/test_lmnp.js`.
- **VÙNG CẤM ĐỊA TUYỆT ĐỐI KHÔNG CHẠM VÀO (Black-list):**
  - CẤM sửa `frontend/js/engine.js` và `frontend/js/state.js` gốc.
  - CẤM sửa cấu trúc chung của `frontend/index.html` (chỉ được render nội dung vào container `<div id="lmnp-container-root">` đã cấp sẵn).
  - CẤM sửa các class CSS dùng chung (`.card`, `.btn`, `.modal`).

## 3. Hợp Đồng Dữ Liệu Đầu Vào & Đầu Ra (Data Contract)
- **Đầu vào (Chỉ đọc từ AppState):**
  - `const plan = window.AppState.getActivePlan();`
  - Lấy trường: `plan.lmnpProperties` (mảng danh sách BĐS).
- **Đầu ra (Ghi kết quả):**
  - Khi người dùng thêm BĐS mới, chỉ cập nhật vào `plan.lmnpProperties`, sau đó gọi:
    `window.dispatchEvent(new CustomEvent('pyretrait:plan-updated'));`

## 4. Tiêu Chuẩn Nghiệm Thu Kỹ Thuật (Acceptance Criteria)
1. Cú pháp JS hợp lệ 100%, chạy `./verify_js.sh` báo `[OK]`.
2. Hỗ trợ song song Dark Mode & Light Mode bằng biến CSS (`var(--bg-card)`, `var(--text-main)`).
3. Đăng ký từ điển đa ngôn ngữ (vi, en, fr) qua `window.I18n.registerTranslations()`.
4. Không có lỗi `NaN` hay `Infinity` khi người dùng nhập số 0 hoặc để trống ô.
```

---

### 6. Lớp 5 — Quy Trình Git Nhánh Độc Lập & Trọng Tài Tự Động Hóa (Git Feature Branching & Automated Gatekeeper)

Để việc ghép code diễn ra trong 3 phút mà không có bất kỳ rủi ro nào:

```mermaid
gitGraph
   commit id: "v2.4.0 (Main)"
   branch feat/tab2-health
   checkout feat/tab2-health
   commit id: "Tạo ui-tab2-health.js"
   commit id: "Thêm CSS .hlth-*"
   checkout main
   branch feat/tab3-lmnp
   checkout feat/tab3-lmnp
   commit id: "Tạo ui-tab3-lmnp.js"
   checkout feat/tab2-health
   commit id: "verify_js [OK]"
   checkout main
   merge feat/tab2-health id: "Merge nhánh Health (3 phút)"
   checkout feat/tab3-lmnp
   merge main id: "Rebase nhận code mới"
   commit id: "verify_js [OK]"
   checkout main
   merge feat/tab3-lmnp id: "Merge nhánh LMNP (Không conflict)"
```

1. **Nguyên Tắc Phân Nhánh Git (Feature Branch Isolation):**
   - Không ai (kể cả bạn khi thử nghiệm tính năng mới) được commit thẳng lên nhánh `main`.
   - Mỗi người làm trên một nhánh độc lập:
     - Bạn A: `git checkout -b feat/tab2-bioage`
     - Bạn B: `git checkout -b feat/tab3-lmnp`
2. **Quy Trình Kiểm Tra Bằng Trọng Tài Tự Động (`./verify_js.sh`):**
   - Trước khi yêu cầu ghép nhánh (Pull Request), lập trình viên phải chạy lệnh kiểm thử trên máy của mình:
     ```bash
     ./verify_js.sh
     ```
   - Nếu có lỗi cú pháp, rò rỉ API key hoặc gõ sai quy tắc CSS: `./verify_js.sh` sẽ chặn lại ngay, không cho phép gửi code lỗi lên kho chung.
3. **Quy Trình Nhạc Trưởng Ghép Nhánh (Integration Review Trong 3 Phút):**
   - Khi Bạn A nộp nhánh `feat/tab2-bioage`:
     1. Bạn mở Pull Request xem danh sách file thay đổi: Bạn A **chỉ sửa đúng 2 file riêng biệt** (`ui-tab2-health.js` và `tab2-health.css`), hoàn toàn không đụng vào `engine.js` hay `index.html`.
     2. Bấm nút **Merge** trên GitHub / Git: **Xác suất conflict = 0%**!
     3. Bạn mở `index.html` thêm đúng 1 dòng nhúng file của Bạn A, tăng `?v=...` và deploy lên server.
   - Khi Bạn B chuẩn bị nộp nhánh `feat/tab3-lmnp`:
     - Bạn B chỉ cần gõ `git merge main` để cập nhật các cải tiến của Bạn A vào máy mình. Nhờ các module nằm ở các file độc lập, việc merge này diễn ra tự động 100% trong 1 giây.

---

### 7. Tóm Tắt Bản Tuyên Ngôn: 6 Điều Khoản "Thảnh Thơi Khi Mở Rộng Đội Ngũ"

| Điều khoản | Trước đây (Làm một mình, ôm đồm, mệt mỏi) | Sau khi Mô-Đun Hóa (Nhiều người/AI cùng làm trơn tru) |
| :--- | :--- | :--- |
| **1. Quản lý File** | Gom toàn bộ vào 1 vài file khổng lồ 5.000–8.000 dòng. | Mỗi tính năng là 1 file JS + 1 file CSS độc lập dưới 1.000 dòng. |
| **2. Giao tiếp giữa các Tab** | Gọi chéo hàm nội bộ của nhau, đổi tên là sập cả web. | Giao tiếp 100% qua sự kiện Event Bus (`pyretrait:plan-updated`). |
| **3. Cấu trúc Dữ liệu** | Mỗi người tự ý đặt tên biến mới trong State. | Đóng băng Schema trong `PROJECT_BLUEPRINT.md`, chia Namespace rõ ràng. |
| **4. Đa ngôn ngữ i18n** | Cùng sửa vào 1 file `i18n.js` duy nhất, liên tục conflict Git. | Tự đăng ký từ điển qua `window.I18n.registerTranslations()`. |
| **5. Phân công công việc** | Giao việc mơ hồ, người làm sau sửa đè vào code người làm trước. | Giao việc bằng **Hồ Sơ Nhiệm Vụ Độc Lập** (có White-list & Black-list file). |
| **6. Ghép mã nguồn (Merge)** | Nơm nớp lo sợ vỡ web, mất cả ngày để gỡ merge conflict. | Trọng tài `./verify_js.sh` duyệt tự động, ghép nhánh trong 3 phút không lỗi. |

Áp dụng trọn vẹn 5 lớp mô-đun hóa này sẽ giải phóng bạn khỏi sự kiệt sức của việc phát triển đơn độc, giúp bạn tự tin chia việc cho cộng sự hoặc điều phối nhiều AI Agent cùng xây dựng ứng dụng với tốc độ vượt trội mà hệ thống vẫn luôn ổn định, vững như bàn thạch!

---

## Phần V. Cẩm Nang Bảo Trì Bền Vững (Long-Term Maintainability Framework): 6 Trụ Cột Giữ Ứng Dụng Vững Vàng, Dễ Nâng Cấp & Không Bao Giờ Thối Rữa Mã Nguồn

### 1. Triết Lý: Dễ Bảo Trì Không Phải Do May Mắn — Đó Là Thiết Kế Kỹ Thuật Có Chủ Đích

Một nghịch lý rất phổ biến trong giới lập trình: **"Ứng dụng chạy rất tốt ở tháng đầu tiên, nhưng sau 3–6 tháng không ai dám đụng vào sửa bất kỳ dòng nào vì sợ sập web"**.
- Hiện tượng này gọi là **Thối Rữa Mã Nguồn (Code Rot)** hoặc **Tích Tụ Nợ Kỹ Thuật (Technical Debt)**:
  - Các hàm tính toán gọi chéo vào DOM, đổi 1 ID thẻ HTML làm hàm tính lăn ra lỗi.
  - Tên biến trong dữ liệu bị trôi dạt (Schema Drift), nâng cấp tính năng mới làm dữ liệu cũ của người dùng bị biến thành `undefined` hoặc `NaN`.
  - Không có công cụ kiểm thử tự động, mỗi lần sửa một nút bấm nhỏ phải mở trình duyệt click bằng tay hàng chục chỗ.
  - Trình duyệt kẹt cache cũ khiến lập trình viên sửa code thật nhưng máy vẫn chạy file cũ, sinh ra ảo giác đoán mò.

Để một ứng dụng tồn tại và phát triển bền bỉ suốt 3–5 năm mà **bất kỳ lúc nào bạn (hoặc một phiên chat AI mới tinh) mở ra cũng có thể bảo trì, sửa lỗi và nâng cấp trong vài phút**, ứng dụng bắt buộc phải tuân thủ **6 Trụ Cột Kỹ Thuật Vàng** dưới đây:

```mermaid
flowchart TD
    M1["1. Kiến Trúc 3 Tầng: Tách bạch Logic Pure Calculation với DOM UI"] --> M_ALL["HỆ THỐNG DỄ BẢO TRÌ BỀN VỮNG"]
    M2["2. Chuỗi Di Trú Schema Bậc Thang: Bảo toàn 100% dữ liệu người dùng cũ"] --> M_ALL
    M3["3. Bản Đồ Codebase Tự Động: Nhảy thẳng 50 dòng cần sửa, 0 token mò mẫm"] --> M_ALL
    M4["4. Kiểm Thử Hồi Quy 0.25s: 42+ test cases tĩnh duyệt sạch lỗi trước khi deploy"] --> M_ALL
    M5["5. Đa Ngôn Ngữ Tập Trung / Tự Đăng Ký: Đổi chữ không chạm logic"] --> M_ALL
    M6["6. Kỷ Luật Cache-Busting & Quy Tắc Gỡ Lỗi 2-Strike Cô Lập Biến Gốc"] --> M_ALL
```

---

### 2. Sáu Trụ Cột Kỹ Thuật Bảo Trì Ứng Dụng Dài Hạn

#### Trụ Cột 1 — Tách Biệt Hoàn Toàn Giữa Logic Tính Toán (Pure Calculation) Và Giao Diện (DOM)
- **Quy tắc bất biến:** Toàn bộ tầng Core Engine (`engine.js`, `taxOptimizer.js`, `monteCarlo.js`, `patrimoine.js`) là **các hàm thuần túy (Pure Functions)**:
  - Chỉ nhận tham số đầu vào (`plan`) và trả về kết quả số học (`{ timeline, finalPortfolio, optimalFireAge }`).
  - **TUYỆT ĐỐI CẤM chứa bất kỳ dòng lệnh DOM nào** (`document.getElementById`, `window.alert`, `classList`).
- **Lợi ích bảo trì sống còn:**
  - Khi cần điều chỉnh luật thuế mới, sửa công thức lương hưu hay tối ưu thuật toán Monte Carlo: Bạn chỉ sửa đúng trong Engine mà **không bao giờ lo làm vỡ layout, lệch khung CSS hay đứt sự kiện nút bấm**.
  - Cho phép kiểm thử tự động bằng Node.js dòng lệnh trong **0.15 giây** mà không cần mở trình duyệt.

#### Trụ Cột 2 — Chuỗi Di Trú Dữ Liệu Tuần Tự Theo Bậc Thang (`_schemaVersion` & Sequential Migration)
- Dữ liệu người dùng là tài sản vô giá. Không bao giờ được phép làm hỏng kế hoạch tài chính đã lưu của họ khi app nâng cấp phiên bản.
- **Khóa phiên bản bằng `_schemaVersion`:** Mọi bản ghi dữ liệu đều mang số phiên bản.
- **Quy tắc di trú bậc thang (Tuyệt đối không rẽ nhánh `else if` cóc nhảy):**
  ```javascript
  function migratePlan(rawPlan) {
    let plan = { ...rawPlan };
    let v = plan._schemaVersion || 1;

    // Nấc 1 lên Nấc 2: Bổ sung quốc gia & tình trạng hôn nhân
    if (v < 2) {
      plan.workCountry = plan.workCountry || 'FR';
      plan.maritalStatus = plan.maritalStatus || 'single';
      v = 2;
    }
    // Nấc 2 lên Nấc 3: Bổ sung Kế hoạch con cái & Lương hưu Đức
    if (v < 3) {
      if (!plan.familyPlan) {
        plan.familyPlan = { enabled: true, kidsCount: 0, kidCostMonthly: 350, kidUniMonthly: 900 };
      }
      v = 3;
    }
    plan._schemaVersion = v;
    return ensurePlanDefaults(plan); // Bù đắp an toàn các giá trị biên
  }
  ```
- **Lợi ích bảo trì:** Dù người dùng xuất file JSON dự phòng từ 2 năm trước rồi import lại vào phiên bản hiện tại, hệ thống vẫn tự động chạy tuần tự `v1 ➔ v2 ➔ v3`, bù đắp đầy đủ các trường mới mà không bao giờ báo lỗi `Cannot read properties of undefined`.

#### Trụ Cột 3 — Bản Đồ Tọa Độ Dòng Code Tự Động Hóa 100% (`docs/CODEBASE_MAP.md`)
- Khi ứng dụng đạt quy mô trên 10.000 dòng code, việc mở từng file đọc từ đầu đến cuối là nguyên nhân hàng đầu gây "ngộ độc ngữ cảnh" (Context Overflow) và tiêu tốn hàng trăm ngàn token.
- Bộ công cụ `./verify_js.sh` tích hợp script Python tự động quét tọa độ dòng code (`StartLine` – `EndLine`) của:
  - Mọi hàm trong Tầng 1 (Engine).
  - Mọi khối State & API trong Tầng 2.
  - Mọi thẻ Card, Modal và sự kiện Tab trong Tầng 3.
  - Mọi khối từ điển ngôn ngữ (`vi`, `en`, `fr`).
- **Lợi ích bảo trì:** Khi có bug ở bất kỳ tính năng nào, bạn hoặc AI chỉ cần tra `docs/CODEBASE_MAP.md` và mở đúng 50 dòng liên quan để xử lý triệt để, tiết kiệm **90% thời gian tra cứu và token**.

#### Trụ Cột 4 — Hệ Thống Kiểm Thử Hồi Quy Tĩnh Siêu Tốc (0.25-Second Regression Runner)
- Mỗi khi sửa một chỗ trong code, làm sao để chắc chắn 100% không làm hỏng những chỗ khác?
- Script `./verify_js.sh` tích hợp sẵn bộ kiểm thử hồi quy tĩnh (Mock DOM Runner):
  1. Chạy `node --check` kiểm tra cú pháp toàn bộ 16 file JS.
  2. Tự động chạy **42 bài kiểm thử kịch bản nghiệp vụ thực tế** (hôn nhân đơn/đôi, giới tính Nam 62t/Nữ 60t, quốc gia làm việc & nơi nghỉ hưu, công thức PPP, tự động ẩn/hiện thẻ).
- **Lợi ích bảo trì:** Toàn bộ 42 bài test hoàn tất trong **0.25 giây**, tốn **0 token**. Bất kỳ sự xáo trộn logic nào làm sai lệch hành vi cũ sẽ bị bắt quả tang ngay tại dòng lệnh trước khi kịp deploy.

#### Trụ Cột 5 — Đa Ngôn Ngữ Tập Trung, Tuyệt Đối Không Hardcode Chuỗi Ký Tự
- **Quy tắc:**
  - Trên HTML: Chỉ dùng thuộc tính ngữ nghĩa `data-i18n="key_name"`, `data-i18n-title="key_name"`.
  - Trong JavaScript sinh mã động: Chỉ dùng `window.I18n.t("key_name", "fallback")`.
- **Lợi ích bảo trì:**
  - Khi cần chỉnh sửa câu từ cho dễ hiểu, thuần Việt và gần gũi với đại chúng: Bạn chỉ cần sửa tại file từ điển `i18n.js` mà **không cần chạm vào bất kỳ dòng HTML hay file logic nào**.
  - Khi cần mở rộng thêm ngôn ngữ mới (tiếng Đức, Nhật, Tây Ban Nha): Chỉ cần bổ sung 1 khối từ điển tương ứng mà không phải cấu trúc lại giao diện.

#### Trụ Cột 6 — Kỷ Luật Quản Lý Phiên Bản, Cache-Busting & Quy Tắc Gỡ Lỗi 2-Strike
- **Kỷ luật Cache-Busting (`?v=YYYYMMDD_vNNN`):**
  - Trình duyệt luôn chủ động lưu cache file tĩnh `.js` và `.css`. Nếu sửa file mà không tăng version trong `index.html`, người dùng và chính bạn sẽ tiếp tục chạy trên file cũ trong máy, dẫn đến tình trạng *"đã sửa trong code nhưng màn hình không đổi"*, sinh ra tâm lý hoang mang và đoán mò sửa lung tung.
  - Bắt buộc tăng `?v=...` ở bước nghiệm thu cuối cùng của mỗi Task.
- **Quy tắc gỡ lỗi 2-Strike (Anti-Spiral Protocol):**
  - Nếu AI sửa **2 lần liên tiếp** cho cùng một bug mà vẫn chưa khỏi: **DỪNG LẠI NGAY LẬP TỨC**.
  - Rollback code về checkpoint sạch gần nhất (`git checkout`).
  - Mở `New Chat (+)` và viết một đoạn script nhỏ (scratch script) in ra các biến trung gian để tìm đúng 100% nguyên nhân gốc rễ trước khi chạm tay vào sửa code chính.

---

### 3. Bài Học Thực Chiến: Sửa Lỗi "Nghịch Lý Tuổi Tối Ưu Khi Chọn 2 Con vs 0 Con"

Đây là ví dụ điển hình chứng minh sức mạnh của **Kiến Trúc Dễ Bảo Trì**:

#### Hiện Tượng Lỗi Kỳ Quặc
- Người dùng phản ánh: *"Tại sao khi chọn 2 con thì Tuổi tối ưu là 56 tuổi, nhưng khi chọn 0 con thì Tuổi tối ưu lại bị đẩy lên tận 67 tuổi (vô lý vì nuôi con tốn kém hơn sao lại được nghỉ hưu sớm hơn 11 năm?)"*.

#### Cách Tìm Ra Nguyên Nhân Gốc Rễ Bằng Script Cô Lập (Tốn ~150 Token)
Thay vì đoán mò sửa bừa trong file UI hay bật browser click thử, ta tạo 1 script nhỏ gọi trực tiếp Tầng 1 (Engine & Monte Carlo) và in ra biến trung gian của từng năm tuổi:
```text
KidCount = 0 (Tuổi 69): Vốn lúc hưu = 5.9M €, Rút vốn = -238.000 €/năm ➔ MC Success = 77% (Bị loại vì < 80%)
KidCount = 2 (Tuổi 69): Vốn lúc hưu = 3.5M €, Rút vốn = -137.000 €/năm ➔ MC Success = 80.5% (Đạt chuẩn!)
```
- **Thủ phạm phát lộ ngay lập tức:**
  - Khi tìm tuổi tối ưu, hệ thống cũ đã ép chạy theo chiến lược rút vốn % danh mục (`fixed_pct` 4%). Người 0 con tích lũy được nhiều tiền hơn (5.9M €) nên bị ép rút một khoản tiền mặt khổng lồ (238.000 €/năm), khiến Monte Carlo trong chuỗi năm thị trường xấu bị cạn tiền nhanh hơn người có 2 con (chỉ rút 137.000 €/năm)!
  - Trong khi nhu cầu chi tiêu sinh hoạt thực tế của người 0 con chỉ là 18.000 €/năm!

#### Khắc Phục Chuẩn Xác Trong 1 Lần Sửa Duy Nhất
- Trong hàm `findOptimalRetirementAge`: Khi thử nghiệm `candPlan`, đặt `enableWithdrawalStrategy: false` (chỉ đo lường năng lực trang trải 100% chi tiêu sinh hoạt thực tế và chống chịu rủi ro, không ép rút hoang phí theo % danh mục).
- **Kết quả logic lập tức chuẩn hóa 100%:**
  - **0 con:** Tuổi tối ưu đạt ở **40 tuổi** (hoặc 33 tuổi trên kế hoạch mẫu) — nghỉ hưu sớm nhất do không vướng bận chi phí nuôi dạy.
  - **1 con:** Tuổi tối ưu lùi lại **42 tuổi** (cần làm thêm 2 năm tích lũy cho bé).
  - **2 con:** Tuổi tối ưu lùi lại **44 tuổi** (cần làm thêm 4 năm tích lũy cho 2 bé).
  - **3 con:** Tuổi tối ưu lùi lại **45 tuổi** (cần làm thêm 5 năm tích lũy cho 3 bé).

---

### 4. Quy Trình 5 Bước Chuẩn Mực Khi Cần Bảo Trì / Sửa Bug / Thêm Tính Năng Mới

Mỗi khi bạn quay lại dự án sau vài tuần hay vài tháng, hãy luôn đi theo đúng **5 bước chuẩn hóa** sau:

```text
Bước 1: Tra cứu docs/CODEBASE_MAP.md ➔ Xác định chính xác file và khoảng dòng cần sửa.
Bước 2: Cập nhật Schema & Pipeline di trú (Nếu có thêm biến mới) ➔ Tăng _schemaVersion trong PROJECT_BLUEPRINT.md và viết hàm di trú trong state.js.
Bước 3: Sửa logic ở Tầng 1 (Core Engine) ➔ Chạy script Node.js kiểm chứng số học độc lập.
Bước 4: Nối giao diện ở Tầng 3 (File UI riêng của Tab đó) ➔ Bổ sung từ điển đa ngôn ngữ vào i18n.js.
Bước 5: Chạy ./verify_js.sh duyệt toàn bộ test cases ➔ Tăng ?v=... trong index.html ➔ Đóng dấu Git commit checkpoint.
```

---

### 5. Bảng Checklist Kiểm Tra Sức Khỏe Bảo Trì (Maintainability Health-Check)

Trước khi đóng máy hoặc bàn giao dự án, hãy dành 1 phút đối chiếu với bảng kiểm tra 8 tiêu chí:

| Tiêu chí | Đạt chuẩn [PASS] | Dấu hiệu vi phạm cần chấn chỉnh [FAIL] |
| :--- | :--- | :--- |
| **1. Kích thước file** | Mọi file JS đều dưới 2.000 dòng, phân theo Tab rõ ràng. | Xuất hiện file phình to 4.000 – 8.000 dòng gộp chung logic. |
| **2. Tách bạch DOM** | Các file Core Engine không chứa lệnh `document.*`. | Trong `engine.js` hay `taxOptimizer.js` có `document.getElementById`. |
| **3. An toàn dữ liệu cũ** | Mọi schema mới đều có khối `if (v < N)` trong hàm di trú. | Thêm trường mới mà người dùng cũ mở app bị lỗi `undefined`. |
| **4. Bản đồ Codebase** | File `docs/CODEBASE_MAP.md` cập nhật chính xác số dòng mới nhất. | Số dòng trong codebase map bị lệch so với code thực tế. |
| **5. Kiểm thử hồi quy** | Lệnh `./verify_js.sh` báo `[PASS]` 100% toàn bộ test cases. | Có test case bị `[FAIL]` hoặc bỏ qua không chạy test. |
| **6. Đa ngôn ngữ** | 100% nhãn mới đều có đủ bản dịch `vi`, `en`, `fr` trong `i18n.js`. | Hardcode chữ tiếng Việt trực tiếp trong HTML/JS không có thẻ `data-i18n`. |
| **7. Tránh dính cache** | Query version parameter `?v=...` trong `index.html` đã được tăng số. | Sửa file JS/CSS nhưng `index.html` vẫn giữ nguyên version cũ. |
| **8. Không có Biến Ma** | 100% ô input trên UI đều có kết nối 2 chiều với State và trực tiếp làm thay đổi kết quả ở Core Engine (vượt qua Delta Sensitivity Test). | Có ô nhập trên UI hoặc thuộc tính trong State nhưng không có bất kỳ dòng code nào trong Core Engine đọc tới. |

Tuân thủ nghiêm ngặt cẩm nang này, ứng dụng của bạn sẽ luôn là một **công trình kiến trúc sạch sẽ, trường tồn, dễ mở rộng và vận hành tin cậy** cho hàng trăm ngàn người dùng suốt nhiều năm tháng!

---

## Phần VI. Đo Lường Hiệu Suất App (Performance Benchmark): Làm Sao Biết Bản Mới "Tốt Hơn" Bản Cũ?

**Nguyên tắc:** Không đánh giá bằng cảm giác. Mỗi lần sửa lớn (refactor, thêm tính năng, tối ưu), hãy đo **trước** và **sau** bằng cùng một cách, ghi vào bảng so sánh, rồi mới kết luận.

### 1. Năm Nhóm Chỉ Số Đo Hiệu Suất & Xu Hướng Tốt (Benchmark Matrix)

| Nhóm | Chỉ số | Ý nghĩa thực tế | Xu hướng TỐT | Ngưỡng chuẩn mục tiêu |
| :--- | :--- | :--- | :--- | :--- |
| **A. Tốc độ trang & Web Vitals** | **FCP** *(First Contentful Paint)* | Thời gian từ lúc mở web đến khi thấy chữ/nội dung đầu tiên | 📉 **GIẢM** | < 1,5 giây (trên 4G) |
| | **LCP** *(Largest Contentful Paint)* | Thời gian để bảng số liệu và biểu đồ chính hiển thị rõ | 📉 **GIẢM** | < 2,5 giây |
| | **INP / TBT** *(Độ trễ phản hồi)* | Bấm vào nút, đổi số liệu thì màn hình phản hồi ngay hay đơ | 📉 **GIẢM** | < 150 – 200 ms |
| | **CLS** *(Độ giật bố cục)* | Giao diện tải xong có bị giật khung làm bấm nhầm không | 📉 **GIẢM** | < 0,1 (ổn định, không giật) |
| | **Điểm Lighthouse Mobile** | Điểm số tổng hợp hiệu năng trang web | 📈 **TĂNG** | 85 – 100 điểm |
| **B. Tốc độ tính toán (Engine)** | **Thời gian `runProjection`** | Thời gian tính dòng tiền cả đời hưu trí | 📉 **GIẢM** | < 20 – 30 ms |
| | **Thời gian Monte Carlo (1.000 lần)** | Chạy 1.000 kịch bản ngẫu nhiên | 📉 **GIẢM** | < 200 – 400 ms |
| | **Bộ nhớ RAM (JS Heap Size)** | Lượng RAM trình duyệt ngốn sau 30 phút dùng app | 🔄 **ỔN ĐỊNH** | < 60 – 100 MB (chống rò rỉ bộ nhớ) |
| | **Số lần tính toán thừa** | Gõ số liên tục có bị tính lại 10 lần làm nóng máy không | 📉 **GIẢM** | Hoãn tính (debounce ~250ms) |
| **C. Quy mô & Độ gọn mã nguồn** | **Số file phình to (> 2.000 dòng)** | File quá dài khiến AI đọc tốn token và dễ sinh lỗi | 📉 **GIẢM** | **0 file** (tách theo Tab độc lập) |
| | **Dung lượng Gzip (Bundle size)** | Số KB người dùng phải tải về máy khi mở web | 📉 **GIẢM / TĂNG CHẬM** | < 450 KB gzip |
| | **Số lượng Biến Ma (Orphan input)** | Ô nhập trên UI nhưng không ảnh hưởng kết quả tính toán | 📉 **BẰNG 0** | **0 biến ma** |
| | **Thời gian chạy `./verify_js.sh`** | Tốc độ quét cú pháp và cập nhật `CODEBASE_MAP.md` | 📉 **GIỮ SIÊU NHANH** | < 0,5 giây |
| | **Tỷ lệ Test PASS** | Số test tự động vượt qua | 📈 **ĐẠT 100%** | 100% PASS (0 FAIL) |
| **D. Hiệu quả làm việc với AI** | **Số lượt chat / tính năng** | Số câu đối thoại cần thiết để hoàn thành 1 task | 📉 **GIẢM** | 3 – 5 lượt chat |
| | **Tỷ lệ sửa sai (2-Strike Rate)** | Số lần AI làm sai phải sửa lại | 📉 **GIẢM VỀ 0** | < 1 lần |
| | **Token tiêu thụ / tính năng** | Lượng token tiêu thụ trong phiên làm việc | 📉 **GIẢM 70% – 85%** | < 30.000 – 50.000 token |
| | **Lỗi hồi quy (Regression bugs)** | Sửa cái mới có làm hỏng tính năng cũ không | 📉 **BẰNG 0** | 0 lỗi hồi quy |

### 2. Đo Tự Động Toàn Diện Bằng `./benchmark.sh` (Mã Nguồn, Tốc Độ Engine & Test)

Chỉ cần gõ duy nhất 1 lệnh trong terminal (chạy trong 0.25 giây, **tốn 0 token**):

```bash
./benchmark.sh "Mô tả tính năng hoặc refactor vừa làm"
```

Script sẽ tự động:
1. **Đo quy mô code:** Tổng số dòng, file lớn nhất, số file >2.000 dòng.
2. **Đo dung lượng:** Số KB gzip nén thực tế người dùng phải tải.
3. **Đo tốc độ tính toán Core Engine:** Chạy trực tiếp 5 lần `RetirementEngine.runProjection` và 1.000 lần `MonteCarloSimulator.runSimulation` trong Node.js để đo thời gian mili-giây (`ms`).
4. **Kiểm thử logic:** Chạy `./verify_js.sh` để đếm số test `[PASS]` và `[FAIL]`.
5. **So sánh với lần trước & Đánh giá xu hướng:** Tự động tính độ chênh lệch (Delta), hiển thị icon xu hướng (📉 Giảm = 🟢 TỐT, 📈 Tăng = 🟡 Cần theo dõi, 🔴 Cảnh báo), và ghi kết quả vào `docs/BENCHMARK_LOG.md`.

### 3. Đo Tốc Độ Tính Toán Ngay Trong Console Trình Duyệt (Copy & Paste)

Mở app ➔ `Cmd + Option + J` (Console) ➔ dán đoạn dưới đây. Mỗi phép đo chạy 5 lần và lấy **trung vị** để loại nhiễu:

```javascript
// Đo thời gian trung vị (ms) của một hàm sau 5 lần chạy
const benchmark = (label, fn, runs = 5) => {
  const times = [];
  for (let i = 0; i < runs; i++) {
    const t0 = performance.now();
    fn();
    times.push(performance.now() - t0);
  }
  times.sort((a, b) => a - b);
  console.log(`${label}: ${times[Math.floor(runs / 2)].toFixed(1)} ms (nhanh nhất ${times[0].toFixed(1)} / chậm nhất ${times[runs - 1].toFixed(1)})`);
};

const plan = getActivePlan();
benchmark('runProjection', () => runProjection(plan));
benchmark('updateAll (vẽ lại toàn bộ UI)', () => updateAll());
// Nếu hàm Monte Carlo của dự án có tên khác, đổi lại cho đúng (xem docs/CODEBASE_MAP.md)
// benchmark('Monte Carlo 1000 runs', () => runMonteCarlo(plan), 3);
```

> [!TIP]
> Đo với **cùng một kế hoạch mẫu** (cùng tuổi, tài sản, số con...) ở cả bản cũ và bản mới. Nếu đổi dữ liệu đầu vào thì so sánh không còn công bằng.

### 4. Đo Tốc Độ Tải Trang Bằng Lighthouse (Không Tốn Token)

1. Mở app ở cửa sổ ẩn danh (tránh extension làm nhiễu) ➔ `Cmd + Option + I` ➔ tab **Lighthouse**.
2. Chọn **Mobile** + chỉ tick **Performance** ➔ bấm *Analyze page load*.
3. Chạy 3 lần, ghi lại điểm **Performance**, **FCP**, **Total Blocking Time (TBT)**, **Largest Contentful Paint (LCP)**.
4. Mục tiêu tham khảo: Performance từ 85 điểm trở lên, FCP dưới 1,8 giây, TBT dưới 200 ms.

### 5. Bảng Ghi Nhận Trước / Sau (Dán Vào `CHANGELOG.md` Hoặc `docs/BENCHMARK_LOG.md`)

Mỗi khi hoàn thành 1 tính năng lớn hoặc refactor, thêm 1 dòng vào bảng:

| Ngày | Phiên bản / Commit | Tổng dòng code | File lớn nhất (dòng) | Dung lượng gzip (KB) | `runProjection` (ms) | `updateAll` (ms) | Lighthouse | Test PASS | Nhận xét |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-10-22 | `v1.x.x` (mốc gốc) | ... | ... | ... | ... | ... | ... | .../... | Mốc so sánh đầu tiên |

- **Mốc gốc (Baseline):** Đo ngay hôm nay và ghi lại làm dòng đầu tiên. Từ đó mọi bản sau đều so với mốc này.
- **Quy tắc kết luận "tốt hơn":** Một thay đổi chỉ được coi là cải thiện khi **ít nhất 1 chỉ số tốt lên mà không chỉ số nào xấu đi quá 10%**. Nếu thêm tính năng làm tổng dòng code tăng là bình thường, nhưng tốc độ và dung lượng gzip không được tụt đáng kể.

### 6. Đo Hiệu Quả Làm Việc Với AI (Token & Số Lượt Chat)

- Với mỗi tính năng, ghi lại: **số lượt chat đã dùng**, **số lần phải sửa lại (2-Strike)**, **số lỗi hồi quy phát hiện sau khi hoàn thành**.
- Tính tỷ lệ: `Lượt chat trung bình / tính năng` — con số này giảm dần chứng tỏ bộ quy trình, `CODEBASE_MAP.md` và `verify_js.sh` đang phát huy tác dụng.
- Số lượt chat trên mỗi tính năng nhỏ mục tiêu: **dưới 5 lượt**; tính năng lớn: dưới 15 lượt (chia thành nhiều Task, mỗi Task 1 phiên chat mới).

### 7. Câu Lệnh Prompt Nhờ AI Đo Hiệu Suất (Copy & Paste)

```text
Hãy đo hiệu suất hiện tại của app và ghi vào docs/BENCHMARK_LOG.md thêm 1 dòng mới.
Chỉ dùng lệnh terminal (wc -l, du, gzip) và ./verify_js.sh, KHÔNG mở browser_subagent.
Báo cáo: tổng dòng code, file lớn nhất, dung lượng gzip, số test PASS, và so sánh với dòng liền trước (tăng/giảm bao nhiêu %).
```

### 8. Checklist Đo Hiệu Suất Nhanh (1 Phút)

| Việc cần làm | Khi nào | Xong |
| :--- | :--- | :--- |
| Đo mốc gốc (baseline) trước khi sửa lớn | Trước khi bắt đầu Task | [ ] |
| Chạy `wc -l` + gzip + `./verify_js.sh` | Sau khi xong Task | [ ] |
| Chạy `benchmark(...)` trong Console với kế hoạch mẫu | Sau khi sửa Engine / `updateAll` | [ ] |
| Chạy Lighthouse (3 lần) | Trước mỗi bản phát hành (`./deploy.sh`) | [ ] |
| Ghi 1 dòng vào bảng Trước / Sau và kết luận | Mỗi khi đóng Git Checkpoint | [ ] |

---

## Phần VII. Cẩm Nang Thực Chiến Chuyển Đổi Kiến Trúc Lớn (Migration Playbook: Vanilla JS ➔ Vue 3 / React Giữ Nguyên 100% UI)

Từ thực tế chuyển đổi hơn **42.000 dòng mã nguồn** của pyRetrait từ Vanilla JS sang **Vue 3 + Vite + Pinia** chỉ trong **3 lượt tương tác (0 lỗi, 0 lần mở `browser_subagent`)**, dưới đây là **8 Bài Học Thực Chiến Xương Máu** giúp khởi tạo đúng từ đầu hoặc chuyển đổi bất kỳ dự án lớn nào sang Platform hiện đại mà không làm vỡ giao diện, không tốn hàng trăm nghìn token và không làm gián đoạn hệ thống:

### 0. Bài Học Gốc Rễ: Luôn Bắt Đầu Bằng Một Platform Chuẩn Hơn Là Xây Thủ Công Từ Con Số 0 (Platform-First Mindset)
- **Vì sao xây từ 0 (Vanilla HTML/JS trần) lại trả giá đắt khi app lớn lên?**
  - Không có cơ chế tách Component gốc của HTML khiến `index.html` phình to lên 6.000+ dòng; mỗi lần sửa 1 nút bấm hoặc 1 thẻ là phải định vị trong một tệp khổng lồ.
  - Phải tự viết tay hàng nghìn dòng code hạ tầng vốn dĩ Platform đã làm sẵn tốt hơn gấp 10 lần: định tuyến trang (Router), quản lý trạng thái phản ứng (Reactive State / Store), đóng gói & chống kẹt bộ nhớ đệm (`?v=...` cache-busting thủ công), và quản lý vòng đời component.
- **Nguyên tắc vàng cho mọi dự án tương lai:**
  - Ngay từ ngày đầu tiên (Day 0), **luôn đứng trên vai một Platform chuẩn** (như **Vue 3 + Vite + Pinia + Vue Router** hoặc **Next.js / Nuxt** cho Frontend; **FastAPI / Supabase** cho Backend).
  - Việc dùng Platform ngay từ đầu giúp tự động chia nhỏ mọi thành phần UI thành các Single-File Components (`.vue`) 100–300 dòng, tự động có Reactivity 2 chiều, tự động hash tên file chống cache khi build (`index-BVIYj1p7.js`), và giúp AI tiết kiệm **70–80% lượng token đọc/ghi ngữ cảnh** trong suốt vòng đời dự án.

### 1. Chiến Thuật "Hộp Cát Song Hành" (Parallel Sandbox Directory & Port Isolation)
- **Sai lầm phổ biến:** Sửa trực tiếp đè lên thư mục `frontend/` đang chạy ổn định khiến ứng dụng chết cứng giữa chừng và mất bản mẫu để đối chiếu.
- **Quy chuẩn bắt buộc:**
  1. Luôn tạo một thư mục độc lập (ví dụ: `frontend-vue/`) chạy trên một cổng riêng biệt (ví dụ: `http://localhost:5174/` với `strictPort: true`).
  2. Giữ nguyên 100% thư mục `frontend/` cũ cho đến khi người dùng mở trình duyệt kiểm tra xong Giai đoạn 1 và xác nhận giao diện mới đã giống hệt 100% bản cũ.
  3. Chỉ xóa thư mục cũ sau khi đã hoàn tất chuyển đổi và cập nhật toàn bộ đường dẫn (`backend/main.py`, `verify_js.sh`, `benchmark.sh`, `deploy.sh`).

### 2. Chuyển Đổi 2 Giai Đoạn Thay Vì "Đập Đi Xây Lại" (2-Phase Strangler Fig Pattern)
- **Sai lầm phổ biến (Anti-Pattern):** Bảo AI *"Hãy viết lại ứng dụng này sang Vue"* ngay từ đầu. Khi gặp file HTML 6.000 dòng, AI sẽ tự "tóm tắt" và vẽ ra một giao diện sơ sài chỉ còn 10% tính năng gốc, làm mất sạch các thẻ chi tiết, công thức và CSS.
- **Quy chuẩn 2 Giai đoạn bất biến:**
  - **Giai đoạn 1 — Bê Nguyên 100% DOM, ID & CSS Class (Lift & Shift 1:1):** Dùng script Node.js cắt chính xác từng khối dòng (`lines.slice(...)`) từ `index.html` gốc sang các Vue Single-File Components (`AppHeader.vue`, `AppSidebar.vue`, `TopKpiGrid.vue`, `TabProjections.vue`, `TabHealth.vue`, `TabTaxes.vue`, `AppModals.vue`). Giữ nguyên 100% các thuộc tính `id`, `class`, `data-i18n` và giữ nguyên toàn bộ file CSS gốc.
  - **Giai đoạn 2 — Bọc Reactivity & Đồng Bộ Pinia Hai Chiều (Progressive Reactivity):** Sau khi giao diện 1:1 đã lên hình hoàn hảo, mới nâng cấp từng component sang dùng Pinia Store (`usePlanStore`, `useI18nStore`, `useModalStore`), `computed`, `v-for`, `:class`, `@click`.

### 3. Cầu Nối Đồng Bộ Hai Chiều Giữa Pinia Store & Legacy Event Bus (Two-Way State Bridge)
- Khi ứng dụng có các module tính toán lớn (như `engine.js`, `patrimoine.js`, `ui-tab1-charts.js`), không cần và không nên viết lại toàn bộ 16 file JS cùng một lúc.
- **Giải pháp Cầu nối (`usePlanStore` ⇄ `AppState`):**
  - Trong `ui.js`, cuối hàm `updateAll()`, phát sự kiện `window.AppState.emit('ui-updated', { plan, proj })`.
  - Trong Pinia Store (`stores/plan.js`), lắng nghe toàn bộ sự kiện từ `AppState` (`plans-loaded`, `plan-changed`, `ui-updated`, `currency-changed`, `tab-changed`) và dùng một biến phản ứng `syncTick.value++` để kích hoạt các `computed` (`activePlan`, `projection`, `monteCarloSummary`) tự động tính lại tức thì.

### 4. Kiểm Soát Thứ Tự Khởi Tạo Vòng Đời (`__PYRETRAIT_VUE_MODE__` & `onMounted`)
- **Bẫy kỹ thuật:** Trong bản Vanilla JS cũ, các file `ui.js`, `auth.js`, `patrimoine.js`, `i18n.js` thường gắn sự kiện vào `document.addEventListener("DOMContentLoaded", init)`. Nhưng trong Vue 3 (Vite ESM), khi `DOMContentLoaded` nổ ra thì Vue vẫn chưa kịp mount các component `<template>` vào `<div id="app">`, dẫn đến `document.getElementById(...)` trả về `null` và làm liệt toàn bộ nút bấm/modal!
- **Giải pháp chuẩn:**
  1. Đặt cờ `window.__PYRETRAIT_VUE_MODE__ = true` ngay đầu file `src/main.js` để chặn các module tự chạy sớm khi `DOMContentLoaded`.
  2. Trong `DashboardView.vue`, đợi Vue render xong DOM hoàn toàn bằng `onMounted(async () => { await nextTick(); ... })`, sau đó mới gọi tuần tự `I18n.init()`, `PatrimoineApp.bindEvents()`, `Auth.init()`, `window.initApp()`, và `planStore.init()`.

### 5. Dùng Script Tự Động Hóa Khi Tách File Lớn (Scripted Extraction — Tiết Kiệm 95% Token)
- Khi cần tách một file `index.html` dài 6.067 dòng thành 7 file `.vue`, **tuyệt đối không để AI xuất (output) lại 6.000 dòng HTML qua công cụ `write_file`** (vừa tốn hàng chục nghìn output token, vừa mất 5–10 phút, vừa dễ bị cắt cụt giữa chừng).
- **Cách làm thông minh:** Chạy một lệnh `node -e "..."` dài 20 dòng để đọc `index.html`, kiểm tra trước xem có ký tự đặc biệt của Vue (`{{` hoặc `<script>`) hay không, rồi cắt theo đúng tọa độ dòng (`lines.slice(start, end)`) và ghi thẳng ra các file `.vue` chỉ trong **0.05 giây** với độ chính xác 100% từng byte.

### 6. Cấu Hình Trình Biên Dịch Vue Cho Custom Web Components (`isCustomElement`)
- Khi dự án sử dụng các Web Component như `<iconify-icon>`, bắt buộc cấu hình trong `vite.config.js`:
  ```javascript
  vue({
    template: {
      compilerOptions: {
        isCustomElement: (tag) => tag === 'iconify-icon'
      }
    }
  })
  ```
  Điều này giúp trình biên dịch Vue không báo cảnh báo `[Vue warn]: Failed to resolve component: iconify-icon` và giữ hiệu năng render tối đa.

### 7. Đồng Bộ Hóa Tức Thì Hệ Sinh Thái Kiểm Thử & Tài Liệu (Zero-Drift Tooling Sync)
- Ngay sau khi chuyển đổi kiến trúc và xóa thư mục cũ, bắt buộc cập nhật đồng bộ bộ 4 công cụ tự động hóa trước khi kết thúc phiên:
  1. **`verify_js.sh`**: Quét cú pháp cả `.vue` lẫn `.js`, chạy bộ test headless (`tests/test_plan_creation_ui.js`) và tự động sinh lại `docs/CODEBASE_MAP.md` bao gồm cả tọa độ dòng của các Vue SFC và Pinia Store.
  2. **`npm --prefix frontend-vue run build`**: Chạy kiểm tra đóng gói Vite (`vite build`) để chắc chắn 100% không có lỗi import hay lỗi cú pháp Vue template nào lọt lưới.
  3. **`backend/main.py` & `deploy.sh`**: Trỏ thư mục phục vụ file tĩnh về `frontend-vue/dist` và thêm bước `npm --prefix frontend-vue run build` vào quy trình deploy.
  4. **`.antigravityignore` & Rules (`GEMINI.md`, `PROJECT_BLUEPRINT.md`)**: Chặn ngay `frontend-vue/node_modules/` và `frontend-vue/dist/` để AI không bao giờ đọc nhầm các file bundle đã nén.

---

### 8. Tám Chiến Thuật Tối Ưu Token Hàng Ngày Đặc Thù Cho Platform Vue 3 + Vite + Pinia (Tiết Kiệm 75% – 90% Token)

Khi phát triển hàng ngày trên nền tảng **Vue 3 + Vite + Pinia**, bản thân cơ chế chia nhỏ Single-File Components (`.vue`) đã giúp tiết kiệm **60% – 75% token** so với HTML/JS thuần. Để đẩy mức tiết kiệm lên tối đa (**75% – 90%**), hãy áp dụng 8 chiến thuật đặc thù sau:

1. **Tận Dụng Tối Đa Lợi Thế "Khoanh Vùng Component" (`Component Isolation`):**
   - **Quy chuẩn kích thước:** Giữ mỗi file `.vue` gọn gàng dưới **250 – 400 dòng** (tách các khối lớn như Biểu đồ, Bảng, Thẻ KPI thành các sub-component độc lập như `Tab1ChartsPanel.vue`, `TopKpiGrid.vue`, `AppHeader.vue`).
   - **Chỉ đích danh file `.vue` khi ra lệnh:** Kết hợp với `@docs/CODEBASE_MAP.md`, khi cần sửa giao diện phần nào chỉ yêu cầu AI mở đúng file `.vue` của phần đó (~150–300 dòng, tốn ~600 token) thay vì đọc toàn bộ trang (tốn ~25.000 token).

2. **Tách Bạch Rạch Ròi 3 Tầng: "Tính Toán Thuần (Engine) – Trạng Thái (Pinia) – Hiển Thị (`.vue`)":**
   - **Tuyệt đối không nhét công thức toán học phức tạp vào trong `<script setup>` của file `.vue`:**
     - **Tầng 1 (`src/engine/*.js`):** Chứa 100% logic nghiệp vụ và toán học thuần túy (Pure Functions), độc lập với Vue và DOM. Khi sửa công thức thuế/lương hưu, AI chỉ đọc và sửa trong `engine.js` hoặc `taxOptimizer.js` rồi chạy kiểm thử bằng Node.js trong 0.1 giây.
     - **Tầng 2 (`src/stores/*.js`):** Pinia Store (`plan.js`, `i18n.js`, `modals.js`) làm cầu nối quản lý state và `computed`.
     - **Tầng 3 (`src/components/*.vue`):** Chỉ đảm nhiệm hiển thị (`{{ planStore.activePlan.xxx }}`) và bắt sự kiện (`@click`, `v-model`).
   - **Lợi ích:** Sửa thuật toán không cần đọc file giao diện `.vue`; sửa giao diện `.vue` không cần đọc file thuật toán `.js`.

3. **Khóa Chặt `node_modules/` và `dist/` Trong `.antigravityignore`:**
   - Trong dự án Vue/Vite, `node_modules/` chứa hàng chục nghìn file và `dist/` chứa các file bundle đã nén (`index-xxx.js` dài hàng vạn ký tự trên 1 dòng). Chỉ 1 lần đọc nhầm vào `dist/` sẽ đốt sạch **40.000 – 100.000 token**.
   - Bắt buộc duy trì trong `.antigravityignore`:
     ```text
     frontend-vue/node_modules/
     frontend-vue/dist/
     *.min.js
     package-lock.json
     ```

4. **Kiểm Tra Cú Pháp `.vue` Bằng `./verify_js.sh` & `vite build` Thay Vì Mở Browser:**
   - **Không gọi `browser_subagent`** (tốn 40.000 – 90.000 token) chỉ để xem trang Vue có bị lỗi template hay trắng trang không.
   - **Cách chuẩn tốn ~200 token (0.5 giây):**
     1. Chạy `./verify_js.sh` để kiểm tra cú pháp, chạy test kịch bản Mock DOM và tự động cập nhật tọa độ dòng của mọi file `.vue` vào `docs/CODEBASE_MAP.md` (tốn 0 token).
     2. Chạy `npm --prefix frontend-vue run build`: Trình biên dịch `vite build` sẽ bắt chính xác 100% mọi lỗi đóng/mở thẻ `<template>`, lỗi biến trong `<script setup>` và lỗi đường dẫn `import`.
     3. Tận dụng **Vite HMR (Hot Module Replacement)** tại `http://localhost:5174/` để xem kết quả cập nhật tức thì trên trình duyệt đang mở sẵn của bạn.

5. **Ưu Tiên Viết Code Khai Báo Phản Ứng (`Declarative Reactivity`) Với Pinia Store:**
   - Khi làm tính năng mới trong Vue, sử dụng `v-model`, `:class`, `v-if`, `v-for` và `computed` từ Pinia Store (`usePlanStore()`, `useI18nStore()`, `useModalStore()`) thay vì viết hàng trăm dòng lệnh DOM thủ công (`document.getElementById(...).addEventListener(...)`).
   - Giúp giảm **50% – 60% số dòng code** cần viết và giảm một nửa lượng output token AI phải sinh ra.

6. **Dùng Script Node.js Khi Cần Tách Component `.vue` Lớn (`Scripted Refactoring`):**
   - Khi một file `.vue` vượt quá 800–1.000 dòng và cần tách thành các component con, tuyệt đối không để AI dùng `write_file` xuất lại hàng nghìn dòng HTML (tốn hàng chục nghìn output token).
   - Yêu cầu AI dùng 1 lệnh `node -e "..."` cắt theo tọa độ dòng (`lines.slice(...)`) từ file gốc sang các file `.vue` con chỉ trong **0.05 giây** (tiết kiệm 95% output token, chính xác tuyệt đối).

7. **Thiết Kế Component Mới Độc Lập Trước Khi Ghép Vào Luồng Chính:**
   - **Bước 1 (~300 token):** Bảo AI vẽ **ASCII Wireframe** trong chat để chốt bố cục và danh sách `props` / `store` cần dùng.
   - **Bước 2 (~1.000 token):** Tạo 1 component `.vue` mới với dữ liệu mẫu để ngắm trực tiếp qua Vite HMR trên `localhost:5174`.
   - **Bước 3:** Khi đã ưng ý 100% bố cục, yêu cầu AI nối hàm tính toán trong `src/engine/` và thêm từ điển `vi / en / fr` vào `src/engine/i18n.js` trong 1 lượt duy nhất.

8. **Kỷ Luật Phiên Chat ("1 Component/Nhiệm Vụ = 1 Chat Mới" + Prompt Batching):**
   - **Đóng bớt các tab file `.vue` / `.js` không còn dùng trên IDE** để tránh IDE tự động đính kèm metadata vào mỗi lượt chat.
   - **Gộp yêu cầu (Prompt Batching):** Gom 3–5 chỉnh sửa nhỏ trên cùng 1 file `.vue` vào một danh sách đánh số `1, 2, 3...` và gửi 1 lần.
   - **Bấm `New Chat (+)` hoặc gõ `/compact`** ngay sau khi hoàn thành 1 component hoặc khi hội thoại chạm ngưỡng **10 – 12 lượt**.

- **Mẫu Câu Lệnh (Prompt) Chuẩn Tiết Kiệm Token Nhất Khi Làm Việc Với Vue Hàng Ngày (Copy & Paste):**
  ```text
  Đọc @docs/CODEBASE_MAP.md để định vị dòng code.
  Hãy thực hiện trong frontend-vue/src/components/tabs/[Tên_File.vue] các chỉnh sửa sau:
  1. [Yêu cầu 1...]
  2. [Yêu cầu 2...]
  3. Bổ sung từ điển đa ngôn ngữ (vi/en/fr) tương ứng vào frontend-vue/src/engine/i18n.js trong 1 lượt.
  Kiểm tra bằng ./verify_js.sh, không mở browser_subagent.
  ```




