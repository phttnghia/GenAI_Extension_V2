// --- KHỞI TẠO ---
let dashboard;
tableau.extensions.initializeAsync().then(() => {
    dashboard = tableau.extensions.dashboardContent.dashboard;
    console.log("✅ Extension initialized");
    
    const analyzeBtn = document.getElementById("analyzeBtn");
    if(analyzeBtn) {
        analyzeBtn.addEventListener("click", getFiltersSmart);
    }
});

// --- HÀM THÔNG MINH: QUÉT TẤT CẢ SHEET ĐỂ TÌM FILTER ---
async function getFiltersSmart() {
    const statusText = document.getElementById("statusText");
    const analyzeResult = document.getElementById("analyzeResult");
    
    try {
        statusText.textContent = "Scanning filters...";
        
        // Object chứa kết quả cuối cùng (Dùng Object để tự loại bỏ filter trùng lặp)
        const finalFilters = {};
        
        // 1. Lấy danh sách tất cả Worksheet trên Dashboard
        const worksheets = dashboard.worksheets;
        
        // 2. Duyệt qua từng sheet để gom Filter
        // (Dùng Promise.all để chạy song song cho nhanh)
        const promises = worksheets.map(async (sheet) => {
            try {
                const filters = await sheet.getFiltersAsync();
                filters.forEach(f => {
                    // Logic lấy giá trị
                    let filterValues = [];
                    
                    if (f.isAllSelected) {
                        filterValues = ["(All)"];
                    } else {
                        // Lấy giá trị thực tế đang chọn
                        filterValues = f.appliedValues.map(v => v.formattedValue);
                    }

                    // Lưu vào kết quả (Ghi đè nếu trùng tên, ưu tiên filter có giá trị cụ thể)
                    // Logic: Nếu filter này chưa có trong list HOẶC filter cũ đang là "All" mà cái mới là "Cụ thể"
                    if (!finalFilters[f.fieldName] || (finalFilters[f.fieldName][0] === "(All)" && filterValues[0] !== "(All)")) {
                        finalFilters[f.fieldName] = filterValues;
                    }
                });
            } catch (e) {
                console.warn(`Lỗi đọc filter sheet ${sheet.name}:`, e);
            }
        });

        await Promise.all(promises);

        // 3. Lấy Parameter (Input Period)
        const params = await dashboard.getParametersAsync();
        const periodParam = params.find(p => p.name === "Input Period");
        const periodValue = periodParam ? periodParam.currentValue.formattedValue : "N/A";

        // 4. Đóng gói Payload
        const payload = {
            "request_meta": { "timestamp": new Date().toISOString() },
            "period": periodValue,
            "filters": finalFilters
        };

        // --- HIỂN THỊ KẾT QUẢ DEBUG ---
        analyzeResult.innerHTML = `
            <div style="font-size:12px; text-align:left; background:#f8f9fa; padding:10px; border:1px solid #ddd;">
                <strong>🔍 TÌM THẤY ${Object.keys(finalFilters).length} FILTERS:</strong>
                <ul style="padding-left:15px; margin:5px 0;">
                    ${Object.entries(finalFilters).map(([key, val]) => 
                        `<li><b>${key}:</b> ${Array.isArray(val) ? val.join(", ") : val}</li>`
                    ).join("")}
                </ul>
                <hr>
                <em>Đang gửi sang Python...</em>
            </div>
        `;

        // 5. Gửi sang Server (như cũ)
        const res = await fetch("http://localhost:5000/ask-ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const result = await res.json();
        
        // Append kết quả server
        analyzeResult.innerHTML += `<br>
            <div style="color:green; font-weight:bold; margin-top:5px;">
                ✅ Python phản hồi: ${result.answer}
            </div>`;
        
        statusText.textContent = "Done!";

    } catch (err) {
        console.error(err);
        analyzeResult.innerHTML = `<span style="color:red">Error: ${err.message}</span>`;
        statusText.textContent = "Failed";
    }
}