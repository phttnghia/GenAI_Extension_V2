from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import pyodbc
import os
import json
from datetime import datetime
from config.settings import settings
import uuid

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

# 1b. Mapping Filter Display Name: Tên Filter UI -> Tên hiển thị trong JSON (Dùng cho Response)
# Dùng để normalize filter names trong JSON response
FILTER_DISPLAY_NAME_MAPPING = {
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

def normalize_filter_names(filters):
    """
    Map filter display names to short names for JSON response
    Example: "Filter 1 (Vw Bug Report By Testplan)" -> "filter_1"
    """
    normalized = {}
    for filter_name, filter_value in filters.items():
        # Get short display name from mapping, or keep original if not found
        short_name = FILTER_DISPLAY_NAME_MAPPING.get(filter_name, filter_name)
        normalized[short_name] = filter_value
    return normalized

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
        conn_str = (
            f"DRIVER={settings.AZURE_SQL_DRIVER};"
            f"SERVER={settings.AZURE_SQL_SERVER};"
            f"DATABASE={settings.AZURE_SQL_DATABASE};"
            f"UID={settings.AZURE_SQL_USER};"
            f"PWD={settings.AZURE_SQL_PASSWORD};"
            f"Connection Timeout={settings.AZURE_CONNECT_TIMEOUT};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
        )

        return pyodbc.connect(conn_str)

    except Exception as e:
        print("❌ Database Connection Error")
        print(e)
        raise


# ==============================================================================
# 3. BUILD QUERY (Query từ EAV Model)
# ==============================================================================
def build_query(filters, period_start, period_end):
    """
    Build dynamic SQL query based on filters
    
    Filter names từ app.js được map như sau:
      - "Redmine Infra" -> column "redmine_infra"
      - "Redmine Server" -> column "redmine_server"
      - "Redmine Instance" -> column "redmine_instance"
      - "Project Identifier" -> column "project_identifier"
      - "Filter 1 (Vw Bug Report By Testplan)" -> column "filter_1"
      ...
    """
    # SELECT 3 cột chính từ EAV model
    sql = f"""
        SELECT 
            date, 
            Metric_Name, 
            Metric_Value 
        FROM [{DB_SCHEMA_NAME}].[{DB_VIEW_NAME}]
        WHERE 1=1
            AND date IS NOT NULL
    """
    
    params = []

    # 1. XỬ LÝ PERIOD (DATE RANGE) - Chỉ thêm nếu cả hai date được cung cấp
    if period_start and period_end:
        sql += " AND date BETWEEN ? AND ?"
        params.append(period_start)
        params.append(period_end)
        print(f"   📅 Period filter: {period_start} to {period_end}")
    else:
        print(f"   📅 Period filter: NONE (will fetch all available data)")

    # 2. XỬ LÝ FILTERS
    print(f"   🔍 Processing {len(filters)} filters:")
    for filter_name, filter_value in filters.items():
        # Tìm mapping từ filter name (từ dashboard) sang column name (trong DB)
        db_column = FILTER_COLUMN_MAPPING.get(filter_name)
        
        if not db_column:
            # Nếu không có mapping, skip
            print(f"      ⊘ {filter_name}: NO MAPPING (skipped)")
            continue
        
        # Bỏ qua nếu value là (All) hoặc rỗng
        if not filter_value or filter_value == "(All)" or filter_value == ["(All)"] or filter_value == []:
            print(f"      ⊘ {filter_name}: ALL VALUES (skipped)")
            continue
        
        # Xử lý list values
        if isinstance(filter_value, list):
            clean_values = [v for v in filter_value if v and v != "(All)"]
            if clean_values:
                placeholders = ', '.join(['?' for _ in clean_values])
                sql += f" AND [{db_column}] IN ({placeholders})"
                params.extend(clean_values)
                print(f"      ✓ {filter_name} IN ({', '.join(clean_values)})")
        
        # Xử lý string value
        elif isinstance(filter_value, str):
            sql += f" AND [{db_column}] = ?"
            params.append(filter_value)
            print(f"      ✓ {filter_name} = '{filter_value}'")
    
    print(f"\n   ✅ Final SQL:\n{sql}")
    print(f"   ✅ Params: {params}\n")
    
    return sql, params

# ==============================================================================
# 4. API ENDPOINT
# ==============================================================================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    try:
        print("\n" + "="*80)
        print("📥 REQUEST FROM TABLEAU EXTENSION")
        print("="*80)
        
        req_data = request.json
        request_meta = req_data.get('request_meta', {})
        filters = req_data.get('filters', {})
        period = req_data.get('period', {})
        mode_type = req_data.get('mode_type', 'Analyze Report')
        
        print(f"Mode: {mode_type}")
        print(f"Period: {period}")
        print(f"Filters: {list(filters.keys())}")
        
        p_start = period.get('start_date')
        p_end = period.get('end_date')

        # ===== A. BUILD & EXECUTE QUERY =====
        print("\n⚙️ STEP 1: BUILD QUERY")
        print("-" * 80)
        sql, params = build_query(filters, p_start, p_end)

        print("\n🔌 STEP 2: CONNECT & QUERY DATABASE")
        print("-" * 80)
        try:
            conn = get_db_connection()
            print("   ✓ Connected")
            
            df = pd.read_sql(sql, conn, params=params)
            conn.close()
            print(f"   ✓ Query returned {len(df)} rows")
            
            if len(df) > 0:
                print(f"   ✓ Date range in raw data: {df['date'].min()} to {df['date'].max()}")
                print(f"   ✓ Unique Metric_Names: {df['Metric_Name'].unique().tolist()}")
                print(f"   ✓ Sample data:\n{df.head(10)}")
            
        except Exception as db_err:
            print(f"   ❌ Database error: {str(db_err)}")
            raise

        # ===== B. PROCESS DATA =====
        if df.empty:
            print("\n⚠️ STEP 3: PROCESS DATA")
            print("-" * 80)
            print("   ⊘ No data returned from query")
            metrics_data = []
        else:
            print("\n📊 STEP 3: PROCESS DATA (EAV → Wide Format)")
            print("-" * 80)
            
            # 1. Clean & standardize dates
            print("   Step 3.1: Standardize dates...")
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            date_min = df['date'].min()
            date_max = df['date'].max()
            print(f"      ✓ Date range: {date_min} to {date_max}")
            print(f"      ✓ Total unique dates: {df['date'].nunique()}")

            # 2. Filter valid metrics
            print("   Step 3.2: Filter valid metrics...")
            valid_metrics = list(METRIC_VALUE_MAPPING.keys())
            print(f"      Expected metrics: {valid_metrics}")
            metrics_in_data = df['Metric_Name'].unique().tolist()
            print(f"      Metrics in data: {metrics_in_data}")
            
            df_before = len(df)
            df = df[df['Metric_Name'].isin(valid_metrics)]
            df_after = len(df)
            print(f"      ✓ Filtered: {df_before} → {df_after} rows")
            
            if df_after == 0:
                print("      ⚠️ WARNING: No valid metrics found after filtering!")
                metrics_data = []
            else:
                # 3. Map metric names (if needed)
                print("   Step 3.3: Map metric names...")
                df['Metric_Name'] = df['Metric_Name'].map(METRIC_VALUE_MAPPING)
                print(f"      ✓ Mapped")

                # 4. Convert Metric_Value to numeric
                print("   Step 3.4: Convert Metric_Value to numeric...")
                df['Metric_Value'] = pd.to_numeric(df['Metric_Value'], errors='coerce')
                print(f"      ✓ Converted")

                # 5. Pivot: EAV to Wide format
                print("   Step 3.5: Pivot data (EAV → Wide)...")
                df_pivot = df.pivot_table(
                    index='date',
                    columns='Metric_Name',
                    values='Metric_Value',
                    aggfunc='first'
                ).reset_index()
                print(f"      ✓ Pivoted: {len(df_pivot)} date rows × {len(df_pivot.columns)-1} metrics")
                print(f"      ✓ Columns: {df_pivot.columns.tolist()}")

                # 6. Fill NaN & Convert to int/float
                print("   Step 3.6: Clean & convert types...")
                df_pivot = df_pivot.fillna(0)
                # Convert numeric columns to numeric type
                for col in df_pivot.columns:
                    if col != 'date':
                        df_pivot[col] = pd.to_numeric(df_pivot[col], errors='coerce').fillna(0).astype(int)
                print(f"      ✓ Ready for output")
                print(f"      ✓ Data types:\n{df_pivot.dtypes}")

                # 7. Sort by date and convert to list of dicts
                df_pivot = df_pivot.sort_values('date').reset_index(drop=True)
                metrics_data = df_pivot.to_dict(orient='records')
                print(f"      ✓ Converted to {len(metrics_data)} records")
                if len(metrics_data) > 0:
                    print(f"      ✓ First record: {metrics_data[0]}")
                    print(f"      ✓ Last record: {metrics_data[-1]}")

        # ===== C. BUILD RESPONSE =====
        print("\n📤 STEP 4: BUILD JSON RESPONSE")
        print("-" * 80)
        
        # Calculate actual period from data (min and max dates)
        actual_period = period.copy() if period else {}
        if metrics_data and len(metrics_data) > 0:
            dates = [record.get('date') for record in metrics_data if record.get('date')]
            if dates:
                dates_sorted = sorted(dates)
                actual_period['start_date'] = dates_sorted[0]
                actual_period['end_date'] = dates_sorted[-1]
                print(f"   ✓ Actual period from data: {actual_period['start_date']} to {actual_period['end_date']}")
        
        final_request_meta = {
            "request_id": generate_request_id(),
            "timestamp": get_iso_timestamp(),
            "mode_type": mode_type
        }
        final_request_meta.update(request_meta)

        # Normalize filter names for response
        normalized_filters = normalize_filter_names(filters)

        final_response = {
            "request_meta": final_request_meta,
            "period": actual_period,
            "filters": normalized_filters,
            "metrics_data": metrics_data
        }

        print(f"   ✓ Generated response")
        print(f"   Request ID: {final_request_meta['request_id']}")
        print(f"   Records: {len(metrics_data)}")
        print(f"   Normalized filters: {list(normalized_filters.keys())}")
        print("="*80 + "\n")

        html_response = f"""
        <div style="text-align:left;">
            <div style="background:#e8f5e9; padding:12px; border-left:4px solid #4caf50; margin-bottom:10px; border-radius:4px;">
                <h5 style="margin:0; color:#2e7d32;">✅ Data Extraction Successful!</h5>
                <p style="margin:5px 0; color:#555;">
                    Found <b>{len(metrics_data)}</b> date records with metrics.
                </p>
                <p style="margin:5px 0; font-size:0.9em; color:#666;">
                    Request ID: <code style="background:#fff; padding:2px 4px; border-radius:2px;">{final_request_meta['request_id']}</code>
                </p>
            </div>
        </div>
        """

        return jsonify({"answer": html_response, "data": final_response})

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"\n❌ ERROR OCCURRED:")
        print(error_msg)
        print("="*80 + "\n")
        
        return jsonify({
            "answer": f"<div style='color:#c62828; background:#ffebee; padding:12px; border-left:4px solid #c62828; border-radius:4px;'><h5 style='margin:0;'>❌ System Error</h5><pre style='margin:8px 0; font-size:0.85em; overflow-x:auto;'>{str(e)}</pre></div>"
        }), 500

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