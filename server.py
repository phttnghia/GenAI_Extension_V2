from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import pyodbc
import os
import json
from datetime import datetime
import uuid
# from config.settings import settings # (Bỏ comment khi chạy thật)

# --- MOCK SETTINGS (Dùng tạm để code chạy được ngay, bạn thay bằng import settings nhé) ---
class settings:
    AZURE_SQL_SERVER = 'your-server.database.windows.net'
    AZURE_SQL_DATABASE = 'your-database'
    AZURE_SQL_USER = 'your-email'
    AZURE_SQL_PASSWORD = 'your-password'
    AZURE_SQL_DRIVER = '{ODBC Driver 17 for SQL Server}'
    AZURE_CONNECT_TIMEOUT = 30

app = Flask(__name__, static_folder=os.path.dirname(os.path.abspath(__file__)))
CORS(app)

# ==============================================================================
# 1. CẤU HÌNH
# ==============================================================================

DB_VIEW_NAME = "vw_bug_report_by_testplan" 
DB_SCHEMA_NAME = "bug-management_dm_test"  

# 1. Mapping Filter: Tên Filter UI -> Tên Cột DB (Dùng cho WHERE clause)
FILTER_COLUMN_MAPPING = {
    "Project Identifier": "project_identifier",
    "Redmine Infra": "redmine_infra",
    "Redmine Server": "redmine_server",
    "Redmine Instance": "redmine_instance",
    "Filter 1 (Vw Bug Report By Testplan)": "filter_1",
    "Filter 2 (Vw Bug Report By Testplan)": "filter_2",
    "Filter 3 (Vw Bug Report By Testplan)": "filter_3",
    "Filter 4 (Vw Bug Report By Testplan)": "filter_4",
    "Filter 5 (Vw Bug Report By Testplan)": "filter_5"
}

# 2. Mapping Metric Name: Giá trị trong cột Metric_Name (DB) -> Key trong JSON (Output)
# Cách dùng: Khi Pivot, cột Metric_Name sẽ được map sang key này trong JSON output
# Ví dụ: DB có Metric_Name='TestCaseActual' -> JSON output sẽ có key 'TestCaseActual': <giá trị>
# NẾU BẠN MUỐN ĐỔI TÊN: Chỉ cần sửa value bên phải
# Ví dụ: "TestCaseActual": "Test_Case_Actual" (nếu muốn snake_case)
METRIC_VALUE_MAPPING = {
    "TestCaseExpected": "TestCaseExpected",
    "TestCaseExpectedTotal": "TestCaseExpectedTotal",
    "TestCaseActual": "TestCaseActual",
    "TestCaseActualTotal": "TestCaseActualTotal",
    "BReportExpected": "BReportExpected",
    "BReportExpectedTotal": "BReportExpectedTotal",
    "BReportActual": "BReportActual",
    "BReportActualTotal": "BReportActualTotal",
    "BReportFixed": "BReportFixed",
    "BReportFixedTotal": "BReportFixedTotal",
    "BReportOutstanding": "BReportOutstanding",
    "BReportUpperBound": "BReportUpperBound",
    "BReportLowerBound": "BReportLowerBound"
}

# ==============================================================================
# 2. HỖ TRỢ HÀM
# ==============================================================================

def generate_request_id():
    """Generate unique request ID"""
    return f"req_{uuid.uuid4().hex[:12]}"

def get_iso_timestamp():
    """Get current timestamp in ISO 8601 format"""
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# ==============================================================================
# 2.5 DATABASE CONNECTION
# ==============================================================================
def get_db_connection():
    try:
        # Authentication=ActiveDirectoryInteractive (Dùng cho MFA)
        # Authentication=SqlPassword (Dùng cho user/pass thường)
        conn_str = (
            f"Driver={settings.AZURE_SQL_DRIVER};"
            f"Server={settings.AZURE_SQL_SERVER};"
            f"Database={settings.AZURE_SQL_DATABASE};"
            f"UID={settings.AZURE_SQL_USER};"
            "Authentication=ActiveDirectoryInteractive;" # <--- QUAN TRỌNG: Để dòng này nếu dùng MFA
        )
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        raise e

# ==============================================================================
# 3. BUILD QUERY (Sửa lại: Chỉ lấy 3 cột chính để Pivot)
# ==============================================================================
def build_query(filters, period_start, period_end):
    # Thay vì select cột động, ta select 3 cột cố định của mô hình EAV
    # Giả sử tên cột trong view là: report_date, metric_name, metric_value
    # Bạn cần sửa lại tên cột này cho đúng với View thật của bạn
    sql = f"""
        SELECT 
            report_date as date, 
            Metric_Name, 
            Metric_Value 
        FROM {DB_SCHEMA_NAME}.{DB_VIEW_NAME} 
        WHERE 1=1
    """
    
    params = []

    # 1. Period
    if period_start and period_end:
        sql += " AND report_date BETWEEN ? AND ?"
        params.append(period_start)
        params.append(period_end)

    # 2. Filters
    for ui_filter_name, filter_values in filters.items():
        db_column = FILTER_COLUMN_MAPPING.get(ui_filter_name)
        
        if db_column and filter_values:
            if isinstance(filter_values, list) and len(filter_values) > 0:
                # Loại bỏ giá trị (All)
                clean_values = [v for v in filter_values if v not in ["(All)", "All"]]
                if clean_values:
                    placeholders = ', '.join(['?'] * len(clean_values))
                    sql += f" AND {db_column} IN ({placeholders})"
                    params.extend(clean_values)
            
            elif isinstance(filter_values, str):
                if filter_values not in ["(All)", "All", ""]:
                    sql += f" AND {db_column} = ?"
                    params.append(filter_values)

    return sql, params

