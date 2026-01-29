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
        // Xử lý period (format YYYY-MM-DD)
        const today = new Date();
        const start_date = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; // 7 ngày trước
        const end_date = today.toISOString().split('T')[0]; // Hôm nay
        
        const payload = {
            "request_meta": { 
                // request_id & timestamp sẽ được server tạo lại
                "mode_type": modeType === "Analyze_Data" ? "Analyze Report" : "AI Assistant"
            },
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "filters": finalFilters,
            "mode_type": modeType === "Analyze_Data" ? "Analyze Report" : "AI Assistant"
        };
        
        // Thêm user_question nếu là Chat mode
        if(isChatMode && userQuestion) {
            payload.user_question = userQuestion;
        }

        // Debug log
        console.log(`📤 Sending payload [${modeType}]:`, payload);

        // --- BƯỚC 3: GỬI SANG BACKEND ---
        console.log("🚀 Gửi request tới /ask-ai...");
        const backendResponse = await sendToBackend(payload);
        
        console.log("📥 Response từ backend:", backendResponse);
        
        // --- HIỂN THỊ TRONG DEBUG PANEL ---
        const debugPanel = document.getElementById("debugPanel");
        if(debugPanel) {
            debugPanel.textContent = JSON.stringify(backendResponse.data || backendResponse, null, 2);
        }
        
        // --- BƯỚC 4: HIỂN THỊ KẾT QUẢ (Bao gồm JSON debug) ---
        let displayHtml = `
            <div style="text-align:left;">
                <div style="background:#e3f2fd; padding:10px; margin-bottom:10px; border-left:4px solid #2196F3;">
                    ${backendResponse.answer || ""}
                </div>
        `;
        
        // Hiển thị JSON response đầy đủ
        if(backendResponse.data) {
            displayHtml += `
                <details open style="background:#f5f5f5; padding:10px; margin-top:10px; border-radius:4px;">
                    <summary style="cursor:pointer; font-weight:bold; color:#333;">
                        📋 JSON Response (DEBUG)
                    </summary>
                    <pre style="background:#fff; border:1px solid #ddd; padding:10px; overflow-x:auto; font-size:11px; margin-top:8px;">
${JSON.stringify(backendResponse.data, null, 2)}
                    </pre>
                </details>
            `;
        }
        
        displayHtml += `</div>`;
        
        if(resultContainer) resultContainer.innerHTML = displayHtml;
        if(statusText) statusText.textContent = "✅ Completed";

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
    try {
        const res = await fetch("http://localhost:5000/ask-ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const data = await res.json();
        return data;
    } catch (err) {
        console.error("❌ Backend error:", err);
        throw new Error(`Failed to reach backend: ${err.message}`);
    }
}