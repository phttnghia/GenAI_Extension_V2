// --- CẤU HÌNH ---
const MAIN_SHEET_NAME = "Line_Chart"; // Đảm bảo tên này khớp với sheet trên Dashboard
const PERIOD_PARAM_NAME = "Input Period"; 

// --- KHỞI TẠO ---
let dashboard;
tableau.extensions.initializeAsync().then(() => {
    dashboard = tableau.extensions.dashboardContent.dashboard;
    console.log("✅ Extension initialized");
    
    const analyzeBtn = document.getElementById("analyzeBtn");
    if(analyzeBtn) analyzeBtn.addEventListener("click", handleAnalyzeSmart);
});

// --- HÀM XỬ LÝ CHÍNH ---
async function handleAnalyzeSmart() {
    const statusText = document.getElementById("statusText");
    const analyzeResult = document.getElementById("analyzeResult");
    
    try {
        statusText.textContent = "Scanning Dashboard...";
        analyzeResult.innerHTML = "⏳ Đang phân tích dữ liệu thực tế...";

        // 1. Lấy Filter thô từ API (Cái này đang bị lỗi All)
        const rawFilters = await getRawFilters();

        // 2. Lấy dữ liệu thực tế từ biểu đồ để Cross-check
        // (Đây là bước fix lỗi "All")
        const finalFilters = await enrichFiltersWithData(rawFilters);

        // 3. Lấy Parameter Period
        const params = await dashboard.getParametersAsync();
        const periodParam = params.find(p => p.name === PERIOD_PARAM_NAME);
        const periodValue = periodParam ? periodParam.currentValue.formattedValue : "N/A";
        const periodData = await getPeriodData(); // Gọi hàm mới

        // 4. Đóng gói
        const payload = {
            "request_meta": { 
                "request_id": "req_" + Date.now(),
                "timestamp": new Date().toISOString(),
                "mode_type": "Analyze Report"
            },
            "period": periodData,
            "filters": finalFilters
        };

        // --- HIỂN THỊ DEBUG (Để bạn kiểm tra xem đã mất chữ All chưa) ---
        let debugHtml = `<div style="text-align:left; font-size:12px;">`;
        for (const [key, val] of Object.entries(finalFilters)) {
            // Tô màu xanh nếu lấy được giá trị cụ thể, màu xám nếu vẫn là All
            const color = (val === "(All)" || val[0] === "(All)") ? "#888" : "#007bff; font-weight:bold";
            debugHtml += `<div>• ${key}: <span style="color:${color}">${Array.isArray(val) ? val.join(", ") : val}</span></div>`;
        }
        debugHtml += `</div>`;
        
        analyzeResult.innerHTML = debugHtml;
        statusText.textContent = "Sending to AI...";

        // 5. Gửi sang Backend (Agent AI)
        // await sendToBackend(payload); // Bỏ comment dòng này khi chạy thật

    } catch (err) {
        console.error(err);
        analyzeResult.innerHTML = `<span style="color:red">Lỗi: ${err.message}</span>`;
        statusText.textContent = "Failed";
    }
}
// ... (Các phần cấu hình và init giữ nguyên)

// --- HÀM MỚI: TỰ ĐỘNG TÍNH PERIOD TỪ DỮ LIỆU ---
async function getPeriodData() {
    try {
        const sheet = dashboard.worksheets.find(w => w.name === MAIN_SHEET_NAME);
        if (!sheet) return { "start_date": "", "end_date": "" };

        // Lấy toàn bộ dữ liệu đang hiển thị
        const summary = await sheet.getSummaryDataAsync({ maxRows: 0 });
        const data = summary.data;
        const columns = summary.columns;

        // 1. Tìm cột chứa dữ liệu Ngày tháng
        // Ưu tiên tìm cột có kiểu dữ liệu là 'date' hoặc 'date-time'
        // Hoặc tìm theo tên field của bạn: "Min_Date", "Max_Date"
        let dateColIndex = columns.findIndex(c => c.dataType === 'date' || c.dataType === 'date-time');

        // Nếu không tìm thấy cột Date chuẩn, thử tìm theo tên Calculated Field bạn vừa tạo
        if (dateColIndex === -1) {
            dateColIndex = columns.findIndex(c => c.fieldName.includes("Min_Date") || c.fieldName.includes("Date"));
        }

        if (dateColIndex === -1 || data.length === 0) {
            console.warn("⚠️ Không tìm thấy cột Date để tính Period");
            return { "start_date": "", "end_date": "" };
        }

        // 2. Quét toàn bộ dữ liệu để tìm Min và Max thực sự
        // Lưu ý: Dữ liệu Tableau trả về có thể chưa sort
        let minTime = Infinity;
        let maxTime = -Infinity;

        data.forEach(row => {
            const cellValue = row[dateColIndex].value; // Giá trị gốc (thường là chuỗi chuẩn hoặc timestamp)
            const timestamp = new Date(cellValue).getTime(); // Convert sang số để so sánh

            if (!isNaN(timestamp)) {
                if (timestamp < minTime) minTime = timestamp;
                if (timestamp > maxTime) maxTime = timestamp;
            }
        });

        // 3. Format lại thành chuỗi "MM/DD/YYYY" như bạn muốn
        if (minTime === Infinity || maxTime === -Infinity) {
            return { "start_date": "", "end_date": "" };
        }

        const formatDate = (ts) => {
            const d = new Date(ts);
            const month = ("0" + (d.getMonth() + 1)).slice(-2);
            const day = ("0" + d.getDate()).slice(-2);
            const year = d.getFullYear();
            return `${month}/${day}/${year}`;
        };

        return {
            "start_date": formatDate(minTime),
            "end_date": formatDate(maxTime)
        };

    } catch (e) {
        console.error("Lỗi tính Period:", e);
        return { "start_date": "Error", "end_date": "Error" };
    }
}

