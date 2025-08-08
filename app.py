from flask import Flask, render_template, request, redirect, session, url_for, jsonify, Response
import json, os
import secrets
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
import cv2
import threading
import subprocess


# Khai báo API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDmYy5FP4sY1Te1OX1OPtKcFWNfAcY0hbI"
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

SYSTEM_PROMPT = """Bạn là một trợ lý AI chuyên giám sát hệ thống camera.
Hãy trả lời rõ ràng, chính xác, ngắn gọn. Giúp người dùng giám sát các khu vực bằng camera. 
Tạo tại khoảng bằng cách nhấn vào tạo tài khoảng mới.
!!Quan trọng: Khi cần liên hệ khẩn cấp cho admin hãy liên hệ số (+84) 985971459
Nếu quên mật khẩu thì liên hệ với admin hoặc tạo tài khoản mới luôn cho nhanh.
Nếu ai hỏi bạn LLM gì? Thì bạn trả lời: là dùng API của google cụ thể là Gemini 2.0 Flash.
Nếu hỏi ngày giờ thì gợi ý người ta nhìn góc trên bên trái.
Nếu người ta hỏi về kĩ thuật thì hãy trả lời dựa vào những - bên dưới:
- Chỉ có 2 camera do đang mô phỏng và hệ thống có khả năng cho chọn người để tracking. 
- Dùng Yolo và reid và một số thuật toán để hoàn thành hệ thống. 
- Camera dùng là Brio500 của logitech. 
- Jetson orin nano và Jetson nano dùng để thực hiện hệ thống khi người ta hỏi dùng gì với camera hay máy tính nhúng gì.
- Dùng webocket với flask của python khi muốn làm giao diện web và ngrok để public.
"""

camera = cv2.VideoCapture(0)  # 0 là camera mặc định (webcam)

def generate_secret_key(length=32):
    return secrets.token_hex(length)

app = Flask(__name__)
app.secret_key = generate_secret_key()

USERS_FILE = 'users.json'



def generate_frames():
   

    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode frame thành JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Trả về frame dạng multipart
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')



# Load và lưu người dùng
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}

def save_users(users):
    # Sắp xếp admin trước, user sau
    sorted_users = dict(
        sorted(users.items(), key=lambda item: 0 if item[1]['role'] == 'admin' else 1)
    )
    with open(USERS_FILE, 'w') as f:
        json.dump(sorted_users, f, indent=4)


@app.route('/sudoku')
def sudoku():
    return render_template('sudoku.html')

# Bộ nhớ hội thoại
user_memory = {}

@app.route('/chat-api', methods=['POST'])
def chat_api():
    user = session.get('user', 'guest')
    data = request.get_json()
    message = data.get('message', '')

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

# Trang đăng nhập
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            session['user'] = username
            session['role'] = users[username]['role']
            # 🔁 Chuyển hướng theo vai trò
            if session['role'] == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('dashboard'))
        return render_template('login.html', error="Sai tài khoản hoặc mật khẩu.")
    return render_template('login.html')
# Dashboard chính
@app.route('/dashboard')
def dashboard():
    role = session.get('role')
    user = session.get('user')

    if role == 'admin':
        return redirect(url_for('admin_panel'))  # Admin -> Trang quản trị

    # Người dùng thường -> Giao diện camera
    return render_template('user.html', user=user, role=role)

# Đăng xuất
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Admin panel mới với giao diện bên trái
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if session.get('role') != 'admin':
        return "Không có quyền truy cập", 403
    return render_template('admin_panel.html', user=session['user'])

@app.route('/quan-ly-user')
def quan_ly_user():
    if session.get('role') != 'admin':
        return "Không có quyền truy cập", 403
    users = load_users()
    total_admins = sum(1 for u in users.values() if u['role'] == 'admin')
    return render_template('quan_ly_user.html', users=users, total_admins=total_admins)

@app.route('/xoa-user/<username>', methods=['POST'])
def delete_user(username):
    if session.get('role') != 'admin':
        return "Không có quyền truy cập", 403

    users = load_users()
    if username in users:
        # Không cho xóa admin cuối cùng
        if users[username]['role'] == 'admin':
            admin_count = sum(1 for u in users.values() if u['role'] == 'admin')
            if admin_count <= 1:
                return "Không thể xóa admin cuối cùng!", 400
        users.pop(username)
        save_users(users)
    return redirect(url_for('quan_ly_user'))

@app.route('/add-admin', methods=['GET', 'POST'])
def add_admin():
    if session.get('role') != 'admin':
        return "Không có quyền truy cập", 403

    users = load_users()
    current_user = session.get('user')

    if request.method == 'POST':
        confirm_password = request.form['confirm_password']
        new_username = request.form['username']
        new_password = request.form['password']

        # Kiểm tra lại mật khẩu của admin hiện tại
        if users[current_user]['password'] != confirm_password:
            return render_template('add_admin.html', error="Mật khẩu xác nhận không đúng!")

        # Kiểm tra trùng tên
        if new_username in users:
            return render_template('add_admin.html', error="Tên người dùng đã tồn tại!")

        # Thêm admin mới
        users[new_username] = {"password": new_password, "role": "admin"}
        save_users(users)
        return redirect(url_for('quan_ly_user'))

    return render_template('add_admin.html')

@app.route('/doi-mat-khau/<username>', methods=['GET', 'POST'])
def doi_mat_khau_user(username):
    if session.get('role') != 'admin':
        return "Không có quyền truy cập", 403

    users = load_users()
    if username not in users:
        return "Người dùng không tồn tại", 404

    is_self = (session['user'] == username)
    error = None

    if request.method == 'POST':
        if is_self:
            old_password = request.form['old_password']
            if users[username]['password'] != old_password:
                error = "Mật khẩu cũ không đúng!"
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            error = "Mật khẩu mới không khớp!"
        elif not error:
            users[username]['password'] = new_password
            save_users(users)
            return redirect(url_for('quan_ly_user'))

    return render_template('doi_mat_khau_user.html', username=username, error=error, is_self=is_self)



# Thêm người dùng
@app.route('/add-user', methods=['GET', 'POST'])
@app.route('/add-user', methods=['GET', 'POST'])
def add_user():
    users = load_users()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm']  # lấy giá trị xác nhận mật khẩu

        if username in users:
            return render_template('add_user.html', error="Tên người dùng đã tồn tại!")

        if password != confirm:
            return render_template('add_user.html', error="Mật khẩu xác nhận không khớp!")

        users[username] = {"password": password, "role": "user"}
        save_users(users)
        return redirect(url_for('login'))
    
    return render_template('add_user.html')

def run_label_studio():
    subprocess.Popen(["label-studio"], stdout=subprocess.DEVNULL)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start-label')
def start_label():
    threading.Thread(target=run_label_studio).start()
    return redirect("http://localhost:8080", code=302)

if __name__ == '__main__':
    try:
       # app.run(debug=True)
        app.run(port=5000)
    finally:
        camera.release()