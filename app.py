from flask import Flask, render_template, request, redirect, session, url_for,jsonify
import json, os
import secrets
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv



load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
SYSTEM_PROMPT = """Bạn là một trợ lý AI chuyên giám sát hệ thống camera.
Hãy trả lời rõ ràng, chính xác, ngắn gọn. Giúp người dùng giám sát các khu vực bằng camera. 
Chỉ có 2 camera và hệ thống có khả năng cho chọn người để tracking. 
Dùng Yolo và reid và một số thuật toán để hoàn thành hệ thống.
Tạo tại khoảng bằng cách nhấn vào tạo tài khoảng mới. 
Camera dùng là Brio500 của logitech, Jetson orin nano dùng để chạy model yolo và reid lẫn chạy flask cho web này và Jetson nano chỉ việc thẩy frame ảnh qua jetson orin nano bằng rtsp.
"""


def generate_secret_key(length=32):
    return secrets.token_hex(length)

app = Flask(__name__)
app.secret_key = generate_secret_key()
print(app.secret_key)

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

user_memory = {}

user_memory = {}

@app.route('/chat-api', methods=['POST'])
def chat_api():
    user = session.get('user', 'guest')
    data = request.get_json()
    message = data.get('message', '')

    # Nếu chưa có memory cho người dùng này, tạo mới
    if user not in user_memory:
        user_memory[user] = ConversationChain(
            llm=llm,
            memory=ConversationBufferMemory(),
            verbose=False,
            prompt=PromptTemplate(
                input_variables=["history", "input"],
                template=(
                    SYSTEM_PROMPT + "\n\n"
                    "Lịch sử trò chuyện:\n{history}\n"
                    "Người dùng: {input}\nTrợ lý:"
                )
            )
        )

    chain = user_memory[user]
    response = chain.run(message)

    return jsonify({"reply": response})


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            session['user'] = username
            session['role'] = users[username]['role']
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Sai tài khoản hoặc mật khẩu.")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'], role=session['role'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if session.get('role') != 'admin':
        return "Không có quyền truy cập", 403
    return render_template('admin_panel.html')

@app.route('/add-user', methods=['GET', 'POST'])
def add_user():
    users = load_users()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            return render_template('add_user.html', error="Tên người dùng đã tồn tại!")
        users[username] = {"password": password, "role": "user"}
        save_users(users)
        return redirect(url_for('login'))
    return render_template('add_user.html')

if __name__ == '__main__':
 #   app.run(debug=True)
    app.run(host="0.0.0.0", port=10000)
