// --- CẤU HÌNH ---
const MAIN_SHEET_NAME = "Line_Chart"; 

// --- KHỞI TẠO ---

// Tab switching
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
  });
});
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
    const chatInput = document.getElementById("chatInput");
    const charCount = document.getElementById("charCount");
    
    if(sendBtn) {
        sendBtn.addEventListener("click", () => handleProcess("AI_Assistant"));
    }
    
    if(chatInput) {
        // Enable/disable send button based on input
        chatInput.addEventListener("input", (e) => {
            const text = e.target.value.trim();
            const charCountText = `${text.length} / 500`;
            
            if(charCount) charCount.textContent = charCountText;
            if(sendBtn) sendBtn.disabled = text.length === 0;
        });
        
        // Allow Shift+Enter to send
        chatInput.addEventListener("keydown", (e) => {
            if(e.key === "Enter" && e.shiftKey && !sendBtn.disabled) {
                handleProcess("AI_Assistant");
            }
        });
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
        // Validate chat input for AI Assistant mode
        if(isChatMode && !userQuestion.trim()) {
            throw new Error("Vui lòng nhập câu hỏi trước khi gửi");
        }

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

        // --- BƯỚC 2: ĐÓNG GÓP PAYLOAD ---
        // Xử lý period: Ban đầu gửi null để backend lấy toàn bộ dữ liệu, 
        // sau đó backend sẽ tính min/max date từ dữ liệu thực tế
        const payload = {
            "request_meta": { 
                "mode_type": modeType === "Analyze_Data" ? "Analyze Report" : "AI Assistant"
            },
            "period": {
                "start_date": null,
                "end_date": null
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
        
        // --- BƯỚC 4: HIỂN THỊ KẾT QUẢ ---
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
        
        // Clear chat input after successful send
        if(isChatMode) {
            const chatInput = document.getElementById("chatInput");
            if(chatInput) {
                chatInput.value = "";
                const charCount = document.getElementById("charCount");
                if(charCount) charCount.textContent = "0 / 500";
                const sendBtn = document.getElementById("sendBtn");
                if(sendBtn) sendBtn.disabled = true;
            }
        }

    } catch (err) {
        console.error(err);
        if(resultContainer) resultContainer.innerHTML = `<span style="color:red">❌ Lỗi: ${err.message}</span>`;
        if(statusText) statusText.textContent = "Failed";
    }
}

// --- HÀM 1: LẤY FILTER THÔ ---
// --- HÀM 1: LẤY FILTER THÔ ---
async function getRawFilters() {
    const sheet = dashboard.worksheets.find(w => w.name === MAIN_SHEET_NAME);
    if (!sheet) throw new Error(`Không tìm thấy sheet: ${MAIN_SHEET_NAME}`);
    
    const filters = await sheet.getFiltersAsync();
    const filterMap = {};
    
    // DANH SÁCH CÁC FILTER MUỐN BỎ QUA (BLACKLIST)
    // Bạn có thể thêm bất kỳ filter nào không muốn gửi đi vào đây
    const IGNORED_FILTERS = [
        "Measure Names", 
        "Metric Name Set", 
        "Filter_Weekend" // <--- Thêm cái này vào
    ];

    filters.forEach(f => {
        // Kiểm tra xem tên filter có nằm trong danh sách bị loại trừ không
        if (!IGNORED_FILTERS.includes(f.fieldName)) {
             if (f.isAllSelected) {
                filterMap[f.fieldName] = ["(All)"];
            } else {
                filterMap[f.fieldName] = f.appliedValues.map(v => v.formattedValue);
            }
        }
    });
    return filterMap;
}

// --- HÀM 2: CROSS-CHECK DỮ LIỆU ---
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
        console.log("🔌 Fetching /ask-ai...");
        const res = await fetch("http://localhost:5000/ask-ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        console.log(`   Response status: ${res.status} ${res.statusText}`);
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const data = await res.json();
        console.log("✅ Got response:", data);
        return data;
    } catch (err) {
        console.error("❌ Backend error:", err);
        throw err;
    }
}
