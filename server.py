from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json

# Định nghĩa thư mục static
current_directory = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=current_directory)
CORS(app)

# --- Serve Frontend ---
@app.route('/')
def index():
    return send_from_directory(current_directory, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(current_directory, path)

# --- API Backend (MOCK - Chỉ nhận và in ra) ---
@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    try:
        # 1. Nhận dữ liệu từ Extension
        data = request.json
        
        # 2. IN RA TERMINAL (Đây là bước quan trọng để bạn Check)
        print("\n" + "="*50)
        print("📥 RECEIVED PAYLOAD FROM TABLEAU:")
        print(json.dumps(data, indent=4, ensure_ascii=False))
        print("="*50 + "\n")

        # 3. Lấy thử vài giá trị để confirm
        filters = data.get('filters', {})
        project_id = filters.get('Project Identifier', ['N/A'])
        
        # 4. Trả lời lại cho UI biết là đã nhận được
        response_msg = f"Backend đã nhận được Filter!<br>Project đang chọn: <b>{project_id}</b>"
        
        return jsonify({"answer": response_msg})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"answer": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)