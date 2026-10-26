# Kế Hoạch Tính Năng: Mở Rộng Hồ Sơ Người Dùng Đa Chiều Qua Popup `+ Mới` (`#plan-modal`) & Tự Động Quy Đổi Chi Tiêu Hưu Trí Từ Số Dư Hàng Tháng (`multi_country_ppp_expansion.md`)

> **Quy trình Thực Thi Tiết Kiệm Token (Theo Chuẩn [`docs/QUY_TRINH_PHAT_TRIEN_APP_BANG_ANTIGRAVITY.md`](file:///Users/canhhung/Documents/pyRetrait/docs/QUY_TRINH_PHAT_TRIEN_APP_BANG_ANTIGRAVITY.md)):**
> 1. **Giai đoạn 1 & 2 (Đã chốt & đóng băng thiết kế — Scope Freeze):**
>    - **Định hình Hồ sơ ngay tại Popup `+ Mới` (`#plan-modal` — Dòng 3386 – 3595 trong `frontend/index.html`):**  
>      Đã chốt khung HTML tĩnh chuẩn phong cách tối giản:
>      - **Kế hoạch này dành cho:** `Cá nhân` (1 người) | `Vợ chồng` (2 người).
>      - **Bố cục Side-by-Side & Cấu trúc Dropdown 2 Lớp Tinh Gọn:**
>        - `Nơi làm việc hiện tại` và `Nơi dự định nghỉ hưu` đặt song song cạnh nhau với mũi tên chuyển đổi ở giữa.
>        - **Quy chuẩn hiển thị 2 lớp (2-Layer Dropdown Hierarchy):**
>          * **Lớp 1 (Nhóm cha `<optgroup>`):** `[Cờ quốc gia] + [Tên quốc gia]` (ví dụ: `🇫🇷 Pháp`, `🇻🇳 Việt Nam`, `🇵🇹 Bồ Đào Nha`, `🇪🇸 Tây Ban Nha`, `🇩🇪 Đức`, `🇺🇸 Mỹ`...).
>          * **Lớp 2 (Lựa chọn con `<option>`):** Chỉ hiển thị `[Khu vực] ([Tỷ lệ PPP])`, tuyệt đối không lặp lại cờ quốc gia hay tên nước (ví dụ: `Paris & Vùng Thủ Đô (1.00x)`, `Tỉnh lẻ (0.85x)`, `Lisbon / Porto (0.65x)`, `Algarve / Tỉnh lẻ (0.55x)`).
>      - **Quy tắc bắt buộc:** Khi chọn `Chỉ 1 nơi`, Nơi nghỉ hưu tự động bằng Nơi làm việc hiện tại (`retireCity = workCity` và bị khóa/disabled), mũi tên đổi thành `=`.
>    - **Ưu tiên số 1 (Mặc định):** Tự động suy ra mức chi tiêu hưu trí từ chính **Thu nhập & Số dư tiết kiệm hàng tháng hiện tại của người dùng** (`Chi tiêu sinh hoạt thực tế = Thu nhập sau thuế - Tiết kiệm đầu tư - Trả góp nợ nhà`), sau đó quy đổi theo tỷ lệ Sức mua tương đương (`PPP nơi nghỉ hưu / PPP nơi làm việc`) và cộng phí bảo hiểm y tế tuổi già.
>    - **Thước đo đối chiếu trực quan (Chỉ đọc — Không phải nút bấm):** Hiển thị dòng tham chiếu 3 mốc xã hội (`Cơ bản 1.600€ | Thoải mái 2.400€ | Thịnh vượng 4.000€ × PPP`) dưới dạng chỉ báo tĩnh trên Tab 1 để người dùng đối chiếu phân khúc sống tại nơi nghỉ hưu.
> 2. **Giai đoạn 3 (Thực thi từng Task cuốn chiếu):**  
>    Sau khi duyệt tài liệu này, người dùng mở phiên chat mới và ra lệnh:  
>    *"Dựa vào file `docs/plans/multi_country_ppp_expansion.md`, hãy thực hiện **Task [N]**. Chỉ dùng `replace_file_content` sửa đúng dòng đã chỉ định trong `docs/CODEBASE_MAP.md`."*
> 3. **Quy chuẩn Kiểm thử Tiết kiệm Token (Non-negotiable Testing Rule):**
>    - Mặc định chỉ kiểm tra giao diện và tính năng trên ngôn ngữ chính là **Tiếng Việt (`vi`)**.
>    - Bản dịch tiếng Anh (`en`) và tiếng Pháp (`fr`) được bảo đảm bằng kiểm tra tĩnh (static code inspection) trong từ điển `i18n.js`. Tuyệt đối không ra lệnh cho browser subagent/tester chuyển qua lại giữa các ngôn ngữ (`VI -> EN -> FR`) trong cùng một phiên test để tránh lãng phí token và thời gian.

---

## 1. Mục Tiêu & Ràng Buộc Kỹ Thuật (Dựa Trên [`PROJECT_BLUEPRINT.md`](file:///Users/canhhung/Documents/pyRetrait/PROJECT_BLUEPRINT.md))

- **Mục tiêu nghiệp vụ**:
  1. **Thiết lập Hồ sơ trong Popup `+ Mới` (`#plan-modal`) để tự động tối ưu Giao diện**:
     - Cấu hình Side-by-Side tinh gọn:
       1. **Kế hoạch này dành cho:** `Cá nhân` (1 người) hoặc `Vợ chồng` (2 người).
       2. **Định hướng không gian sống:** `Chỉ 1 nơi` | `Chuyển hẳn` | `Song hành (50/50)`.
       3. **Bố cục Side-by-Side song song (Dropdown 2 lớp chuẩn mực):**
          - Lớp 1 (Nhóm cha `<optgroup>`): Cờ quốc gia + Tên nước (`🇫🇷 Pháp`, `🇻🇳 Việt Nam`, `🇵🇹 Bồ Đào Nha`, `🇪🇸 Tây Ban Nha`, `🇩🇪 Đức`, `🇺🇸 Mỹ`...).
          - Lớp 2 (Lựa chọn con `<option>`): Khu vực/Thành phố + Tỷ lệ PPP (`Lisbon / Porto (0.65x)`, `Tỉnh lẻ (0.55x)`...).
     - **Quy chuẩn hiển thị thẻ theo Quốc gia & Thẻ Chung Toàn Cầu (Country-Specific vs Global Cards):**
       * **1. Nhóm Thẻ Đặc Thù Theo Nơi Làm Việc & Nơi Nghỉ Hưu (`Country-Specific Pension Cards`):**
         - Khi người dùng chọn **Nơi làm việc (`workCountry`)**, thẻ lương hưu nước sở tại của nơi đó sẽ tự động xuất hiện (ví dụ: làm việc tại Pháp ➔ hiện thẻ *Lương hưu Pháp*; làm việc tại Việt Nam ➔ hiện thẻ *Lương hưu BHXH Việt Nam*; làm việc tại Đức ➔ hiện thẻ *Lương hưu Đức*; Mỹ ➔ *Lương hưu Social Security*...).
         - **Trường hợp Nơi làm việc KHÁC Nơi nghỉ hưu (`workCountry !== retireCountry`)**: Hệ thống **TỰ ĐỘNG BẬT CẢ HAI THẺ LƯƠNG HƯU Ở HAI NƠI**.
           * Ví dụ: Đi làm ở Pháp (`FR`), về hưu ở Việt Nam (`VN`) ➔ Bật cả **Thẻ Lương hưu Pháp** (quyền lợi tích lũy năm tháng đi làm) VÀ **Thẻ Lương hưu BHXH Việt Nam** (đóng tự nguyện hoặc tiếp nối tại quê hương).
           * Mỗi thẻ này được thiết kế và tính toán riêng biệt cho từng nơi theo luật hưu trí sở tại.
         - **Trường hợp Nơi làm việc CÙNG Nơi nghỉ hưu (`workCountry === retireCountry` hoặc `retireMode === 'domestic'`)**: Chỉ bật **1 thẻ lương hưu duy nhất** của nước đó, ẩn thẻ hưu trí của các nước khác; đồng thời tự động ẩn thẻ *Lạm phát 2 chặng & Tỷ giá* (`#card-dual-inflation-stream`) và ẩn cụm 3 radio *Pháp / Việt / Song hành*.
       * **2. Nhóm Thẻ Chung Toàn Cầu — Luôn Luôn Hiển Thị Cho Mọi Quốc Gia (`Global Shared Cards`):**
         - Các thẻ nền tảng tài chính và gia đình sau đây là thẻ chung toàn cầu, **LUÔN LUÔN HIỂN THỊ** đối với tất cả mọi hồ sơ người dùng (bất kể làm việc hay nghỉ hưu ở Pháp, Việt Nam, Đức, Mỹ hay bất kỳ quốc gia nào):
           1. **Kế hoạch Nuôi con** (`#card-children-family-stream`): Chi phí nuôi con và đại học tự động quy đổi theo hệ số PPP của thành phố sở tại.
           2. **Chi tiêu/tháng khi về hưu** (`#card-retire-expense-stream`): Tự động tính từ dòng tiền hiện tại (Thu nhập - Tiết kiệm - Nợ nhà), áp dụng PPP và bảng bóc tách 7 nhóm chi tiêu.
           3. **Dự phòng Chăm sóc Tuổi Già (78t+)** (`#card-senior-care-stream`): Chi phí điều dưỡng và hỗ trợ sinh hoạt cuối đời theo PPP.
           4. **Kế Hoạch Thừa Kế & Di Sản** (`#card-estate-legacy-combined`): Hoạch định di sản chuyển giao cho thế hệ sau.
           5. **Danh mục đầu tư & Bất động sản** (`#card-asset-allocation-stream` + `#card-lmnp-income-stream` / Căn hộ cho thuê): Quản lý tài sản sinh lời và dòng tiền thuê nhà toàn cầu.
           6. **Chiến Lược Rút Tiền Hưu Trí** (`#card-withdrawal-strategy-controls`): 4 chiến lược rút vốn chuẩn khoa học (Bengen 4%, Guyton-Klinger, VPW, Fixed %).
  2. **Công thức Mặc định: Tính Chi tiêu Hưu trí từ Số dư Hàng tháng Hiện tại (`Cashflow-Derived Retirement Spending`)**:
     - `Chi tiêu sinh hoạt hiện tại/tháng = Thu nhập sau thuế/tháng - Số tiền tiết kiệm đầu tư/tháng - Tiền trả góp mua nhà/tháng (đã trả xong trước khi nghỉ hưu)`
     - `Chi tiêu hưu trí dự kiến/tháng = Chi tiêu sinh hoạt hiện tại/tháng * Hệ_số_PPP + Phụ phí Y tế tuổi già`
     - Hiển thị kèm dòng tham chiếu tĩnh (`Cơ bản | Thoải mái | Thịnh vượng × PPP` — chỉ để xem, không bấm) và bảng bóc tách 7 hạng mục chi tiêu trên Tab 1.
  3. **Đồng bộ Thuế, Lương hưu & Miễn trừ cho cả Cá nhân lẫn Vợ chồng**:
     - Khi chọn **Vợ chồng (`married`)**: Tự động chia phần thuế hộ gia đình (`taxParts = 2.0`), nhân đôi hạn mức rút lãi miễn thuế (**Assurance-Vie `9.200 EUR/năm`**, **Sparer-Pauschbetrag `2.000 EUR/năm`**), và tính tổng lương hưu từ cả 2 nguồn thu nhập của vợ & chồng.
     - **Nguyên Tắc Thiết Kế Trực Quan — Luôn Luôn Hiển Thị Trực Tiếp (Show Mọi Thứ Ngay Trên Giao Diện, Tuyệt Đối Không Giấu Sau Nút Sửa / Không Dùng Modal Phụ):**
       - **Hiển thị trực tiếp (Inline UI), không popup/modal che khuất:**
         * Toàn bộ thông số cấu hình và tính toán đều được **hiển thị trực tiếp ngay trên giao diện Tab 1**. Người dùng không cần phải bấm nút `[Sửa]` hay mở bất kỳ hộp thoại Modal phụ nào mới thấy hoặc sửa được dữ liệu.
       - **Hiển thị chi tiết theo Hồ sơ Cá nhân / Vợ chồng:**
         * **Khi chọn Cá nhân (`single`):** Các thẻ lương hưu hiển thị 1 khối thông số trực tiếp (Tuổi bắt đầu đi làm, Tuổi hưởng hưu, Giới tính, Số năm đóng bảo hiểm).
         * **Khi chọn Vợ chồng (`married`):** Các thẻ lương hưu (Lương hưu Pháp CNAV/Agirc-Arrco và BHXH Việt Nam) tự động bung nở / hiển thị trực tiếp 2 cột hoặc 2 khối song song cho **Bạn (Người 1)** và **Bạn đời (Người 2)**:
           - **Lương hưu Pháp:** Ô nhập Tuổi bắt đầu đi làm (`startWorkAge`), Tuổi nhận hưu (`claimAge`), Mức lương tính hưu của từng người hiển thị ngay trên thẻ. Người dùng thấy ngay số quý đóng (`trimestres`), tỷ lệ phạt/thưởng décote và số tiền lương hưu độc lập của từng người + tổng lương hưu gia đình. Chỉnh sửa trực tiếp ngay trên thẻ, số liệu cập nhật tức thì.
           - **Lương hưu BHXH Việt Nam:** Ô chọn Giới tính (`Nam` chuẩn 35 năm = 75% / `Nữ` chuẩn 30 năm = 75%), Số năm đóng (`yearsContributed`), Mức lương đóng của Chồng và Vợ hiển thị ngay trên thẻ.
       - **Bóc tách chi tiêu & Đối chiếu PPP luôn mở sẵn:**
         * Khung giải thích công thức từ Số dư hàng tháng, dòng tham chiếu 3 mức sống (`Cơ bản | Thoải mái | Thịnh vượng × PPP`) và bảng bóc tách 7 hạng mục chi tiêu thiết yếu luôn luôn hiển thị trực quan (visible by default), không giấu trong các accordion hay dropdown đóng.

- **Ràng buộc kỹ thuật bất biến (Theo [`PROJECT_BLUEPRINT.md`](file:///Users/canhhung/Documents/pyRetrait/PROJECT_BLUEPRINT.md) Mục 2 & 3)**:
  - **Local-First 100%**: Mọi phép tính tài chính, Monte Carlo, thuế và hưu trí phải chạy 100% trên JavaScript client, không gọi API backend để tính toán.
  - **Tab 3 là nội dung tĩnh thuần túy (Static Guide / Reference)**: Chỉ hiển thị cẩm nang pháp lý, tối ưu thuế, mẹo tài khoản đầu tư và infographic tĩnh; tuyệt đối không gắn các logic tính toán động hay can thiệp vào dòng tiền tính toán ngầm. Toàn bộ logic tính toán tài chính cốt lõi tập trung 100% tại Core Engine (`engine.js`, `taxOptimizer.js`) và tương tác trực quan trên Tab 1.
  - **Hệ thống giao diện kép (Dual-Theme)**: Hỗ trợ 100% Dark Mode và Light Mode qua biến CSS (`var(--bg-card)`, `var(--text-main)`, `var(--text-muted)`). Tuyệt đối không hardcode màu nền tối cố định hoặc màu chữ xám nhạt làm mất độ tương phản.
  - **Typography & Biểu thức**: Thống nhất font `var(--font-sans)` (Inter) cho toàn bộ văn bản và công thức. Tuyệt đối không dùng cú pháp LaTeX.
  - **Nguyên tắc phân chia file & chống phình file**: Mỗi Task chỉ sửa tối đa **2–3 file** và xác thực ngay bằng `./verify_js.sh`.

---

## 2. Tổng Quan Các File & Tọa Độ Dòng Cần Thay Đổi (Cập Nhật Chuẩn Xác Theo [`docs/CODEBASE_MAP.md`](file:///Users/canhhung/Documents/pyRetrait/docs/CODEBASE_MAP.md))

| Task | File tác động (Tối đa 2–3 file/Task) | Khoảng dòng hiện tại trong `CODEBASE_MAP.md` | Nội dung nâng cấp |
| :--- | :--- | :--- | :--- |
| **Task 1** [x] | `frontend/js/taxOptimizer.js` | Dòng `1 – 747` | Bổ sung `COUNTRY_PPP_PROFILES` (22+ khu vực), hàm `calculateRetireBudgetFromCashflow()` (tính từ Thu nhập - Tiết kiệm - Trả góp nhà), thước đo tham chiếu 3 mức sống, chia thuế theo `taxParts` & lương hưu tham số hóa cho cả 2 vợ chồng |
| **Task 2** [x] | `frontend/js/state.js`<br>`frontend/js/engine.js`<br>`frontend/js/ui.js` | Dòng `99 – 339`<br>Dòng `525 – 1354`<br>Dòng `752 – 881` | Chuẩn hóa schema Hồ sơ theo Blueprint (`workCountry`, `retireMode`, `retireCountry`, `retireCity`, `maritalStatus`, `taxParts`), chế độ 1 quốc gia (`isSingleCountry`), gộp lương hưu độc lập 2 vợ chồng và đồng bộ Cloud preferences (`theme`, `lang`, `currency`, `viewMode`) |
| **Task 3** [x] | `frontend/index.html`<br>`frontend/js/ui-modals.js`<br>`frontend/js/ui.js` | Dòng `3386 – 3595`<br>Dòng `1022 – 1215`<br>Dòng `255 – 353` | Hoàn thiện đấu nối DOM cho `#plan-modal` (lưu profile đa quốc gia & gia đình, đồng bộ select khi chọn Chỉ 1 nơi) |
| **Task 4** [x] | `frontend/index.html`<br>`frontend/js/ui-tab1-streams.js` | Dòng `410 – 745`, `1067 – 1280`, `1573 – 1695`<br>Dòng `878 – 903`, `1540 – 1649` | Tự động ẩn/hiện thẻ theo Hồ sơ (`applyProfileVisibilityRules`), hiển thị trực tiếp (inline, không popup) cấu hình Bạn & Bạn đời trên thẻ hưu trí khi chọn Vợ chồng; công thức chi tiêu từ Số dư + dòng tham chiếu tĩnh & bảng 7 khoản chi luôn mở sẵn |
| **Task 5** [x] | `frontend/js/i18n.js`<br>`frontend/js/engine.js`<br>`frontend/index.html` | Dòng `21 – 620`<br>Dòng `9 – 47`<br>Dòng `27`, `4850 – 4896` | Bổ sung đầy đủ bản dịch (`vi`, `en`, `fr`), hỗ trợ tiền tệ `CNY`, xóa file nháp `frontend/preview.html` và tăng query version cache-busting `?v=...` trên `index.html` |
| **Task 6** [ ] | `frontend/index.html`<br>`frontend/js/taxOptimizer.js`<br>`frontend/js/engine.js`<br>`frontend/js/ui-tab1-streams.js` | Dòng `579 – 745`<br>Dòng `220 – 450`<br>Dòng `600 – 750`<br>Dòng `1640 – 1760` | Xây dựng **thẻ hưu trí riêng biệt chuẩn luật cho từng quốc gia** (`#card-french-pension-stream`, `#card-bhxh-income-stream`, `#card-german-pension-stream`, `#card-us-pension-stream`), tuyệt đối không dùng thẻ chung đoán mò khi chưa có dữ liệu chuẩn; hiển thị thông báo minh bạch hướng dẫn tự nhập thu nhập tùy chỉnh cho các nước chưa hỗ trợ; tích hợp engine dòng tiền và nhân chi phí nuôi con theo PPP |
| **Task 7** [ ] | `frontend/js/ui-tab3-taxes.js`<br>`frontend/js/ui-tab2-health.js`<br>`frontend/js/i18n.js` | Dòng `470 – 550`<br>Dòng `580 – 660`, `1270 – 1320`<br>Dòng `25 – 650` | Tab 3 tự động chuyển biểu thuế nước sở tại và ẩn tài khoản đặc thù Pháp (PEA/AV) thay bằng tài khoản quốc tế; Tab 2 chuẩn hóa y tế tuổi già và bỏ trợ cấp CAF Pháp; đa ngôn ngữ |

---

## 3. Phân Tích Rủi Ro Logic & Trường Hợp Biên (Edge Cases)

- **Trường hợp 1 — Người dùng chọn `"Chỉ 1 nơi (Ở lại nơi làm việc)"` (`retireMode === 'domestic'`)**:
  - Hệ thống tự động gán `retireCountry = workCountry`, `retireCity = workCity`, `dualInflation.enabled = false`, `forexDrift = 0`.
  - Trên popup `#plan-modal`: Ô *Nơi dự định nghỉ hưu* tự động nhận giá trị của *Nơi làm việc hiện tại* và bị khóa mờ (`disabled`), mũi tên đổi thành `=`.
  - Trên giao diện Tab 1: Tự động **ẩn** thẻ `#card-dual-inflation-stream` (Lạm phát 2 chặng & Tỷ giá) và **ẩn** cụm `#retire-location-radios` (3 nút Pháp / Việt / Song hành), giúp giao diện dành cho người sống ở 1 nơi cực kỳ tinh gọn.
- **Trường hợp 2 — Người dùng chọn `"Song hành 2 nơi (50% nơi làm việc / 50% nơi nghỉ hưu)"` (`retireMode === 'hybrid'`)**:
  - Hệ số PPP áp dụng bằng trung bình cộng: `pppEffective = 0.5 * pppWork + 0.5 * pppRetire` (cộng thêm dự phòng vé máy bay khứ hồi hàng năm trong nhóm Giải trí/Đi lại).
  - Mũi tên giữa 2 cột hiển thị biểu tượng `⇄`.
- **Trường hợp 3 — Khấu trừ khoản trả góp mua nhà (`monthlyMortgagePaidOff`) khi bước vào tuổi nghỉ hưu**:
  - Công thức `calculateRetireBudgetFromCashflow()` tự động trừ khoản trả góp ngân hàng mua nhà sẽ tất toán trước tuổi nghỉ hưu ra khỏi chi tiêu hiện tại trước khi quy đổi PPP.
- **Trường hợp 4 — Tương thích ngược với Kế hoạch cũ (Backward Compatibility)**:
  - Khi nạp kế hoạch cũ từ `localStorage` hoặc SQLite chưa có các trường mới, `ensurePlanDefaults(plan)` trong `state.js` tự động bổ sung giá trị mặc định an toàn: `maritalStatus: 'single'`, `taxParts: 1.0`, suy luận `workCountry` và `retireCountry` từ `taxRegime` hoặc `retireLocation`.

### Bảng Ma Trận Hiển Thị Thẻ Giao Diện Theo Nơi Làm Việc & Nơi Nghỉ Hưu

| Kịch Bản Thiết Lập | Thẻ Lương Hưu Nước Làm Việc | Thẻ Lương Hưu Nước Nghỉ Hưu | Thẻ Lạm Phát Kép (`#card-dual-inflation-stream`) | Nhóm Thẻ Chung Toàn Cầu (Con Cái, Chi Tiêu Hưu Trí, Chăm Sóc Tuổi Già, Thừa Kế, Danh Mục Đầu Tư, Chiến Lược Rút) |
| :--- | :--- | :--- | :--- | :--- |
| **Làm Pháp ➔ Nghỉ Pháp** (`FR ➔ FR`) | 🇫🇷 **HIỆN** (Lương hưu Pháp) | — (Trùng nhau) | ❌ **ẨN** | ✅ **LUÔN HIỂN THỊ 100%** |
| **Làm VN ➔ Nghỉ VN** (`VN ➔ VN`) | 🇻🇳 **HIỆN** (BHXH Việt Nam) | — (Trùng nhau) | ❌ **ẨN** | ✅ **LUÔN HIỂN THỊ 100%** |
| **Làm Pháp ➔ Nghỉ VN** (`FR ➔ VN`) | 🇫🇷 **HIỆN** (Lương hưu Pháp) | 🇻🇳 **HIỆN** (BHXH Việt Nam)<br>*(Bật cả 2 thẻ)* | ✅ **HIỆN** | ✅ **LUÔN HIỂN THỊ 100%** |
| **Làm VN ➔ Nghỉ Pháp** (`VN ➔ FR`) | 🇻🇳 **HIỆN** (BHXH Việt Nam) | 🇫🇷 **HIỆN** (Lương hưu Pháp)<br>*(Bật cả 2 thẻ)* | ✅ **HIỆN** | ✅ **LUÔN HIỂN THỊ 100%** |
| **Làm Đức ➔ Nghỉ VN** (`DE ➔ VN`) | 🇩🇪 **HIỆN** (Lương hưu Đức) | 🇻🇳 **HIỆN** (BHXH Việt Nam)<br>*(Bật cả 2 thẻ)* | ✅ **HIỆN** | ✅ **LUÔN HIỂN THỊ 100%** |
| **Làm Mỹ ➔ Nghỉ VN** (`US ➔ VN`) | 🇺🇸 **HIỆN** (Social Security) | 🇻🇳 **HIỆN** (BHXH Việt Nam)<br>*(Bật cả 2 thẻ)* | ✅ **HIỆN** | ✅ **LUÔN HIỂN THỊ 100%** |
| **Quốc tế khác ➔ Quốc tế khác** | 🌐 **HIỆN** (Hưu trí nước làm việc) | 🌐 **HIỆN** (Hưu trí nước nghỉ hưu) | ✅ **HIỆN** (nếu khác nước) | ✅ **LUÔN HIỂN THỊ 100%** |

> **Nguyên tắc cốt lõi bất di bất dịch:**
> 1. Đi làm ở đâu thì thẻ lương hưu nước đó xuất hiện.
> 2. Nếu nơi làm việc KHÁC nơi nghỉ hưu thì **BẬT CẢ HAI THẺ LƯƠNG HƯU Ở HAI NƠI**. Mỗi thẻ được thiết kế riêng biệt cho mỗi nơi (Pháp: quý đóng/décote; VN: năm đóng/luật BHXH; Đức: Rentenpunkte; Mỹ: Bend Points...).
> 3. Các thẻ chung: Con cái, Chi tiêu/tháng khi về hưu, Dự phòng Chăm sóc Tuổi Già (78t+), Kế Hoạch Thừa Kế, Danh mục đầu tư & BĐS, Chiến Lược Rút Tiền Hưu Trí là **THẺ CHUNG LUÔN HIỂN THỊ** cho mọi quốc gia.

---

## 4. Danh Sách Công Việc Cuốn Chiếu (Actionable Tasks)

### [x] Task 1 — Xây dựng Công Thức Quy Đổi Chi Tiêu Từ Số Dư Hàng Tháng & Ma Trận PPP 22+ Quốc Gia (`frontend/js/taxOptimizer.js`)

- **File cần sửa**:
  1. `frontend/js/taxOptimizer.js` (Toàn bộ file 469 dòng, bổ sung các hằng số và hàm mới).
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - Dòng `1 – 36`: Khai báo **Giỏ chuẩn gốc Tây Âu (`BASE_RETIRE_BASKET_EUR = { lean: 1600, standard: 2400, fat: 4000, seniorHealth: 180 }`)** và bảng `COUNTRY_PPP_PROFILES` cho **22+ quốc gia/khu vực trọng điểm** kèm tùy chọn `custom`.
  - Dòng `37 – 221` (`calculateProgressiveTax` và `calculateTaxDetailed`):
    - Hỗ trợ chia thu nhập chịu thuế theo số phần gia đình `taxParts` (`options.taxParts || 1.0`).
    - Hỗ trợ **4 Khuôn mẫu Thuế Toàn cầu (`taxArchetype`)**: `'fr_quotient'`, `'eu_splitting'`, `'asia_pacific'`, `'zero_cgt'`.
  - Dòng `222 – 333`:
    - Bổ sung hàm cốt lõi số 1: **`calculateRetireBudgetFromCashflow(params)`** — tính chi tiêu hưu trí trực tiếp từ Thu nhập, Số dư tiết kiệm hàng tháng và Nợ vay mua nhà hiện tại (hỗ trợ cả 3 chế độ `retireMode`: `'domestic'`, `'relocate'`, `'hybrid'`).
    - Bổ sung hàm số 2: **`getSuggestedRetirementBudget(cityKey, lifestyleTier, householdSize, customPppFactor)`** — trả về 3 mốc tham chiếu xã hội chỉ đọc (`1.600€ / 2.400€ / 4.000€ × PPP`) để đối chiếu và bóc tách 7 hạng mục chi tiêu.
    - Cập nhật hàm số 3: **`calculateFrenchPension(averageSalary, startWorkAge, stopWorkAge, claimAge)`** — tính chính xác số quý đóng (`trimestres`), phạt décote (-1.25%/quý thiếu nếu claim < 67t) và tự động xóa phạt ở tuổi 67 theo luật Pháp 2023. Khi là Vợ chồng, hàm được gọi độc lập cho từng người (`spouse1`, `spouse2`) với tuổi bắt đầu đi làm riêng biệt rồi cộng gộp quyền lợi.
    - Bổ sung hàm số 4: **`calculateVietnamBhxhPension(salaryVnd, yearsContributed, gender = 'male', claimAge)`** — phân định chuẩn xác theo luật BHXH Việt Nam:
      * **Nam:** 20 năm đầu = 45%, mỗi năm sau +2% ➔ Cần 35 năm để đạt 75% tối đa, tuổi hưởng lộ trình 62 tuổi.
      * **Nữ:** 15 năm đầu = 45%, mỗi năm sau +2% ➔ Cần 30 năm để đạt 75% tối đa, tuổi hưởng lộ trình 60 tuổi.
      * Khi là Vợ chồng: Chồng mặc định nhận quyền lợi Nam (62t), Vợ nhận quyền lợi Nữ (60t).
- **Công thức & Logic Đầu vào – Đầu ra**:
  1. **Công thức Chính: `calculateRetireBudgetFromCashflow(params)`**:
     - **Đầu vào (`params`)**:
       - `monthlyNetIncome`: Thu nhập ròng sau thuế hàng tháng hiện tại (EUR).
       - `monthlySavings`: Số dư tiết kiệm / đầu tư hàng tháng hiện tại (EUR).
       - `monthlyMortgagePaidOff`: Tiền trả góp mua nhà hàng tháng hiện tại sẽ trả xong trước khi nghỉ hưu (EUR, mặc định `0`).
       - `currentMonthlyLivingFallback`: Chi tiêu sinh hoạt hiện tại nếu người dùng nhập trực tiếp (EUR).
       - `workCityKey`: Mã nơi đang làm việc (ví dụ `'fr_paris'`, `pppWork = 1.00`).
       - `retireCityKey`: Mã nơi dự định nghỉ hưu (ví dụ `'vn_hcm_hn'`, `pppRetire = 0.45`).
       - `retireMode`: `'domestic'` (Ở lại 1 nơi) | `'relocate'` (Chuyển hẳn sang nơi nghỉ hưu) | `'hybrid'` (Song hành 50/50 giữa 2 nơi).
       - `householdSize`: `1` (Cá nhân) hoặc `2` (Vợ chồng).
     - **Các bước tính toán**:
       - `Bước 1 (Chi tiêu sinh hoạt thực tế hiện tại - currentLivingMonthly)`:
         Nếu `monthlyNetIncome > monthlySavings`:
         `currentLivingMonthly = max(500, monthlyNetIncome - monthlySavings - monthlyMortgagePaidOff)`
         Ngược lại: dùng `currentMonthlyLivingFallback`.
       - `Bước 2 (Quy đổi tương đương sức mua sang nơi nghỉ hưu - pppAdjustedLiving)`:
         - Nếu `retireMode === 'domestic'`: `effectivePpp = pppWork`, `pppRatio = 1.0`.
         - Nếu `retireMode === 'hybrid'`: `effectivePpp = 0.5 * pppWork + 0.5 * pppRetire`, `pppRatio = effectivePpp / pppWork`.
         - Nếu `retireMode === 'relocate'` (mặc định khi `workCityKey !== retireCityKey`): `effectivePpp = pppRetire`, `pppRatio = pppRetire / pppWork`.
         - `pppAdjustedLiving = Làm tròn(currentLivingMonthly * pppRatio)`
       - `Bước 3 (Cộng Bảo hiểm Y tế tuổi già)`:
         `seniorHealthAddon = Làm tròn(180 * effectivePpp * (householdSize >= 2 ? 1.90 : 1.0))`
         `monthlyRetireTotal = pppAdjustedLiving + seniorHealthAddon`
     - **Đầu ra**: Trả về `{ currentLivingMonthly, pppRatio, effectivePpp, pppAdjustedLiving, seniorHealthAddon, monthlyRetireTotal, annualRetireTotal: monthlyRetireTotal * 12, matchedTierLabel, referenceBenchmarks: { lean, standard, fat }, breakdown }`.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "({ fromCashflowParis: window.TaxOptimizer.calculateRetireBudgetFromCashflow({ monthlyNetIncome: 3200, monthlySavings: 1000, monthlyMortgagePaidOff: 700, workCityKey: 'fr_paris', retireCityKey: 'fr_paris', retireMode: 'domestic', householdSize: 1 }), fromCashflowVN: window.TaxOptimizer.calculateRetireBudgetFromCashflow({ monthlyNetIncome: 3200, monthlySavings: 1000, monthlyMortgagePaidOff: 700, workCityKey: 'fr_paris', retireCityKey: 'vn_hcm_hn', retireMode: 'relocate', householdSize: 1 }) })"
  ```
  - *Kết quả kỳ vọng*: `fromCashflowParis.currentLivingMonthly === 1500`, `fromCashflowParis.monthlyRetireTotal === 1680`, `fromCashflowVN.monthlyRetireTotal === 756`.

---

### [x] Task 2 — Chuẩn hóa Hồ sơ Người dùng & Đồng Bộ Đám Mây Toàn Bộ Biến (`Theme`, `Ngôn ngữ`, `Tiền tệ`, `Profile`) Khi Đăng Nhập (`state.js`, `engine.js`, `ui.js`)

- **File cần sửa**:
  1. `frontend/js/state.js` (Dòng `99 – 275`, các hàm `savePlansToStorage`, `loadInitialPlans` & hàm bổ sung `ensurePlanDefaults`).
  2. `frontend/js/engine.js` (Dòng `525 – 1298`, hàm `runProjection`).
  3. `frontend/js/ui.js` (Dòng `752 – 877`, các hàm `setCurrency`, `toggleTheme`, `loadTheme`, `reloadPlansFromBackend`).
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - `frontend/js/state.js` dòng `99 – 140` (`savePlansToStorage` & `debouncedSavePlansToStorage`):
    - **Lưu kèm `preferences` vào gói JSON đồng bộ lên Cloud (`/api/plans`)**: Trước khi lưu vào `localStorage` và gửi `POST /api/plans` lên SQLite backend, tự động đính kèm đối tượng `state.plansData.preferences`:
      ```javascript
      state.plansData.preferences = {
        lang: localStorage.getItem('pyretrait_lang') || 'vi',
        theme: localStorage.getItem('pyRetrait_theme') || document.documentElement.getAttribute('data-theme') || 'dark',
        currency: state.currency || 'EUR',
        viewMode: state.viewMode || 'nominal'
      };
      ```
    - **Khôi phục tự động khi tải dữ liệu / Đăng nhập (`applySavedUserPreferences(plansData)`)**: Khi `loadInitialPlans()` hoặc `reloadPlansFromBackend()` nhận dữ liệu từ `/api/plans` của tài khoản vừa đăng nhập, nếu có `plansData.preferences`, hệ thống tự động:
      1. Khôi phục **Theme (`dark` / `light`)**: Cập nhật `localStorage.setItem('pyRetrait_theme', pref.theme)`, đặt `document.documentElement.setAttribute('data-theme', pref.theme)` và đổi icon Mặt trời/Mặt trăng.
      2. Khôi phục **Ngôn ngữ (`vi` / `en` / `fr`)**: Cập nhật `localStorage.setItem('pyretrait_lang', pref.lang)` và gọi `window.I18n.setLanguage(pref.lang)`.
      3. Khôi phục **Đơn vị tiền tệ (`EUR` / `VND` / `USD` / `CNY`)** và **Chế độ xem (`nominal` / `real`)**.
    - Bổ sung hàm `ensurePlanDefaults(plan)` để tự động di trú an toàn theo `Plan Schema` tại Mục 4 của Blueprint:
      - `workCountry`: `'FR'`, `workCity`: `'fr_paris'`
      - `retireMode`: `'relocate'` (`'domestic' | 'relocate' | 'hybrid'`)
      - `retireCountry`: `'VN'`, `retireCity`: `'vn_hcm_hn'`
      - `maritalStatus`: `'single'` (`'single' | 'married'`), `taxParts`: `1.0`
      - `monthlyMortgagePaidOff`: `0`
      - `frenchPensionDetails`: `{ spouse1: { startWorkAge: 24, claimAge: 64, targetAnnualPension: 18000 }, spouse2: { startWorkAge: 24, claimAge: 64, targetAnnualPension: 16000 } }`
      - `bhxhVnDetails`: `{ spouse1: { gender: 'male', yearsContributed: 20, monthlySalaryVnd: 10000000, claimAge: 62 }, spouse2: { gender: 'female', yearsContributed: 20, monthlySalaryVnd: 10000000, claimAge: 60 } }`
  - `frontend/js/ui.js` dòng `752 – 877`:
    - Trong `toggleTheme()`, `setCurrency()`, `setViewMode()`: Gọi `debouncedSavePlansToStorage()` để lưu preferences lên Cloud.
    - Trong `reloadPlansFromBackend()`: Gọi `applySavedUserPreferences(state.plansData)` ngay sau khi đăng nhập thành công.
  - `frontend/js/engine.js` dòng `525 – 1298` (trong hàm `runProjection`):
    - Xác định `isSingleCountry = (plan.retireMode === 'domestic' || (plan.workCountry && plan.retireCountry && plan.workCountry === plan.retireCountry))` và `isSingle = (plan.maritalStatus !== 'married')`.
    - Nếu `isSingleCountry === true`: Đặt `forexDrift = 0` (không trượt tỷ giá ngoại tệ).
    - Truyền `taxParts: Number(plan.taxParts) || (isSingle ? 1.0 : 2.0)` vào `window.TaxOptimizer.calculateProgressiveTax`.
    - **Tính lương hưu độc lập & cộng gộp chính xác:** Khi `maritalStatus === 'married'`, tính lương hưu Pháp/BHXH theo tuổi bắt đầu đi làm và giới tính Nam/Nữ của từng người (`spouse1`, `spouse2`), sau đó cộng gộp vào dòng tiền an sinh của gia đình (`annualIncome += pensionSpouse1 + pensionSpouse2`).
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "(() => { const p = { currentAge: 30, retirementAge: 50, lifeExpectancy: 85, workCountry: 'FR', retireMode: 'domestic', retireCountry: 'FR', maritalStatus: 'married', taxParts: 2.0, currentSavings: 100000, annualSavings: 20000, retirementExpenses: 29760 }; const res = window.RetirementEngine.runProjection(p); return { survived: res.survived, isSingleCountry: res.isSingleCountry, finalPortfolio: Math.round(res.finalPortfolio) }; })()"
  ```

---

### [x] Task 3 — Đấu Nối Sự Kiện & Lưu Trữ Cho Popup `#plan-modal` (`frontend/js/ui-modals.js` & `frontend/index.html`)

- **File cần sửa**:
  1. `frontend/index.html` (Dòng `3386` đổi `style="display: flex;"` thành `style="display: none;"` sau khi hoàn thành kiểm tra bố cục; Dòng `255 – 270` chèn thanh `#profile-summary-bar` vào đầu `#tab-projections`).
  2. `frontend/js/ui-modals.js` (Dòng `1022 – 1070`, các hàm `openModal`, `saveNewPlanFromModal`).
  3. `frontend/js/ui.js` (Dòng `354 – 532`, hàm `renderActivePlanInputs` cập nhật dữ liệu hiển thị trên `#profile-summary-bar`).
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - `frontend/index.html` dòng `3386 – 3595`: Khung HTML của `#plan-modal` đã có sẵn. Đóng mở modal qua class/display.
  - `frontend/index.html` dòng `255 – 270` (ngay đầu `#tab-projections` trước `#baseline-params-card`): Thêm thanh tóm tắt Hồ sơ `#profile-summary-bar` sử dụng class `.profile-summary-bar` đã có sẵn trong `styles.css` (dòng 8887–8930):
    ```html
    <div class="profile-summary-bar" id="profile-summary-bar">
      <div class="profile-summary-info">
        <span class="profile-tag-pill" id="lbl-summary-household">👤 Cá nhân (1 người)</span>
        <span class="profile-tag-pill" id="lbl-summary-locations">🇫🇷 Paris ➔ 🇻🇳 TP.HCM</span>
        <span class="profile-tag-pill" id="lbl-summary-mode">Chuyển hẳn (PPP 0.45x)</span>
      </div>
      <button class="btn btn-secondary btn-sm" id="btn-edit-profile-summary" style="font-size: 0.78rem; padding: 0.25rem 0.65rem;">
        ⚙️ Đổi hồ sơ
      </button>
    </div>
    ```
  - `frontend/js/ui-modals.js` dòng `1029 – 1068`:
    - Hàm `openModal(title, mode = 'create')`:
      - Nếu `mode === 'edit'`: Tải giá trị hiện tại của `getActivePlan()` vào các ô (`#inp-new-plan-name`, `#inp-plan-work-city`, `#inp-plan-retire-city`, các nút chọn gia đình và định hướng nơi sống).
      - Nếu `mode === 'create'`: Đặt các giá trị mặc định.
      - Gắn sự kiện chuyển đổi giữa các nút bấm `btn-plan-fam-*`, `btn-plan-mode-*`.
      - Khi chọn `btn-plan-mode-domestic`: Tự động khóa `inp-plan-retire-city` và đồng bộ bằng `inp-plan-work-city`.
    - Hàm `saveNewPlanFromModal()`:
      - Đọc `household` (`single` / `married`), `taxParts` (`1.0` / `2.0`).
      - Đọc `retireMode` (`domestic` / `relocate` / `hybrid`).
      - Đọc `workCity`, `workCountry`, `retireCity`, `retireCountry`.
      - Tự động gọi `calculateRetireBudgetFromCashflow()` để cập nhật ngân sách hưu trí cho kế hoạch.
      - Gọi `savePlansToStorage()`, `renderPlanSelector()`, `updateAll()`.
  - `frontend/js/ui.js` dòng `168 – 289`: Bắt sự kiện click vào nút `#btn-edit-profile-summary` để gọi `window.openModal('Chỉnh sửa Hồ sơ & Quốc gia', 'edit')`.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "typeof window.saveNewPlanFromModal === 'function' && typeof window.openModal === 'function'"
  ```

---

### [x] Task 4 — Hiển Thị Trực Tiếp Toàn Bộ Thông Số (Inline Show All, Không Cần Nút Sửa) & Tự Động Ẩn/Hiện Thẻ Theo Hồ Sơ (`frontend/index.html` & `frontend/js/ui-tab1-streams.js`)

- **File cần sửa**:
  1. `frontend/index.html` (Dòng `489 – 745`: thẻ Lương hưu Pháp và BHXH VN; Dòng `1067 – 1280`: thẻ Chi tiêu hưu trí).
  2. `frontend/js/ui-tab1-streams.js` (Dòng `878 – 903`, `1540 – 1649`).
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - **Nguyên tắc Hiển thị Trực tiếp — Show Mọi Thứ Ngay Trên Giao Diện (Inline Show All):**
    * Thẻ *Thông số Cơ bản & Dòng tiền* (`.baseline-params-card`): Giữ nguyên 5 cột chuẩn (Năm sinh, Tuổi nghỉ hưu, Kỳ vọng tuổi thọ, Tài sản hiện có, Lạm phát bình quân).
    * Cột *Các Luồng Thu Nhập* — **Cấu hình Lương hưu hiển thị trực tiếp, tuyệt đối không giấu sau nút Sửa hay Popup/Modal:**
      - **Khi `plan.maritalStatus === 'single'` (Cá nhân):** Thẻ lương hưu hiển thị 1 khối cấu hình trực tiếp ngay trên mặt thẻ (Tuổi bắt đầu đi làm, Tuổi nhận hưu, Giới tính, Số năm đóng bảo hiểm).
      - **Khi `plan.maritalStatus === 'married'` (Vợ chồng):** Thẻ lương hưu tự động hiển thị trực tiếp 2 khối/cột song song cho **Bạn (Người 1)** và **Bạn đời (Người 2)**:
        * **Lương hưu Pháp (CNAV + Agirc-Arrco):** Hiển thị trực tiếp ô nhập Tuổi bắt đầu đi làm (`startWorkAge`), Tuổi claim (`claimAge`) của từng người. Người dùng nhìn thấy ngay số quý đóng (`trimestres`), tỷ lệ phạt/thưởng décote, số tiền lương hưu riêng của từng người và tổng lương hưu gia đình. Có thể chỉnh sửa trực tiếp ngay trên thẻ, số liệu cập nhật tức thì.
        * **Lương hưu BHXH Việt Nam:** Hiển thị trực tiếp chọn Giới tính (`Nam`/`Nữ`), Số năm đóng (`yearsContributed`), Mức lương đóng của Chồng và Vợ ngay trên mặt thẻ.
  - `frontend/index.html` dòng `1067 – 1280` (trong `#card-retire-expense-stream`):
    - Hiển thị hộp giải thích tự động **"Tính từ mức sống hiện tại của bạn (Thu nhập - Số dư tiết kiệm)"** (`#box-cashflow-derived-retire`):
      Hiển thị rõ phép tính: `Thu nhập ròng/tháng - Tiết kiệm/tháng - Nợ nhà tất toán = Chi tiêu hiện tại ➔ × Hệ số PPP = Chi tiêu hưu trí`.
    - Bên dưới là **dòng tham chiếu tĩnh (Read-only, chỉ để xem đối chiếu)** (`#lbl-ppp-static-benchmarks`):
      `Mốc tham khảo tại [Thành phố]: Cơ bản ~X €/tháng • Thoải mái ~Y €/tháng • Thịnh vượng ~Z €/tháng`.
    - **Bảng bóc tách 7 khoản chi tiêu thực tế hàng tháng (`#box-ppp-breakdown-detail`):** Luôn luôn hiển thị mở sẵn (show all by default), không cần bấm click mở/đóng hay giấu trong accordion. Người dùng nhìn thấy ngay chi tiết từng nhóm chi phí (Ăn uống, Nhà ở, Y tế, Năng lượng, Đi lại, Đồ gia dụng, Giải trí/Giao lưu).
  - `frontend/js/ui-tab1-streams.js` dòng `1640 – 1760` (hàm `applyProfileVisibilityRules(plan)`):
    1. **Nhóm Thẻ Đặc Thù Theo Quốc Gia (Country-Specific Cards)**:
       - **Thẻ theo Nơi làm việc (`workCountry`)**: Xuất hiện thẻ lương hưu của quốc gia nơi làm việc (làm việc ở Pháp ➔ hiện `#card-french-pension-stream`; làm việc ở VN ➔ hiện `#card-bhxh-income-stream`).
       - **Khi Nơi làm việc KHÁC Nơi nghỉ hưu (`workCountry !== retireCountry`)**:
         * **Tự động BẬT CẢ HAI THẺ LƯƠNG HƯU Ở HAI NƠI** (`cardFrench.style.display = ""`, `cardBhxh.style.display = ""`). Mỗi thẻ được thiết kế riêng biệt cho từng nơi theo luật hưu trí và công thức đặc thù.
         * Bật thẻ *Lạm phát 2 chặng & Tỷ giá* (`#card-dual-inflation-stream`) và cụm 3 radio *Pháp / Việt / Song hành*.
       - **Khi Nơi làm việc CÙNG Nơi nghỉ hưu (`workCountry === retireCountry` hoặc `retireMode === 'domestic'`)**:
         * Chỉ hiển thị **1 thẻ lương hưu duy nhất** của quốc gia đó, ẩn thẻ của các nước khác.
         * Ẩn hoàn toàn thẻ *Lạm phát 2 chặng & Tỷ giá* (`#card-dual-inflation-stream`) và cụm 3 radio.
    2. **Nhóm Thẻ Chung Toàn Cầu — Luôn Luôn Hiển Thị Cho Mọi Quốc Gia (Global Shared Cards)**:
       - Tất cả 6 thẻ chung sau đây được thiết lập `display = ""` vĩnh viễn, không bao giờ bị ẩn:
         * **Bất Động Sản Cho Thuê** (`#card-lmnp-income-stream` / Doanh thu BĐS & Quản lý Căn hộ): Lớp tài sản đầu tư chung toàn cầu.
         * **Danh mục đầu tư & Phân bổ tài sản** (`#card-asset-allocation-stream`).
         * **Chi tiêu/tháng khi về hưu** (`#card-retire-expense-stream`): Đi kèm công thức tính từ Số dư + dòng tham chiếu tĩnh & bảng 7 nhóm chi tiêu.
         * **Kế hoạch Nuôi con** (`#card-children-family-stream`).
         * **Dự phòng Chăm sóc Tuổi Già (78t+)** (`#card-senior-care-stream`).
         * **Kế Hoạch Thừa Kế & Di Sản** (`#card-estate-legacy-combined`).
         * **Chiến Lược Rút Tiền Hưu Trí** (`#card-withdrawal-strategy-controls`).
    3. Tự động gọi `window.TaxOptimizer.calculateRetireBudgetFromCashflow()` để cập nhật chi tiêu hưu trí, dòng tham chiếu tĩnh và bảng 7 khoản chi tiêu.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "Object.keys(window.TaxOptimizer.COUNTRY_PPP_PROFILES).slice(0, 6).map(k => ({ city: k, fromCashflow: window.TaxOptimizer.calculateRetireBudgetFromCashflow({ monthlyNetIncome: 3500, monthlySavings: 1300, monthlyMortgagePaidOff: 0, workCityKey: 'fr_paris', retireCityKey: k, retireMode: 'relocate', householdSize: 1 }).monthlyRetireTotal }))"
  ```

---

### [x] Task 5 — Mở Rộng Đa Ngôn Ngữ (`vi`, `en`, `fr`), Tiền Tệ `CNY`, Dọn Dẹp File Nháp & Cache-Busting (`frontend/js/i18n.js`, `frontend/js/engine.js`, `frontend/index.html`)

- **File cần sửa / xóa**:
  1. `frontend/js/i18n.js` (Bổ sung khóa dịch cho popup hồ sơ và công thức cho `vi`, `en`, `fr`).
  2. `frontend/js/engine.js` (Hỗ trợ tiền tệ `'CNY'`).
  3. `frontend/index.html` (Tăng query version cache-busting `?v=...`).
  4. Xóa file nháp tạm `frontend/preview.html` nếu tồn tại.
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - `frontend/js/i18n.js` dòng `21 – 620`: Bổ sung từ điển dịch cho các chuỗi mới của popup hồ sơ, thanh tóm tắt và bảng bóc tách chi tiêu cho cả 3 ngôn ngữ (`vi`, `en`, `fr`).
  - `frontend/js/engine.js` dòng `9 – 47`: Hỗ trợ mã tiền tệ `'CNY'` (`¥`) trong `formatCurrency()`.
  - `frontend/index.html` dòng `27` và `4850 – 4896`: Tăng query version `?v=...` cho `styles.css` và các file JS đã sửa để tránh cache trình duyệt.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "({ eur: window.RetirementEngine.formatCurrency(1600, 'EUR'), cny: window.RetirementEngine.formatCurrency(12000, 'CNY'), vnd: window.RetirementEngine.formatCurrency(25000000, 'VND') })"
  ```

---

### [x] Task 6 — Mở Rộng Hệ Thống Thẻ Lương Hưu Riêng Biệt Chuẩn Luật (Đức, Mỹ) & Nguyên Tắc Minh Bạch Khi Chưa Có Dữ Liệu (`frontend/index.html`, `frontend/js/taxOptimizer.js`, `frontend/js/engine.js`, `frontend/js/ui-tab1-streams.js`)

- **File cần sửa**:
  1. `frontend/index.html` (Thêm khối HTML thẻ chuyên biệt cho Đức, Mỹ ngay dưới các thẻ Pháp và BHXH VN; thêm khối thông báo minh bạch khi quốc gia chưa có dữ liệu hưu trí tự động).
  2. `frontend/js/taxOptimizer.js` (Bổ sung công thức tính lương hưu chuyên sâu chuẩn luật cho Đức, Mỹ).
  3. `frontend/js/engine.js` (Tích hợp nguồn lương hưu an sinh tương ứng theo quốc gia vào dòng tiền `runProjection`).
  4. `frontend/js/ui-tab1-streams.js` (Bổ sung render, ràng buộc sự kiện cho từng thẻ và cập nhật `applyProfileVisibilityRules` để bật/tắt thẻ độc lập theo `workCountry`/`retireCountry`).
- **Danh Sách Các Thẻ Hưu Trí Chuyên Biệt Từng Quốc Gia (Dedicated Country Pension Cards)**:
  1. 🇫🇷 **`#card-french-pension-stream`**: Thẻ Lương hưu Pháp (CNAV + Agirc-Arrco, Quý đóng trimestres, Phạt décote).
  2. 🇻🇳 **`#card-bhxh-income-stream`**: Thẻ Lương hưu BHXH Việt Nam (Chuẩn 35 năm Nam / 30 năm Nữ = 75%, Quỹ lương VND).
  3. 🇩🇪 **`#card-german-pension-stream`**: Thẻ Lương hưu Đức (*Gesetzliche Rentenversicherung* — Hệ thống Điểm Rentenpunkte `RP`, Tuổi chuẩn 67t, Phạt nhận sớm -3.6%/năm, Giá trị điểm Rentenwert ~39.32€).
  4. 🇺🇸 **`#card-us-pension-stream`**: Thẻ Lương hưu Mỹ (*Social Security SSA* — AIME bình quân 35 năm, 3 bậc tỷ lệ cong Bend Points, Tuổi chuẩn FRA 67t).
- **Nguyên Tắc Minh Bạch Khi Chưa Có Dữ Liệu Hưu Trí Chuẩn (Anti-Hallucination & Financial Accuracy)**:
  - **Tuyệt đối KHÔNG sử dụng thẻ chung / công thức generic phỏng đoán**: Đối với các quốc gia chưa được nghiên cứu và lập trình đầy đủ luật an sinh (ví dụ Bồ Đào Nha, Tây Ban Nha, Thái Lan, Singapore, Úc, Canada...), hệ thống **tuyệt đối không áp dụng tỷ lệ đoán mò** vì sẽ làm sai lệch nghiêm trọng kế hoạch tài chính của người dùng.
  - **Khối thông báo minh bạch `#callout-pension-unsupported`**:
    * Khi `workCountry` thuộc quốc gia chưa có thẻ hưu trí chuyên biệt, hệ thống ẩn toàn bộ các thẻ lương hưu tự động và hiển thị một khối thông báo trang nhã, minh bạch:  
      *"pyRetrait hiện chưa có mô hình tính toán lương hưu tự động theo luật của [Tên Quốc Gia]. Bạn có thể ước tính riêng và bổ sung trực tiếp khoản lương hưu này vào danh sách Luồng Thu Nhập tùy chỉnh bằng nút `[+ Thêm Thu Nhập]` bên dưới."*
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - `frontend/index.html` dòng `579 – 745`:
    - Tạo các thẻ độc lập với cấu trúc HTML đồng nhất, có hỗ trợ hiển thị 2 cột (Bạn & Bạn đời khi chọn Vợ chồng):
      * Thẻ hưu trí Đức `#card-german-pension-stream`
      * Thẻ hưu trí Mỹ `#card-us-pension-stream`
      * Khối thông báo minh bạch `#callout-pension-unsupported`
  - `frontend/js/taxOptimizer.js` dòng `220 – 450`:
    - **Công thức Lương hưu Đức (`calculateGermanPension`)**:
      * Chuẩn hưu trí luật Đức (*Gesetzliche Rentenversicherung*):
      * Điểm hưu trí tích lũy hàng năm: `Rentenpunkte (RP) = Lương_gross_hàng_năm / Thu_nhập_bình_quân_toàn_quốc` (năm 2024 bình quân ~45.358 EUR/năm).
      * Tuổi nghỉ hưu chuẩn (*Regelaltersgrenze*): 67 tuổi. Nhận sớm tối thiểu từ 63 tuổi: mỗi tháng nhận sớm bị giảm `0.3%` (`-3.6%/năm`). Nhận muộn sau 67 tuổi: mỗi tháng được thưởng `+0.5%` (`+6.0%/năm`).
      * Giá trị 1 điểm hưu trí (*Aktueller Rentenwert*): ~39.32 EUR/tháng.
      * `Lương hưu tháng = Tổng_RP * Hệ_số_tuổi_nhận * 39.32 EUR`.
    - **Công thức Lương hưu An sinh Mỹ (`calculateUsSocialSecurityPension`)**:
      * Chuẩn An sinh Xã hội Mỹ (*Social Security Administration*):
      * Thu nhập bình quân 35 năm làm việc có đóng thuế FICA (tính theo tháng - AIME).
      * Công thức tính mức hưởng chuẩn tại tuổi hưu tròn (Primary Insurance Amount - PIA) theo 3 bậc tỷ lệ cong (Bend Points 2024: $1.174 và $7.078):
        - Bậc 1: 90% phần AIME đến $1.174.
        - Bậc 2: 32% phần AIME từ $1.174 đến $7.078.
        - Bậc 3: 15% phần AIME vượt $7.078.
      * Tuổi hưu chuẩn (*Full Retirement Age - FRA*): 67 tuổi. Nhận sớm từ 62 tuổi giảm tối đa 30%; nhận muộn đến 70 tuổi tăng 8%/năm.
  - `frontend/js/engine.js` dòng `600 – 750` (trong hàm `runProjection`):
    - Tích hợp đúng dòng tiền lương hưu từ thẻ quốc gia tương ứng (Pháp, Đức, Mỹ, Việt Nam) vào tổng thu nhập an sinh hưu trí của kế hoạch. Nếu là quốc gia khác, không tự cộng nguồn lương hưu giả định.
  - `frontend/js/ui-tab1-streams.js` dòng `1640 – 1760` (hàm `applyProfileVisibilityRules`):
    - **Cơ chế Ẩn/Hiện Thẻ Độc Lập Theo Nơi Làm Việc & Nơi Nghỉ Hưu**:
      * Ẩn tất cả các thẻ lương hưu mặc định (`display = "none"`).
      * **Bật thẻ nước làm việc (`workCountry`)**:
        - Nếu `workCountry === 'FR'`: Hiện `#card-french-pension-stream`.
        - Nếu `workCountry === 'DE'`: Hiện `#card-german-pension-stream`.
        - Nếu `workCountry === 'US'`: Hiện `#card-us-pension-stream`.
        - Nếu `workCountry === 'VN'`: Hiện `#card-bhxh-income-stream`.
        - Nếu thuộc quốc gia khác: Hiện thông báo minh bạch `#callout-pension-unsupported`.
      * **Bật thêm thẻ nước nghỉ hưu nếu khác nước làm việc (`workCountry !== retireCountry`)**:
        - Nếu nghỉ hưu ở VN (`retireCountry === 'VN'`) và làm việc ở nước ngoài: Tự động BẬT THÊM `#card-bhxh-income-stream`.
        - Nếu làm việc ở VN và nghỉ hưu ở nước ngoài: Tự động BẬT THÊM thẻ hưu trí tương ứng của nước nghỉ hưu (nếu là Pháp, Đức, Mỹ).
    - **Nhóm Thẻ Chung Toàn Cầu — Luôn Luôn Hiển Thị Cho Mọi Quốc Gia**:
      * Con cái (`#card-children-family-stream`), Chi tiêu/tháng khi về hưu (`#card-retire-expense-stream`), Dự phòng Chăm sóc Tuổi Già (78t+) (`#card-senior-care-stream`), Kế Hoạch Thừa Kế (`#card-estate-legacy-combined`), Danh mục đầu tư & BĐS (`#card-asset-allocation-stream` + `#card-lmnp-income-stream`), Chiến Lược Rút Tiền Hưu Trí (`#card-withdrawal-strategy-controls`) là các thẻ chung toàn cầu luôn luôn hiển thị.
    - **Khi chọn Hồ sơ Cá nhân (`plan.maritalStatus === 'single'`)**:
      * Tất cả các thẻ lương hưu chỉ hiển thị 1 cột duy nhất của Bạn (ẩn cột Bạn đời).
    - **Chi phí Kế hoạch Nuôi con**:
      * Chi phí nuôi con và học phí đại học tự động nhân với hệ số PPP của thành phố nước sở tại (`targetCityProfile.ppp`).
      * Ẩn hoàn toàn khoản trợ cấp gia đình CAF Pháp khi `plan.workCountry !== 'FR'`.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "({ dePension: window.TaxOptimizer.calculateGermanPension(60000, 35, 67), usPension: window.TaxOptimizer.calculateUsSocialSecurityPension(80000, 35, 67) })"
  ```

---

### [x] Task 7 — Thích Ứng Thuế Nước Sở Tại, Thay Thế Tài Khoản Đầu Tư Quốc Tế & Y Tế Tuổi Già Trung Tính (`frontend/js/ui-tab3-taxes.js`, `frontend/js/ui-tab2-health.js`, `frontend/js/i18n.js`, `frontend/index.html`)

- **File cần sửa**:
  1. `frontend/js/ui-tab3-taxes.js` (Tự động thích ứng biểu thuế và ẩn các thẻ tài khoản đặc thù của Pháp, thay bằng tài khoản quốc tế).
  2. `frontend/js/ui-tab2-health.js` (Chuẩn sinh học Nam, ẩn bạn đời khi độc thân, chi phí y tế theo PPP nước sở tại và bỏ trợ cấp CAF Pháp).
  3. `frontend/js/i18n.js` (Cập nhật từ điển dịch `vi`, `en`, `fr`).
  4. `frontend/index.html` (Tăng query version `?v=...` cache-busting).
- **Tọa độ dòng code theo `CODEBASE_MAP.md`**:
  - `frontend/js/ui-tab3-taxes.js` dòng `470 – 550` (hàm `updateTaxRegimeUI`):
    - Tự động phát hiện quốc gia của kế hoạch (`plan.workCountry` / `plan.retireCountry`):
      * Nếu ở Mỹ (`US`): Tự động áp dụng biểu thuế Liên bang Mỹ (`us`), hiển thị thông tin về tài khoản hưu trí 401(k), Roth IRA, HSA.
      * Nếu ở Đức (`DE`) hoặc Châu Âu khác: Tự động áp dụng biểu thuế nước sở tại / thuế phẳng quốc tế.
      * Nếu ở Pháp (`FR`): Giữ nguyên biểu thuế IR Pháp và cơ chế Quotient Familial.
    - **Ẩn các thẻ đặc thù của Pháp khi `plan.workCountry !== 'FR'`**:
      * Ẩn `#card-pea-masterclass` (PEA Pháp).
      * Ẩn `#card-assurance-vie-masterclass` (Bảo hiểm nhân thọ AV Pháp).
      * Ẩn `#card-livret-masterclass` (Sổ tiết kiệm Livret A Pháp).
      * Hiển thị thẻ Danh mục Tài khoản Đầu tư Quốc tế / Nước sở tại thay thế.
  - `frontend/js/ui-tab2-health.js` dòng `580 – 660`, `1270 – 1320`:
    - **Bảo đảm chuẩn sinh học theo giới tính**:
      * Khi `plan.gender === 'male'`: Áp dụng chuẩn sinh học Nam 👨 (vòng eo < 90cm, mỡ máu, chỉ số cơ xương, testosterone), kỳ vọng tuổi thọ chuẩn nam giới.
    - **Bố cục Cá nhân**:
      * Khi `plan.maritalStatus === 'single'`: Ẩn toàn bộ thẻ so sánh song song Bạn đời, chỉ hiển thị cột chỉ số của Bạn.
    - **Chi phí Chăm sóc Y tế Tuổi già (sau 78 tuổi)**:
      * Sử dụng chi phí cơ sở `healthCostBase` của nước sở tại từ `COUNTRY_PPP_PROFILES` (Đức 200€, Thụy Sĩ 350€, Mỹ 300$, Bồ Đào Nha 140€...).
      * Sử dụng ngôn ngữ y tế chuẩn mực, trung tính và phổ thông đại chúng: không nhắc BHYT Pháp (Sécurité Sociale/Mutuelle) hay BHXH Việt Nam khi ở nước khác.
    - **Nuôi con & Trợ cấp**:
      * Bỏ nhãn và dòng tính trợ cấp CAF Pháp khi `plan.workCountry !== 'FR'`.
  - `frontend/js/i18n.js` dòng `25 – 650`:
    - Bổ sung các bản dịch đầy đủ cho 3 ngôn ngữ (`vi`, `en`, `fr`) về lương hưu nước sở tại (Đức, Mỹ, Quốc tế), tài khoản đầu tư quốc tế và các nhãn liên quan.
  - `frontend/index.html` dòng `27` và cuối trang:
    - Tăng query version `?v=...` cho các file stylesheet và script.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "typeof window.TaxOptimizer.calculateGermanPension === 'function' && typeof window.updateTaxRegimeUI === 'function'"
  ```

---

## 5. Nguồn Dữ Liệu PPP & Cơ Chế Cập Nhật Tự Động Định Kỳ (World Bank API, Numbeo & Cache Sync)

### 5.1. Bản Chất Dữ Liệu Thống Kê PPP
- **Dữ liệu Vĩ mô Quốc tế (World Bank / ICP)**: 
  - Chỉ số: `PA.NUS.PRVT.PP` (*PPP conversion factor, private consumption*) do Ngân Hàng Thế Giới khảo sát và công bố.
  - **Chu kỳ công bố:** Thống kê theo **NĂM** (Annual), **không có số liệu theo tháng** do quá trình khảo sát rổ hàng hóa toàn cầu mất nhiều thời gian.
- **Dữ liệu Cấp Thành phố & Hưu trí Thực tế (Numbeo / Expatistan / Eurostat)**:
  - World Bank đo bình quân toàn quốc. Trong thực tế nghỉ hưu, mức chi phí tại các thành phố lớn (Paris, TP.HCM, Hà Nội, New York) chênh lệch lớn so với vùng nông thôn hoặc tỉnh lẻ.
  - Vì vậy, hệ số PPP trong pyRetrait lấy mốc gốc là **Pháp (Paris = 1.00)** kết hợp giữa tỷ lệ giá tiêu dùng thực tế của **Numbeo** (*Cost of Living Plus Rent Index*) và mức giá so sánh của **Eurostat/OECD**.

---

### 5.2. Cách Khai Thác Trực Tiếp World Bank REST API (Miễn Phí 100%, Không Cần API Key)

- **Endpoint chính thức**:
  `https://api.worldbank.org/v2/country/{MÃ_QUỐC_GIA}/indicator/PA.NUS.PRVT.PP?mrv=1&format=json`
  - Tham số `mrv=1` (*Most Recent Value*): Tự động lấy số liệu năm mới nhất đã công bố.
  - Ví dụ gọi nhiều quốc gia cùng lúc:
    `https://api.worldbank.org/v2/country/FRA;VNM;DEU;USA;ESP;PRT;THA;MYS;SGP;JPN/indicator/PA.NUS.PRVT.PP?mrv=1&format=json`
- **Cấu trúc JSON trả về từ World Bank**:
  ```json
  [
    { "page": 1, "pages": 1, "total": 10 },
    [
      { "countryiso3code": "FRA", "date": "2023", "value": 0.81 },
      { "countryiso3code": "VNM", "date": "2023", "value": 7850.25 },
      { "countryiso3code": "DEU", "date": "2023", "value": 0.79 },
      { "countryiso3code": "USA", "date": "2023", "value": 1.00 }
    ]
  ]
  ```

---

### 5.3. Hai Phương Án Tự Động Hóa Cập Nhật Định Kỳ (Bảo Đảm Nguyên Tắc Local-First)

Vì pyRetrait bắt buộc phải chạy 100% offline và không bắt người dùng phải chờ API ngoài mỗi khi tải trang, việc cập nhật định kỳ được tổ chức theo 2 giải pháp:

#### Phương án A: Tự Động Kiểm Tra & Cache Trên Trình Duyệt (Frontend LocalStorage Sync — 30 Ngày/Lần)
Khi người dùng mở ứng dụng có kết nối mạng, trình duyệt kiểm tra thời gian đồng bộ lần cuối. Nếu đã quá 30 ngày, hệ thống tự động fetch ngầm trong background và lưu cache:

```javascript
async function syncWorldBankPppIfExpired() {
  const CACHE_KEY = 'pyretrait_wb_ppp_cache';
  const lastSync = localStorage.getItem('pyretrait_wb_ppp_last_sync');
  const now = Date.now();
  const THIRTY_DAYS = 30 * 24 * 60 * 60 * 1000;

  if (lastSync && (now - Number(lastSync) < THIRTY_DAYS)) {
    return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');
  }

  try {
    const url = 'https://api.worldbank.org/v2/country/FRA;VNM;DEU;USA;ESP;PRT;THA/indicator/PA.NUS.PRVT.PP?mrv=1&format=json';
    const res = await fetch(url);
    const data = await res.json();
    if (data && data[1]) {
      const pppMap = {};
      data[1].forEach(row => {
        if (row.value) pppMap[row.countryiso3code] = row.value;
      });
      localStorage.setItem(CACHE_KEY, JSON.stringify(pppMap));
      localStorage.setItem('pyretrait_wb_ppp_last_sync', String(now));
      return pppMap;
    }
  } catch (err) {
    console.warn('Không thể kết nối World Bank API, sử dụng bảng cấu hình tĩnh.', err);
  }
  return null;
}
```

#### Phương án B: Script Python Trên Backend / Cron Job Hàng Tháng (`scripts/fetch_worldbank_ppp.py`)
Định kỳ hàng tháng, một cron job đơn giản chạy ngầm tải dữ liệu mới nhất từ World Bank API và chốt vào bảng cấu hình:

```python
import urllib.request
import json

url = "https://api.worldbank.org/v2/country/FRA;VNM;DEU;USA;ESP;PRT;THA;MYS;SGP;JPN/indicator/PA.NUS.PRVT.PP?mrv=1&format=json"
req = urllib.request.Request(url, headers={'User-Agent': 'pyRetrait-Sync/1.0'})

with urllib.request.urlopen(req) as response:
    raw_data = json.loads(response.read().decode())[1]

ppp_data = {item['countryiso3code']: item['value'] for item in raw_data if item.get('value')}
print("Dữ liệu PPP World Bank mới nhất:", ppp_data)
```

---

### 5.4. Ma Trận Bảng Giá Tham Chiếu Mặc Định (`COUNTRY_PPP_PROFILES`)
Bảng tĩnh dự phòng tích hợp sẵn trong `frontend/js/taxOptimizer.js` (gốc Pháp Paris = 1.00):
- **Pháp & Tây Âu**: Paris (`1.00`), Tỉnh lẻ Pháp (`0.82`), Đức (`0.95`), Bỉ (`0.92`), Thụy Sĩ (`1.45`), Anh (`1.10`).
- **Nam Âu (Thiên đường hưu trí)**: Bồ Đào Nha (`0.65`), Tây Ban Nha (`0.62`), Ý (`0.78`), Hy Lạp (`0.58`).
- **Bắc Mỹ & Châu Đại Dương**: Mỹ NY/SF (`1.25`), Mỹ Texas/Florida (`0.95`), Canada (`0.98`), Úc (`1.05`).
- **Đông Nam Á & Châu Á**: Việt Nam TP.HCM/Hà Nội (`0.45`), Đà Nẵng/Tỉnh lẻ (`0.36`), Thái Lan (`0.50`), Malaysia (`0.46`), Singapore (`1.20`), Trung Quốc (`0.58`), Nhật Bản (`0.85`).
- **Tùy chỉnh cá nhân**: `custom` (Mặc định `1.00`, cho phép người dùng tự nhập hệ số hoặc số tiền thực tế).
