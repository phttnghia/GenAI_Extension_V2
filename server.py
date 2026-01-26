from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
import os
import json



current_directory = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=current_directory)
CORS(app)

# --- PHẦN 1: (FRONTEND) ---

@app.route('/')
def index():
    return send_from_directory(current_directory, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(current_directory, path)

# --- PHẦN 2:  (BACKEND) ---



@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    data = request.json
    # --- THÊM ĐOẠN NÀY ĐỂ DEBUG ---
    print("----- RECEIVED PAYLOAD -----")
    # In toàn bộ JSON ra màn hình console của Python, format đẹp dễ nhìn
    print(json.dumps(data, indent=4, ensure_ascii=False)) 
    print("----------------------------")
    # ------------------------------
    user_question = data.get('question')
    chart_data = data.get('context_data')

    print(f"Receive questions: {user_question}")


    mock_html = """
    <div class="alert alert-danger">
        <h5>Error: Failed to load error analysis report</h5>
        <p>Error details: Database connection failed. Please check the database connection and try again later.</p>
    </div>
    """
    return jsonify({"answer": mock_html})

if __name__ == '__main__':
    app.run(port=5000, debug=True)