// ... (Các hàm getRawFilters, enrichFiltersWithData giữ nguyên code cũ)
// --- HÀM 1: LẤY FILTER THÔ (Giữ nguyên logic cũ) ---
async function getRawFilters() {
    const sheet = dashboard.worksheets.find(w => w.name === MAIN_SHEET_NAME);
    if (!sheet) throw new Error(`Không tìm thấy sheet: ${MAIN_SHEET_NAME}`);
    
    const filters = await sheet.getFiltersAsync();
    const filterMap = {};
    
    filters.forEach(f => {
        // Chỉ lấy các filter chính (Bỏ Measure Names)
        if (f.fieldName !== "Measure Names" && f.fieldName !== "Metric Name Set") {
             if (f.isAllSelected) {
                filterMap[f.fieldName] = ["(All)"];
            } else {
                filterMap[f.fieldName] = f.appliedValues.map(v => v.formattedValue);
            }
        }
    });
    return filterMap;
}

// --- HÀM 2: CROSS-CHECK DỮ LIỆU (FIX LỖI ALL) ---
// --- HÀM 2: CROSS-CHECK DỮ LIỆU (BẢN NÂNG CẤP) ---
async function enrichFiltersWithData(currentFilters) {
    const sheet = dashboard.worksheets.find(w => w.name === MAIN_SHEET_NAME);
    
    // Lấy dữ liệu
    const summary = await sheet.getSummaryDataAsync({ maxRows: 0 }); 
    const data = summary.data;
    const columns = summary.columns;

    // --- DEBUG: In ra danh sách cột thực tế Extension nhìn thấy ---
    // (Bấm F12 -> Console để xem danh sách này)
    console.log("📊 CÁC CỘT DỮ LIỆU TÌM THẤY TRONG LINE_CHART:");
    columns.forEach(c => console.log(` - ${c.fieldName}`));
    console.log("------------------------------------------------");

    // Duyệt qua từng Filter
    for (const [filterName, filterValue] of Object.entries(currentFilters)) {
        
        // Chỉ xử lý nếu đang là (All)
        if (filterValue[0] === "(All)") {
            
            // 1. TÌM CỘT TƯƠNG ỨNG (Logic tìm kiếm mờ - Fuzzy Match)
            // Tableau hay thêm [] hoặc ATTR() vào tên cột, nên cần so sánh tương đối
            const colIndex = columns.findIndex(c => {
                const dbName = c.fieldName.replace(/[\[\]]/g, ""); // Bỏ dấu []
                const fName = filterName.replace(/[\[\]]/g, "");
                return dbName === fName || dbName.includes(fName); 
            });
            
            if (colIndex !== -1 && data.length > 0) {
                const uniqueValues = new Set();
                
                // Quét 500 dòng đầu
                const limit = Math.min(data.length, 500); 
                for (let i = 0; i < limit; i++) {
                    uniqueValues.add(data[i][colIndex].formattedValue);
                }

                // Nếu chỉ tìm thấy 1 giá trị duy nhất -> Đó là giá trị đang Filter
                if (uniqueValues.size === 1) {
                    currentFilters[filterName] = Array.from(uniqueValues);
                    console.log(`✅ Đã fix filter "${filterName}" -> ${Array.from(uniqueValues)}`);
                } 
                // Logic bổ sung: Nếu tìm thấy ít hơn 10 giá trị, lấy luôn list đó
                else if (uniqueValues.size > 1 && uniqueValues.size < 10) {
                    currentFilters[filterName] = Array.from(uniqueValues);
                }
            } else {
                console.warn(`⚠️ Không tìm thấy cột dữ liệu cho filter: "${filterName}". Hãy kéo field này vào Tooltip của Line_Chart!`);
            }
        }
    }
    
    return currentFilters;
}

// Hàm gửi backend (để tạm đây)
async function sendToBackend(payload) {
    const res = await fetch("http://localhost:5000/ask-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return await res.json();
}