import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3 as sql

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# 업로드 폴더가 존재하는지 확인
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def init_db():
    with sql.connect('database.db') as con:
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        password TEXT,
                        instructions TEXT,
                        interests TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS photos (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        filename TEXT,
                        description TEXT,
                        keywords TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY,
                        sender_id INTEGER,
                        receiver_id INTEGER,
                        content TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        con.commit()

def reset_db():
    with sql.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS users")
        cur.execute("DROP TABLE IF EXISTS photos")
        cur.execute("DROP TABLE IF EXISTS messages")
        con.commit()
    init_db()

# 데이터베이스를 초기화 (예: 첫 실행 시 또는 스키마 변경 시)
# reset_db()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sql.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            con.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sql.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cur.fetchone()
            if user:
                session['username'] = username
                session['user_id'] = user[0]
                return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    with sql.connect('database.db') as con:
        cur = con.cursor()
        # 게시물 정보와 함께 사용자 이름도 가져오기 위한 SQL 쿼리
        cur.execute("SELECT p.*, u.username FROM photos p JOIN users u ON p.user_id = u.id")
        photos = cur.fetchall()
    return render_template('dashboard.html', photos=photos)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files['file']
        description = request.form['description']
        keywords = request.form['keywords']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            with sql.connect('database.db') as con:
                cur = con.cursor()
                cur.execute("INSERT INTO photos (user_id, filename, description, keywords) VALUES (?, ?, ?, ?)", 
                            (session['user_id'], filename, description, keywords))
                con.commit()
            return redirect(url_for('dashboard'))
    return render_template('upload.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    with sql.connect('database.db') as con:
        cur = con.cursor()
        if request.method == 'POST':
            instructions = request.form['instructions']
            interests = request.form['interests']
            cur.execute("UPDATE users SET instructions = ?, interests = ? WHERE id = ?", (instructions, interests, user_id))
            con.commit()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cur.fetchone()
        cur.execute("SELECT * FROM photos WHERE user_id = ?", (user_id,))
        photos = cur.fetchall()
    return render_template('profile.html', user=user, photos=photos)

@app.route('/user_profile/<username>')
def user_profile(username):
    with sql.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if user:
            cur.execute("SELECT * FROM photos WHERE user_id = ?", (user[0],))
            photos = cur.fetchall()
            return render_template('user_profile.html', user=user, photos=photos)
        else:
            return "User not found"


@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    with sql.connect('database.db') as con:
        cur = con.cursor()
        if request.method == 'POST':
            description = request.form['description']
            keywords = request.form['keywords']
            file = request.files['file']  # 새로운 파일을 선택했을 경우
            if file:
                # 기존 사진 파일 삭제
                cur.execute("SELECT filename FROM photos WHERE id = ?", (post_id,))
                filename = cur.fetchone()[0]
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                # 새로운 사진 저장
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                cur.execute("UPDATE photos SET filename = ?, description = ?, keywords = ? WHERE id = ?", 
                            (filename, description, keywords, post_id))
            else:
                cur.execute("UPDATE photos SET description = ?, keywords = ? WHERE id = ?", 
                            (description, keywords, post_id))
            con.commit()
            return redirect(url_for('profile'))
        cur.execute("SELECT * FROM photos WHERE id = ?", (post_id,))
        photo = cur.fetchone()
    return render_template('edit_post.html', photo=photo)


@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    with sql.connect('database.db') as con:
        cur = con.cursor()
        # 삭제할 사진의 파일 이름 가져오기
        cur.execute("SELECT filename FROM photos WHERE id = ?", (post_id,))
        filename = cur.fetchone()[0]
        # 업로드 폴더에서 사진 파일 삭제
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # 데이터베이스에서 사진 레코드 삭제
        cur.execute("DELETE FROM photos WHERE id = ?", (post_id,))
        con.commit()
    return redirect(url_for('profile'))

@app.route('/messages', methods=['GET', 'POST'])
def messages():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    chat_user_id = request.args.get('chat_user_id', type=int)
    
    with sql.connect('database.db') as con:
        cur = con.cursor()
        
        # 대화 상대 목록 가져오기
        cur.execute("""
            SELECT DISTINCT u.id, u.username
            FROM users u
            JOIN messages m ON u.id = m.sender_id OR u.id = m.receiver_id
            WHERE u.id != ?
        """, (user_id,))
        chat_users = cur.fetchall()

        messages = []
        chat_user_name = ""

        if chat_user_id:
            # 선택된 대화 상대와의 메시지 가져오기
            cur.execute("""
                SELECT m.id, m.sender_id, m.receiver_id, m.content, m.timestamp, u.username AS sender_username
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE (m.receiver_id = ? AND m.sender_id = ?) OR (m.receiver_id = ? AND m.sender_id = ?)
                ORDER BY m.timestamp ASC
            """, (user_id, chat_user_id, chat_user_id, user_id))
            messages = cur.fetchall()

            # 대화 상대 이름 가져오기
            cur.execute("SELECT username FROM users WHERE id = ?", (chat_user_id,))
            chat_user_name = cur.fetchone()[0]
        
    return render_template('messages.html', chat_users=chat_users, messages=messages, chat_user_id=chat_user_id, chat_user_name=chat_user_name)

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return redirect(url_for('login'))
    sender_id = session['user_id']
    receiver_id = request.form['receiver_id']
    content = request.form['content']
    with sql.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)", 
                    (sender_id, receiver_id, content))
        con.commit()
    return redirect(url_for('messages', chat_user_id=receiver_id))

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    with sql.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        con.commit()
    return redirect(request.referrer or url_for('messages'))


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        keyword = request.form['keyword']
        with sql.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM photos WHERE keywords LIKE ?", ('%' + keyword + '%',))
            photos = cur.fetchall()
        return render_template('search_results.html', photos=photos)
    return render_template('search.html')

@app.route('/user_list', methods=['GET', 'POST'])
def user_list():
    if request.method == 'POST':
        search_keyword = request.form['search_keyword']
        with sql.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("SELECT username, instructions, interests FROM users WHERE username LIKE ?", ('%' + search_keyword + '%',))
            users = cur.fetchall()
        return render_template('user_list.html', users=users, search_keyword=search_keyword)
    else:
        with sql.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("SELECT username, instructions, interests FROM users")
            users = cur.fetchall()
        return render_template('user_list.html', users=users, search_keyword=None)


@app.route('/send_post_message/<int:post_id>', methods=['POST'])
def send_post_message(post_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    sender_id = session['user_id']
    content = request.form['content']
    with sql.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("SELECT user_id FROM photos WHERE id = ?", (post_id,))
        receiver = cur.fetchone()
        if receiver:
            receiver_id = receiver[0]
            if sender_id == receiver_id:
                return redirect(url_for('dashboard'))
            cur.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                        (sender_id, receiver_id, content))
            con.commit()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
