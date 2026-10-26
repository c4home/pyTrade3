# Kế Hoạch Nâng Cấp: Đồng Bộ Sức Khỏe – Tài Chính & Chuẩn Hóa Logic Mô Hình (`upgrade_health_finance_model.md`)

> **Quy trình Thực Thi Tiết Kiệm Token (Theo Chuẩn [`docs/QUY_TRINH_PHAT_TRIEN_APP_BANG_ANTIGRAVITY.md`](file:///Users/canhhung/Documents/pyRetrait/docs/QUY_TRINH_PHAT_TRIEN_APP_BANG_ANTIGRAVITY.md)):**
> 1. **Kế thừa các thành quả từ [`docs/plans/multi_country_ppp_expansion.md`](file:///Users/canhhung/Documents/pyRetrait/docs/plans/multi_country_ppp_expansion.md):**
>    - **Đã hoàn thành**: Schema Hồ sơ Đa quốc gia & Gia đình (`workCountry`, `retireCountry`, `retireMode`, `maritalStatus`, `taxParts = 1.0 / 2.0`), cơ chế 1 quốc gia `isSingleCountry` (tự động triệt tiêu trượt giá tỷ giá `forexDrift = 0`), ngân sách hưu trí tự động tính từ Số dư hàng tháng theo PPP 22+ quốc gia (`calculateRetireBudgetFromCashflow`), và mô hình Lương hưu Pháp/BHXH VN tham số hóa độc lập cho 2 vợ chồng (`spouse1`, `spouse2`).
> 2. **Phạm vi trọng tâm của kế hoạch này:**
>    - Khắc phục các điểm bất hợp lý còn lại giữa Sức khỏe – Tài chính từ báo cáo [`NGHIEN_CUU_KIEN_TRUC_VA_MO_HINH_PYRETRAIT.md`](file:///Users/canhhung/Documents/pyRetrait/NGHIEN_CUU_KIEN_TRUC_VA_MO_HINH_PYRETRAIT.md): Khớp nối Tuổi sinh học/Healthspan vào dòng tiền, đồng bộ 100% Monte Carlo với Engine, hoàn thiện lãi kép các tài khoản Pháp (`frenchAccounts`), mở rộng `taxParts` tính thêm con cái (`familyPlan`) kèm trần Plafonnement du quotient familial, tránh đánh thuế 2 lần (`taxable !== false`), và bảo trì quỹ chung cư Pháp.
> 3. **Thực thi từng Task cuốn chiếu (Giai đoạn 3):**  
>    Sau khi duyệt tài liệu này, người dùng mở phiên chat mới và ra lệnh:  
>    *"Dựa vào file `docs/plans/upgrade_health_finance_model.md`, hãy thực hiện **Task [N]**. Chỉ dùng `replace_file_content` sửa đúng dòng đã chỉ định trong `docs/CODEBASE_MAP.md`."*
> 4. **Quy chuẩn Kiểm thử Tiết kiệm Token:**
>    - Mặc định chỉ kiểm tra giao diện và tính năng trên ngôn ngữ chính là **Tiếng Việt (`vi`)**.
>    - Luôn chạy `./verify_js.sh` để xác thực cú pháp và cập nhật tự động bảng số dòng trong `docs/CODEBASE_MAP.md`.

---

## 1. Mục Tiêu & Ràng Buộc Kỹ Thuật

- **Mục tiêu nghiệp vụ**:
  1. **Khớp nối Trực tiếp Mô hình Sức Khỏe vào Dòng Tiền & Kế Hoạch**:
     - Lưu kết quả **Tuổi sinh học (`bioAge`)**, **Tuổi thọ khỏe mạnh (`estimatedHealthspan`)** và các chỉ số thể chất (`rhr`, `bp`, `whtr`, `habits`) từ Tab Sức khỏe ([`ui-tab2-health.js`](file:///Users/canhhung/Documents/pyRetrait/frontend/js/ui-tab2-health.js)) vào `plan.healthProfile` và đồng bộ Cloud.
     - Khớp nối `estimatedHealthspan` vào mốc kích hoạt Quỹ chăm sóc tuổi già (`seniorCareAge`) và các pha Spending Smile (`gogoAge`, `slowgoAge`) trong [`engine.js`](file:///Users/canhhung/Documents/pyRetrait/frontend/js/engine.js).
     - Hiển thị chỉ số KPI trực quan **"Số năm nghỉ hưu khỏe mạnh"** (`healthyRetirementYears = Math.max(0, estimatedHealthspan - retireAge)`) trên Sidebar.
  2. **Chuẩn Hóa Logic Rút Tiền, Lạm Phát 2 Chặng & Tăng Trưởng Tài Khoản Pháp**:
     - Loại bỏ việc tính trùng lạm phát khi bật `dualInflation` giữa 2 quốc gia: Tốc độ tăng chi phí tính theo đồng gốc EUR tại Việt Nam được tính bằng `max(0, inflationPost - eurVndAnnualDrift)` theo nguyên tắc PPP.
     - Cho phép số dư các tài khoản Pháp (`frenchAccounts`: PEA, Assurance-Vie, Livret A) tăng trưởng theo tỷ suất sinh lời danh mục trong suốt thời gian tích lũy và đầu mỗi năm nghỉ hưu trước khi rút vốn.
     - Bảo toàn phần thặng dư rút tiền (`withdrawalAmount > deficit`) thay vì làm mất dòng tiền khi chiến lược rút vốn tạo ra số tiền lớn hơn nhu cầu chi tiêu thực tế.
  3. **Đồng Bộ 100% Dòng Tiền Giữa Monte Carlo & Engine**:
     - Trích xuất mảng dòng tiền ròng chuẩn từng năm (`netSavingsOrDeficitByAge` — đã gồm thuế lũy tiến theo `taxParts`, lương hưu 2 vợ chồng độc lập, con cái, chăm sóc tuổi già, nợ vay, cột mốc và Spending Smile) từ 1 lượt chạy chuẩn của [`engine.js`](file:///Users/canhhung/Documents/pyRetrait/frontend/js/engine.js).
     - Chạy 1,000 vòng mô phỏng Mulberry32 (seed 42) trong [`monteCarlo.js`](file:///Users/canhhung/Documents/pyRetrait/frontend/js/monteCarlo.js) trên dòng tiền chuẩn này để kết quả Monte Carlo khớp 100% với biểu đồ Net Worth chính và bảng dự phóng từng năm.
  4. **Mở Rộng `taxParts` Theo Con Cái, Trần Plafonnement & Cờ Miễn Thuế (`taxable`)**:
     - Mở rộng công thức tính suất thuế gia đình Pháp: `taxParts = maritalParts (1.0 hoặc 2.0) + childParts` (2 con đầu mỗi con +0.5 part, từ con thứ 3 mỗi con +1.0 part).
     - Áp dụng trần giảm trừ gia cảnh của Pháp (`Plafonnement du quotient familial` tối đa ~1,759 € cho mỗi 0.5 part con tăng thêm).
     - Kiểm tra cờ `stream.taxable !== false` trên từng nguồn thu nhập để loại bỏ thu nhập đã nộp thuế tại nguồn, kiều hối, quà tặng hoặc thừa kế ra khỏi thu nhập chịu thuế, tránh đánh thuế 2 lần.
     - Đồng bộ giao diện Tab 3 ([`ui-tab3-taxes.js`](file:///Users/canhhung/Documents/pyRetrait/frontend/js/ui-tab3-taxes.js)) hiển thị đúng thông số gia đình và kết nối với các hàm lương hưu mới từ `taxOptimizer.js`.
  5. **Tinh Chỉnh Khấu Hao Căn Hộ Chung Cư Pháp Có Quỹ Bảo Trì Tòa Nhà**:
     - Khi căn hộ chung cư có khai báo phí bảo trì định kỳ (`annual_maintenance > 0` hoặc quỹ bảo trì tòa nhà `Fonds de travaux / Charges de copropriété`), giảm tỷ lệ hao mòn vật lý xác nhà (sàn bảo tồn 50%–60% sau 30 năm thay vì tụt về 10%), phản ánh đúng giá trị thực tế tại Pháp.

- **Ràng buộc kỹ thuật bất biến**:
  - **Local-First 100%**: Toàn bộ thuật toán chạy trên client qua JavaScript thuần, không gọi backend tính toán.
  - **Kiến trúc 3 tầng chống phình file**: Tuân thủ phân định trách nhiệm Tầng 1 (Core Engine), Tầng 2 (State & Sync), Tầng 3 (UI Modules).
  - **Công thức & Trình bày**: Tuyệt đối không dùng cú pháp LaTeX. Trình bày công thức bằng văn bản thuần trực quan hoặc code block.
  - **Hệ thống giao diện kép (Dual-Theme)**: Tuân thủ 100% CSS Variables, không hardcode màu tối/sáng.

---

## 2. Tổng Quan Các File & Tọa Độ Dòng Cần Thay Đổi (Cập Nhật Theo [`docs/CODEBASE_MAP.md`](file:///Users/canhhung/Documents/pyRetrait/docs/CODEBASE_MAP.md))

| Task | File tác động (Tối đa 2–3 file/Task) | Khoảng dòng hiện tại trong `CODEBASE_MAP.md` | Nội dung nâng cấp |
| :--- | :--- | :--- | :--- |
| **Task 1** | `frontend/js/ui-tab2-health.js`<br>`frontend/js/engine.js`<br>`frontend/js/ui.js` | Dòng `89 – 291`<br>Dòng `536 – 1364` (khu vực `760 – 785`)<br>Dòng `552 – 740` (khu vực `560 – 620`) | Khớp nối Tuổi sinh học & Healthspan vào `plan.healthProfile`, tự động link với mốc Quỹ chăm sóc tuổi già (`seniorCareAge`) và Spending Smile; hiển thị KPI "Số năm nghỉ hưu khỏe mạnh" trên Sidebar |
| **Task 2** | `frontend/js/engine.js` | Dòng `536 – 1364` (khu vực `655 – 670`, `915 – 1025`) | Khử trùng lặp lạm phát 2 chặng EUR/VND theo nguyên lý PPP; tính lãi kép cho các tài khoản Pháp (`frenchAccounts`) trong giai đoạn tích lũy & đầu mỗi năm nghỉ hưu; bảo toàn thặng dư rút tiền (`withdrawalAmount > deficit`) |
| **Task 3** | `frontend/js/monteCarlo.js`<br>`frontend/js/ui-tab1-charts.js` | Dòng `31 – 171`<br>Dòng `1421 – 1652` | Đồng bộ 100% Monte Carlo: Trích xuất mảng dòng tiền ròng cơ sở chuẩn từng năm từ `runProjection()` (đã có thuế `taxParts`, lương hưu 2 vợ chồng, con cái, nợ vay, chăm sóc già) và áp biến thiên ngẫu nhiên Mulberry32 |
| **Task 4** | `frontend/js/taxOptimizer.js`<br>`frontend/js/engine.js`<br>`frontend/js/ui-tab3-taxes.js` | Dòng `108 – 225`<br>Dòng `671 – 734`, `892 – 905`<br>Dòng `439 – 774` | Mở rộng `taxParts` tính thêm con cái (`familyPlan`) kèm trần Plafonnement du quotient familial (~1.759 €/nửa suất); kiểm tra cờ `taxable !== false` chống đánh thuế 2 lần; đồng bộ hiển thị Tab 3 |
| **Task 5** | `frontend/js/engine.js`<br>`frontend/js/patrimoine.js` | Dòng `135 – 161`<br>Dòng `635 – 887` | Tinh chỉnh mô hình khấu hao chung cư Pháp khi có quỹ bảo trì định kỳ (`Charges de copropriété` / `Fonds de travaux`): Sàn bảo tồn xác nhà 50%–60% sau 30 năm thay vì tụt về 10% |

---

## 3. Phân Tích Logic & Trường Hợp Biên (Edge Cases)

- **Trường hợp 1 — Người dùng chưa đánh giá hoặc không chọn chỉ số sức khỏe ở Tab 2**:
  - `plan.healthProfile` có thể chưa tồn tại hoặc bị rỗng.
  - `engine.js` tự động dùng giá trị dự phòng: `estimatedHealthspan = Number(plan.lifeExpectancy) - 7` (mặc định khỏe mạnh đến 7 năm trước tuổi thọ), hoặc giữ nguyên mốc `seniorCareAge = 78` thủ công của người dùng nếu chưa bật tự động đồng bộ.
- **Trường hợp 2 — Lạm phát 2 chặng khi ở 1 quốc gia vs khi ở 2 quốc gia**:
  - Nếu `plan.retireMode === 'domestic'` hoặc `plan.workCountry === plan.retireCountry`: Cờ `isSingleCountry === true` (đã triển khai ở Task 2 của kế hoạch PPP), `forexDrift = 0`, áp dụng 1 tỷ lệ lạm phát duy nhất.
  - Nếu `plan.retireMode !== 'domestic'` (nghỉ hưu ở Việt Nam với đồng tiền gốc là EUR):
    `Tỷ lệ trượt chi tiêu thực tế (EUR) = max(0, lạm phát VN - tốc độ trượt giá EUR/VND)`
    Tránh trường hợp nhân lạm phát 4.0% vào chi tiêu EUR rồi lại nhân tiếp 1.2% trượt giá ngoại tệ, khiến chi phí EUR tăng ảo gấp đôi.
- **Trường hợp 3 — Chiến lược rút tiền tạo ra số tiền lớn hơn nhu cầu chi tiêu (`withdrawalAmount > deficit`)**:
  - Khi danh mục tăng trưởng tốt, các chiến lược rút vốn (VPW, Guyton-Klinger, Bengen) có thể tính ra số tiền được phép rút lớn hơn số tiền cần chi trả sinh hoạt trong năm.
  - Phần thặng dư `surplus = withdrawalAmount - deficit` không được để biến mất khỏi hệ thống. Người dùng có thể chọn:
    1. Tái đầu tư thặng dư vào danh mục thanh khoản (`portfolio += surplus`).
    2. Nâng hạn mức chi tiêu hưởng thụ trong năm đó (`actualExpenditure = withdrawalAmount`).
- **Trường hợp 4 — Gia đình có con phụ thuộc vượt trần giảm thuế Pháp (Plafonnement du Quotient Familial)**:
  - Luật thuế Pháp quy định mỗi nửa phần thuế tăng thêm từ người phụ thuộc chỉ được giảm tối đa một mức trần danh nghĩa (năm 2024: 1,759 € / nửa suất con).
  - Thuật toán `calculateProgressiveTax` phải so sánh số thuế tính theo số suất thực tế với số thuế tính theo suất cơ bản trừ đi trần tối đa, lấy giá trị lớn hơn để phản ánh đúng thực tế thuế Pháp.

---

## 4. Danh Sách Công Việc Cuốn Chiếu (Actionable Tasks)

### [ ] Task 1 — Khớp Nối Mô Hình Sức Khỏe Vào Kế Hoạch & Dòng Tiền Dự Phóng (`ui-tab2-health.js`, `engine.js`, `ui.js`)

- **File cần sửa**:
  1. `frontend/js/ui-tab2-health.js` (Dòng `89 – 291`).
  2. `frontend/js/engine.js` (Dòng `760 – 785`).
  3. `frontend/js/ui.js` (Dòng `552 – 740`).
- **Nội dung thực hiện**:
  1. Trong `frontend/js/ui-tab2-health.js` — hàm `updateBioAge()` và `updateHealthspanScore()`:
     - Đóng gói dữ liệu sức khỏe vào `plan.healthProfile`:
       ```javascript
       plan.healthProfile = {
         bioAge: estimatedBioAge,
         estimatedHealthspan: estimatedHealthspan,
         rhr: getVal('inp-bio-rhr'),
         bp: getVal('inp-bio-bp'),
         whtr: getVal('inp-bio-whtr'),
         strength: getVal('inp-bio-strength'),
         updatedAt: new Date().toISOString()
       };
       debouncedSavePlansToStorage();
       ```
  2. Trong `frontend/js/engine.js` — hàm `runProjection()`:
     - Đọc `healthProfile = plan.healthProfile || {}`.
     - Nếu người dùng bật liên kết sức khỏe (`plan.linkHealthToCare !== false`):
       - Tự động gán mốc bắt đầu giai đoạn `No-Go` và tuổi kích hoạt Quỹ chăm sóc tuổi già `seniorCareAge = Math.min(Number(plan.seniorCareAge) || 78, Math.round(healthProfile.estimatedHealthspan || 78))`.
     - Tính và trả về chỉ số trong kết quả `runProjection`:
       `healthyRetirementYears = Math.max(0, (healthProfile.estimatedHealthspan || (lifeExpectancy - 7)) - retireAge)`.
  3. Trong `frontend/js/ui.js` — hàm `updateAll()`:
     - Cập nhật số liệu hiển thị tại thẻ Mục tiêu Độc lập trên Sidebar:
       Hiển thị dòng chữ: `"Nghỉ hưu khỏe mạnh: X năm (đến khoảng Y tuổi)"`.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "(() => { const p = { currentAge: 35, retirementAge: 55, lifeExpectancy: 85, healthProfile: { estimatedHealthspan: 76 } }; const res = window.RetirementEngine.runProjection(p); return { healthyYears: res.healthyRetirementYears, seniorCareAge: res.seniorCareAge }; })()"
  ```

---

### [ ] Task 2 — Chuẩn Hóa Logic Rút Tiền, Lạm Phát 2 Chặng & Tăng Trưởng Tài Khoản Pháp (`engine.js`)

- **File cần sửa**:
  1. `frontend/js/engine.js` (Dòng `655 – 670` và dòng `915 – 1025`).
- **Nội dung thực hiện**:
  1. **Chuẩn hóa lạm phát 2 chặng EUR/VND**:
     - Khi `plan.retireMode !== 'domestic'` và `plan.dualInflation?.enabled`:
       Chi tiêu sinh hoạt bằng đồng EUR ở giai đoạn nghỉ hưu tại Việt Nam tăng trưởng theo tốc độ lạm phát thực tế quy đổi:
       `effectiveEurInflation = Math.max(0.01, (inflationPost - forexDrift))`.
       Dùng `effectiveEurInflation` cho dòng chi tiêu EUR, chỉ áp dụng trượt giá tỷ giá ngoại tệ đầy đủ khi chuyển đổi hiển thị ra đồng VND.
  2. **Tăng trưởng số dư tài khoản Pháp (`frenchAccounts`)**:
     - Trong vòng lặp từng năm của `runProjection`:
       - Cho các số dư `peaBalance`, `assuranceVieBalance`, `livretABalance` sinh lời theo tỷ suất tài sản tương ứng (`peaReturn || returnRate`, `avReturn || (returnRate * 0.75)`, `livretReturn || 0.03`) trong cả giai đoạn tích lũy lẫn giai đoạn nghỉ hưu trước khi kích hoạt thác rút tiền.
  3. **Bảo toàn thặng dư rút vốn (`surplus cashflow`)**:
     - Khi `withdrawalAmount > deficit`:
       - Số tiền thực rút khỏi danh mục để bù đắp chi tiêu chỉ là `actualWithdrawal = deficit`.
       - Hoặc nếu rút toàn bộ theo quy tắc chiến lược (`actualWithdrawal = withdrawalAmount`), phần thặng dư dôi dư `surplus = withdrawalAmount - deficit` được cộng ngược lại vào danh mục tài sản sinh lời thanh khoản (`portfolio += surplus`), ngăn chặn hiện tượng mất tiền ảo.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "(() => { const p = { currentAge: 50, retirementAge: 55, lifeExpectancy: 65, currentSavings: 500000, retirementExpenses: 15000, withdrawalStrategy: 'vpw' }; const res = window.RetirementEngine.runProjection(p); return { survived: res.survived, endPortfolio: Math.round(res.finalPortfolio) }; })()"
  ```

---

### [x] Task 3 — Đồng Bộ 100% Dòng Tiền Giữa Monte Carlo & Engine (`monteCarlo.js`, `ui-tab1-charts.js`)

- **File cần sửa**:
  1. `frontend/js/monteCarlo.js` (Dòng `31 – 171`).
  2. `frontend/js/ui-tab1-charts.js` (Dòng `1421 – 1652`).
- **Nội dung thực hiện**:
  1. Trong `frontend/js/monteCarlo.js` — hàm `runSimulation(plan, numSimulations = 1000)`:
     - Chạy 1 lượt dự phóng chuẩn không nhiễu:
       `const baseRun = window.RetirementEngine.runProjection(plan, null, true, true);`
     - Trích xuất mảng dòng tiền ròng cơ sở từng năm:
       `baseNetCashflows = baseRun.yearlyData.map(d => ({ age: d.age, netCashFlow: d.netCashFlow, portfolioStart: d.portfolioStart, expenses: d.expenses, income: d.income, isRetired: d.age >= plan.retirementAge }));`
       *(Mảng này đã tích hợp đầy đủ 100% logic thuế theo `taxParts`, lương hưu 2 vợ chồng độc lập, chi phí con cái, nợ vay, chăm sóc già và Spending Smile)*.
     - Trong 1,000 vòng mô phỏng Monte Carlo (Mulberry32 seed 42):
       - Áp dụng tỷ suất sinh lời ngẫu nhiên `r = randomNormal(meanReturn, stdDev)` lên số dư danh mục đầu năm, sau đó cộng/trừ dòng tiền ròng của năm đó.
       - Áp dụng quy tắc phòng vệ Guyton-Klinger: Khi thị trường sụt giảm mạnh (`r < -0.05`), cắt giảm 10% phần chi tiêu linh hoạt.
  2. Trong `frontend/js/ui-tab1-charts.js` — hàm `renderMonteCarloTab()`:
     - Đảm bảo xác suất thành công (`successRate`) và các dải phân vị P10, P50, P90 phản ánh chính xác kế hoạch thực tế của gia đình.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "(() => { const p = { currentAge: 40, retirementAge: 60, lifeExpectancy: 85, currentSavings: 200000, annualSavings: 15000, retirementExpenses: 20000, maritalStatus: 'married', taxParts: 2.0 }; const mc = window.MonteCarloSimulation.runSimulation(p, 100); return { successRate: mc.successRate, p50Final: Math.round(mc.p50[mc.p50.length - 1]) }; })()"
  ```

---

### [x] Task 4 — Mở Rộng `taxParts` Gia Đình (Con Cái & Trần Plafonnement), Cờ Thuế (`taxable`) & Đồng Bộ Tab 3 (`taxOptimizer.js`, `engine.js`, `ui-tab3-taxes.js`)

- **File cần sửa**:
  1. `frontend/js/taxOptimizer.js` (Dòng `108 – 225`).
  2. `frontend/js/engine.js` (Dòng `671 – 734` và dòng `892 – 905`).
  3. `frontend/js/ui-tab3-taxes.js` (Dòng `439 – 774`).
- **Nội dung thực hiện**:
  1. Trong `frontend/js/taxOptimizer.js` — hàm `calculateProgressiveTax(income, regime, options)`:
     - Tính toán số suất gia đình chuẩn luật Pháp:
       `baseParts = options.maritalStatus === 'married' ? 2.0 : 1.0;`
       `kidsCount = Number(options.kidsCount) || 0;`
       `childParts = kidsCount <= 2 ? (kidsCount * 0.5) : (1.0 + (kidsCount - 2) * 1.0);`
       `totalTaxParts = options.taxParts || (baseParts + childParts);`
     - Áp dụng trần giảm trừ gia cảnh Pháp (`Plafonnement du quotient familial`):
       - Mức giảm thuế tối đa cho mỗi nửa suất con tăng thêm là 1,759 €/năm.
       - So sánh thuế tính theo `baseParts` trừ trần giảm thuế với thuế tính theo `totalTaxParts`, chọn giá trị thuế thực tế phải nộp.
  2. Trong `frontend/js/engine.js` — hàm `runProjection()`:
     - Tách riêng `taxableIncome`: Chỉ tính thuế trên các luồng thu nhập có `stream.taxable !== false` (loại bỏ thu nhập kiều hối, quà tặng hoặc thu nhập đã đóng thuế tại nguồn).
     - Truyền `kidsCount` từ `plan.familyPlan?.kidsCount` vào `calculateProgressiveTax`.
  3. Trong `frontend/js/ui-tab3-taxes.js` — hàm `updateTaxRegimeUI()` và `updatePensionDecoteUI()`:
     - Hiển thị trực quan số suất thuế gia đình (`taxParts`) gồm cả phần vợ chồng và con cái.
     - Đấu nối thẻ Lương hưu Pháp và BHXH VN trên Tab 3 hiển thị kết quả đồng bộ với hàm mới `calculateFrenchPension` và `calculateVietnamBhxhPension`.
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "({ singleTax: window.TaxOptimizer.calculateProgressiveTax(60000, 'france_vietnam', { taxParts: 1.0 }), marriedTax: window.TaxOptimizer.calculateProgressiveTax(60000, 'france_vietnam', { taxParts: 2.0 }), familyTax: window.TaxOptimizer.calculateProgressiveTax(60000, 'france_vietnam', { taxParts: 3.0, kidsCount: 2 }) })"
  ```

---

### [x] Task 5 — Tinh Chỉnh Mô Hình Khấu Hao & Bảo Trì Căn Hộ Chung Cư Pháp (`engine.js`, `patrimoine.js`)

- **File cần sửa**:
  1. `frontend/js/engine.js` (Dòng `135 – 161` — hàm `computePropertyValue()`).
  2. `frontend/js/patrimoine.js` (Dòng `635 – 887` — hàm `renderBreakEvenSingleApt()`).
- **Nội dung thực hiện**:
  1. Trong `frontend/js/engine.js` — hàm `computePropertyValue()`:
     - Với bất động sản loại căn hộ chung cư (`apartment`):
       - Phần Đất (25% giá trị ban đầu): Tăng trưởng dài hạn theo tỷ lệ thị trường (+2.0%/năm).
       - Phần Xác nhà (75% giá trị ban đầu):
         - Nếu có phí bảo trì định kỳ (`annual_maintenance > 0` hoặc `charges_copro > 0`): Hao mòn vật lý được kiểm soát và bù đắp bởi bảo trì thường xuyên; giá trị xác nhà không tụt về 10% mà được bảo toàn sàn ở mức **55% – 60%** sau 30 năm.
         - Nếu không có phí bảo trì: Hao mòn về sàn 10% sau 30 năm như cũ.
  2. Trong `frontend/js/patrimoine.js` — hàm `renderBreakEvenSingleApt()`:
     - Cập nhật hiển thị biểu đồ và giải thích điểm hòa vốn căn hộ kèm tác động tích cực của quỹ bảo trì tòa nhà (`Fonds de travaux Loi ALUR`).
- **Biểu thức kiểm thử bằng `./verify_js.sh`**:
  ```zsh
  ./verify_js.sh "({ aptMaintained: window.RetirementEngine.computePropertyValue({ property_type: 'apartment', current_value: 300000, annual_maintenance: 1200, growth_rate: 2.0 }, 30), aptUnmaintained: window.RetirementEngine.computePropertyValue({ property_type: 'apartment', current_value: 300000, annual_maintenance: 0, growth_rate: 2.0 }, 30) })"
  ```
