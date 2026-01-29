from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import pyodbc
import os
import json
from datetime import datetime
import uuid
from config.settings import settings  # Load từ .env & settings.py

app = Flask(__name__, static_folder=os.path.dirname(os.path.abspath(__file__)))
CORS(app)

print(f"✅ Settings loaded:")
print(f"   Server: {settings.AZURE_SQL_SERVER}")
print(f"   Database: {settings.AZURE_SQL_DATABASE}")
print(f"   User: {settings.AZURE_SQL_USER}")
print(f"   Driver: {settings.AZURE_SQL_DRIVER}")

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
        # Sử dụng Basic Authentication (username/password)
        conn_str = (
            f"Driver={settings.AZURE_SQL_DRIVER};"
            f"Server={settings.AZURE_SQL_SERVER};"
            f"Database={settings.AZURE_SQL_DATABASE};"
            f"UID={settings.AZURE_SQL_USER};"
            f"PWD={settings.AZURE_SQL_PASSWORD};"
            f"Connection Timeout={settings.AZURE_CONNECT_TIMEOUT};"
        )
        print(f"🔌 Connecting to: {settings.AZURE_SQL_SERVER}/{settings.AZURE_SQL_DATABASE}")
        conn = pyodbc.connect(conn_str)
        print("✅ Connected successfully!")
        return conn
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        raise e

# ==============================================================================
# 3. BUILD QUERY (Lấy 3 cột chính: date, metric_name, metric_value)
# ==============================================================================
def build_query(filters, period_start, period_end):
    """
    Xây dựng SQL query động dựa trên filters
    
    Args:
        filters: Dict {filter_name: value(s)}
        period_start: YYYY-MM-DD
        period_end: YYYY-MM-DD
    
    Returns:
        (sql_query, params_list)
    """
    # SELECT 3 cột chính theo mô hình EAV (Entity-Attribute-Value)
    sql = f"""
        SELECT 
            report_date as date, 
            Metric_Name, 
            Metric_Value 
        FROM {DB_SCHEMA_NAME}.{DB_VIEW_NAME} 
        WHERE 1=1
    """
    
    params = []

    # 1. Xử lý Period (Date Range)
    if period_start and period_end:
        sql += " AND report_date BETWEEN ? AND ?"
        params.append(period_start)
        params.append(period_end)
        print(f"   📅 Period: {period_start} to {period_end}")

    # 2. Xử lý Filters
    print(f"   🔍 Processing {len(filters)} filters:")
    for filter_name, filter_value in filters.items():
        # Bỏ qua filter với giá trị (All) hoặc rỗng
        if not filter_value or filter_value == "(All)" or (isinstance(filter_value, list) and (len(filter_value) == 0 or "(All)" in filter_value)):
            print(f"      - {filter_name}: SKIPPED (All or empty)")
            continue
        
        # Tìm mapping từ filter name sang column name
        db_column = FILTER_COLUMN_MAPPING.get(filter_name)
        if not db_column:
            print(f"      - {filter_name}: NO MAPPING (skipped)")
            continue
        
        # Nếu là list
        if isinstance(filter_value, list):
            clean_values = [v for v in filter_value if v not in ["(All)", ""]]
            if clean_values:
                placeholders = ', '.join(['?' for _ in clean_values])
                sql += f" AND {db_column} IN ({placeholders})"
                params.extend(clean_values)
                print(f"      - {filter_name} IN {clean_values}")
        
        # Nếu là string đơn
        elif isinstance(filter_value, str):
            sql += f" AND {db_column} = ?"
            params.append(filter_value)
            print(f"      - {filter_name} = '{filter_value}'")

    print(f"   ✅ Final SQL: {sql}")
    print(f"   ✅ Final Params: {params}")
    
    return sql, params

# ==============================================================================
# 4. API ENDPOINT
# ==============================================================================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    try:
        req_data = request.json
        print("\n" + "="*80)
        print("📥 RECEIVED REQUEST FROM TABLEAU")
        print("="*80)

        # --- Lấy dữ liệu từ request ---
        request_meta = req_data.get('request_meta', {})
        filters = req_data.get('filters', {})
        period = req_data.get('period', {})
        mode_type = req_data.get('mode_type', 'Analyze Report')
        
        print(f"📋 Mode: {mode_type}")
        print(f"📋 Period: {period}")
        print(f"📋 Filters Keys: {list(filters.keys())}")
        
        p_start = period.get('start_date')
        p_end = period.get('end_date')

        # --- A. BUILD QUERY ---
        print("\n⚙️ BUILDING QUERY...")
        sql, params = build_query(filters, p_start, p_end)

        # --- B. QUERY DATABASE ---
        print(f"\n🔌 CONNECTING TO DATABASE...")
        try:
            conn = get_db_connection()
            
            # Execute query
            print(f"🔄 EXECUTING QUERY...")
            df = pd.read_sql(sql, conn, params=params)
            conn.close()
            
            print(f"✅ Query returned {len(df)} rows")
            
        except Exception as db_error:
            print(f"\n❌ DATABASE ERROR: {str(db_error)}")
            raise db_error

        # --- C. PROCESS DATA ---
        if df.empty:
            print("⚠️ Query returned empty result!")
            metrics_data = []
        else:
            print(f"\n🔄 PROCESSING DATA...")
            
            # 1. Chuẩn hóa date
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            print(f"   ✓ Standardized dates")

            # 2. Filter metrics
            df = df[df['Metric_Name'].isin(METRIC_VALUE_MAPPING.keys())]
            print(f"   ✓ Filtered to {len(df)} valid metrics")
            
            # 3. Map metric names
            df['Metric_Name'] = df['Metric_Name'].map(METRIC_VALUE_MAPPING)
            print(f"   ✓ Mapped metric names")

            # 4. Pivot data
            df_pivot = df.pivot_table(
                index='date', 
                columns='Metric_Name', 
                values='Metric_Value', 
                aggfunc='first'
            ).reset_index()
            print(f"   ✓ Pivoted to {len(df_pivot)} date rows")

            # 5. Fill NaN
            df_pivot = df_pivot.fillna(0)
            
            # 6. Convert to dict
            metrics_data = df_pivot.to_dict(orient='records')
            print(f"   ✓ Converted to {len(metrics_data)} records")

        # --- D. BUILD RESPONSE ---
        print(f"\n📤 BUILDING RESPONSE...")
        final_request_meta = {
            "request_id": generate_request_id(),
            "timestamp": get_iso_timestamp(),
            "mode_type": mode_type
        }
        final_request_meta.update(request_meta)

        final_response = {
            "request_meta": final_request_meta,
            "period": period,
            "filters": filters,
            "metrics_data": metrics_data
        }

        print(f"✅ SUCCESS: Generated response with {len(metrics_data)} metric records")
        print(f"   Request ID: {final_request_meta['request_id']}")
        print("="*80 + "\n")
        
        html_response = f"""
        <div>
            <h5 style="color:green">✅ Data Extraction Successful!</h5>
            <p>Found <b>{len(metrics_data)}</b> date records with metrics.</p>
            <p>Ready for AI Analysis.</p>
            <p style="font-size:0.9em; color:#666;">
                Request ID: <code>{final_request_meta['request_id']}</code>
            </p>
        </div>
        """

        return jsonify({"answer": html_response, "data": final_response})

    except Exception as e:
        import traceback
        print(f"\n❌ ERROR OCCURRED:")
        print(traceback.format_exc())
        print("="*80 + "\n")
        return jsonify({"answer": f"<div style='color:red'><h5>System Error</h5><pre>{str(e)}</pre></div>"}), 500

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