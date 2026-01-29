// --- CẤU HÌNH ---
const MAIN_SHEET_NAME = "Line_Chart"; 

// --- KHỞI TẠO ---
let dashboard;
tableau.extensions.initializeAsync().then(() => {
    dashboard = tableau.extensions.dashboardContent.dashboard;
    console.log("✅ Extension initialized");
    
    // 1. Gắn sự kiện cho nút ANALYZE (Report)
    const analyzeBtn = document.getElementById("analyzeBtn");
    if(analyzeBtn) {
        analyzeBtn.addEventListener("click", () => handleProcess("Analyze_Data"));
    }

    // 2. Gắn sự kiện cho nút SEND (Chat AI)
    const sendBtn = document.getElementById("sendBtn");
    if(sendBtn) {
        sendBtn.addEventListener("click", () => handleProcess("AI_Assistant"));
    }
});

// --- HÀM XỬ LÝ CHUNG (Nhận tham số modeType) ---
async function handleProcess(modeType) {
    // Xác định vùng hiển thị kết quả dựa trên Mode
    const isChatMode = (modeType === "AI_Assistant");
    
    // Lấy các element UI tương ứng
    const statusText = document.getElementById("statusText"); // Text trạng thái chung
    
    // Nếu là Chat Mode thì hiển thị kết quả vào ô chat, ngược lại vào ô Analyze
    const resultContainer = isChatMode 
        ? document.getElementById("chatResult") 
        : document.getElementById("analyzeResult");

    // Lấy câu hỏi của User (Chỉ dùng nếu là AI Assistant)
    const userQuestion = isChatMode 
        ? document.getElementById("chatInput").value 
        : "";

    try {
        if(statusText) statusText.textContent = `Processing ${modeType}...`;
        if(resultContainer) {
            resultContainer.innerHTML = "⏳ Đang thu thập dữ liệu & phân tích...";
            resultContainer.classList.remove("empty");
        }

        // --- BƯỚC 1: LẤY DỮ LIỆU DASHBOARD (Dùng chung cho cả 2 mode) ---
        
        // 1.1 Lấy Filter thô
        const rawFilters = await getRawFilters();

        // 1.2 Cross-check để lấy giá trị thực (Fix lỗi All)
        const finalFilters = await enrichFiltersWithData(rawFilters);

        // 1.3 Lấy Parameter Period (Nếu có)
        const params = await dashboard.getParametersAsync();
        const periodParam = params.find(p => p.name === "Input Period"); 
        const periodValue = periodParam ? periodParam.currentValue.formattedValue : "N/A";

        // --- BƯỚC 2: ĐÓNG GÓI PAYLOAD ---
        const payload = {
            "request_meta": { 
                "request_id": "req_" + Date.now(),
                "timestamp": new Date().toISOString(),
                "mode_type": modeType // <--- GIÁ TRỊ ĐỘNG Ở ĐÂY ("Analyze_Data" hoặc "AI_Assistant")
            },
            "user_question": userQuestion, // Gửi kèm câu hỏi nếu có
            "period": periodValue,
            "filters": finalFilters
        };

        // Debug log
        console.log(`📤 Sending payload [${modeType}]:`, payload);

        // --- BƯỚC 3: HIỂN THỊ DEBUG (Tạm thời) ---
        // (Bạn có thể bỏ phần này khi chạy thật để gọi sendToBackend)
        let debugHtml = `
            <div style="text-align:left; font-size:12px;">
                <div style="background:#e3f2fd; padding:5px; margin-bottom:5px; border-left:3px solid #2196F3;">
                    <strong>MODE:</strong> ${modeType}<br>
                    ${isChatMode ? `<strong>Q:</strong> ${userQuestion}` : ''}
                </div>
                <strong>FILTERS:</strong>
        `;
        
        for (const [key, val] of Object.entries(finalFilters)) {
            const color = (val === "(All)" || val[0] === "(All)") ? "#888" : "#007bff; font-weight:bold";
            debugHtml += `<div>• ${key}: <span style="color:${color}">${Array.isArray(val) ? val.join(", ") : val}</span></div>`;
        }
        debugHtml += `</div>`;
        
        if(resultContainer) resultContainer.innerHTML = debugHtml;
        if(statusText) statusText.textContent = "Ready to send";

        // --- BƯỚC 4: GỬI SANG BACKEND ---
        // const backendResponse = await sendToBackend(payload);
        // if(resultContainer) resultContainer.innerHTML = backendResponse.answer;

    } catch (err) {
        console.error(err);
        if(resultContainer) resultContainer.innerHTML = `<span style="color:red">Lỗi: ${err.message}</span>`;
        if(statusText) statusText.textContent = "Failed";
    }
}

// ... (Giữ nguyên các hàm getRawFilters và enrichFiltersWithData ở dưới)
// --- HÀM 1: LẤY FILTER THÔ (Giữ nguyên) ---
async function getRawFilters() {
    const sheet = dashboard.worksheets.find(w => w.name === MAIN_SHEET_NAME);
    if (!sheet) throw new Error(`Không tìm thấy sheet: ${MAIN_SHEET_NAME}`);
    
    const filters = await sheet.getFiltersAsync();
    const filterMap = {};
    
    filters.forEach(f => {
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

// --- HÀM 2: CROSS-CHECK DỮ LIỆU (Giữ nguyên) ---
async function enrichFiltersWithData(currentFilters) {
    const sheet = dashboard.worksheets.find(w => w.name === MAIN_SHEET_NAME);
    const summary = await sheet.getSummaryDataAsync({ maxRows: 0 }); 
    const data = summary.data;
    const columns = summary.columns;

    // console.log("📊 COLUMNS FOUND:", columns.map(c => c.fieldName));

    for (const [filterName, filterValue] of Object.entries(currentFilters)) {
        if (filterValue[0] === "(All)") {
            const colIndex = columns.findIndex(c => {
                const dbName = c.fieldName.replace(/[\[\]]/g, ""); 
                const fName = filterName.replace(/[\[\]]/g, "");
                return dbName === fName || dbName.includes(fName); 
            });
            
            if (colIndex !== -1 && data.length > 0) {
                const uniqueValues = new Set();
                const limit = Math.min(data.length, 500); 
                for (let i = 0; i < limit; i++) {
                    uniqueValues.add(data[i][colIndex].formattedValue);
                }

                if (uniqueValues.size === 1) {
                    currentFilters[filterName] = Array.from(uniqueValues);
                } else if (uniqueValues.size > 1 && uniqueValues.size < 10) {
                    currentFilters[filterName] = Array.from(uniqueValues);
                }
            }
        }
    }
    return currentFilters;
}

// Hàm gửi backend
async function sendToBackend(payload) {
    const res = await fetch("http://localhost:5000/ask-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return await res.json();
}