# ==============================================================================
# 4. API ENDPOINT
# ==============================================================================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    try:
        req_data = request.json
        print("📥 Received Payload...")

        # --- Lấy dữ liệu từ request ---
        request_meta = req_data.get('request_meta', {})
        filters = req_data.get('filters', {})
        period = req_data.get('period', {})
        mode_type = req_data.get('mode_type', 'Analyze Report')  # Default mode
        
        p_start = period.get('start_date')
        p_end = period.get('end_date')

        # --- A. QUERY DATABASE ---
        print("⚙️ Building Query...")
        sql, params = build_query(filters, p_start, p_end)
        
        print(f"   SQL: {sql}")
        print(f"   Params: {params}")

        print("🔌 Connecting to DB...")
        conn = get_db_connection()
        
        # Load dữ liệu vào DataFrame
        df = pd.read_sql(sql, conn, params=params)
        conn.close()

        if df.empty:
            print("⚠️ Query trả về rỗng.")
            metrics_data = []
        else:
            # --- B. XỬ LÝ PIVOT DATA ---
            print("🔄 Pivoting Data...")
            
            # 1. Chuẩn hóa format ngày tháng (YYYY-MM-DD)
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 2. Filter: Chỉ lấy metric nằm trong METRIC_VALUE_MAPPING
            df = df[df['Metric_Name'].isin(METRIC_VALUE_MAPPING.keys())]
            
            # 3. Map tên metric sang tên key JSON (nếu có sự khác biệt)
            df['Metric_Name'] = df['Metric_Name'].map(METRIC_VALUE_MAPPING)

            # 4. Pivot Table: Xoay dữ liệu từ dạng dài sang dạng rộng
            # Index: date (Mỗi ngày 1 dòng)
            # Columns: Metric_Name (Biến giá trị cột này thành tên cột mới)
            # Values: Metric_Value (Giá trị của metric)
            df_pivot = df.pivot_table(
                index='date', 
                columns='Metric_Name', 
                values='Metric_Value', 
                aggfunc='first'  # Nếu trùng, lấy giá trị đầu tiên
            ).reset_index()

            # 5. Fill NaN với 0 (hoặc null nếu bạn muốn)
            df_pivot = df_pivot.fillna(0)
            
            # 6. Convert thành List Dictionary
            metrics_data = df_pivot.to_dict(orient='records')

        # --- C. TẠO JSON OUTPUT THEO FORMAT CÓ ĐỊNH ---
        # Tạo request_meta với request_id, timestamp, mode_type
        final_request_meta = {
            "request_id": generate_request_id(),
            "timestamp": get_iso_timestamp(),
            "mode_type": mode_type
        }
        
        # Merge với request_meta từ client (nếu có thêm thông tin)
        final_request_meta.update(request_meta)

        # Tạo response theo format chuẩn
        final_response = {
            "request_meta": final_request_meta,
            "period": period,
            "filters": filters,
            "metrics_data": metrics_data
        }

        print(f"✅ Success: {len(metrics_data)} rows processed.")
        print(f"   Request ID: {final_request_meta['request_id']}")
        
        # --- D. SAVE JSON FILE (Optional) ---
        # Bỏ comment nếu bạn muốn save file
        # json_output_path = f"outputs/metrics_{final_request_meta['request_id']}.json"
        # os.makedirs("outputs", exist_ok=True)
        # with open(json_output_path, 'w', encoding='utf-8') as f:
        #     json.dump(final_response, f, indent=2, ensure_ascii=False)
        # print(f"   Saved to: {json_output_path}")

        # --- E. RESPONSE HỎI CLIENT ---
        # Hiển thị tóm tắt trên UI
        html_response = f"""
        <div>
            <h5 style="color:green">✅ Data Extraction Successful!</h5>
            <p>Found <b>{len(metrics_data)}</b> records.</p>
            <p>Ready for AI Analysis.</p>
            <p style="font-size:0.9em; color:#666;">
                Request ID: <code>{final_request_meta['request_id']}</code>
            </p>
        </div>
        """

        return jsonify({"answer": html_response, "data": final_response})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"answer": f"<div style='color:red'><h5>System Error</h5>{str(e)}</div>"}), 500

# ==============================================================================
# 5. SERVE STATIC FILES
# ==============================================================================

@app.route('/')
def index():
    """Serve index.html"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory(app.static_folder, path)

# ==============================================================================
# 6. ENDPOINT LƯU JSON OUTPUT (Optional - Dùng nếu muốn save file)
# ==============================================================================

# @app.route('/save-metrics-json', methods=['POST'])
# def save_metrics_json():
#     """Save metrics data to JSON file"""
#     try:
#         data = request.json
#         request_id = data.get('request_meta', {}).get('request_id', 'unknown')
        
#         # Tạo thư mục outputs nếu chưa tồn tại
#         output_dir = os.path.join(app.static_folder, 'outputs')
#         os.makedirs(output_dir, exist_ok=True)
        
#         # Lưu file JSON
#         file_path = os.path.join(output_dir, f'metrics_{request_id}.json')
#         with open(file_path, 'w', encoding='utf-8') as f:
#             json.dump(data, f, indent=2, ensure_ascii=False)
        
#         print(f"✅ Saved JSON to: {file_path}")
        
#         return jsonify({
#             "status": "success",
#             "message": f"File saved successfully",
#             "file_path": file_path,
#             "request_id": request_id
#         })
    
#     except Exception as e:
#         print(f"❌ Error saving JSON: {e}")
#         return jsonify({
#             "status": "error",
#             "message": str(e)
#         }), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)