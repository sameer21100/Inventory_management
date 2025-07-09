from flask import Flask, render_template, request, jsonify, redirect, session
from flask_socketio import SocketIO, emit
import sqlite3
import os
from werkzeug.utils import secure_filename
import secrets


#Trie Implementation

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

class TagTrie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, tag):
        node = self.root
        for char in tag.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def suggest(self, prefix):
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        return self._collect(node, prefix.lower())

    def _collect(self, node, prefix):
        results = []
        if node.is_end_of_word:
            results.append(prefix)
        for char, child in node.children.items():
            results.extend(self._collect(child, prefix + char))
        return results
    
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

socketio = SocketIO(app, cors_allowed_origins='*')

DB_PATH = 'db/board.db'
posts = []
def init_db():
    if not os.path.exists('db'):
        os.makedirs('db')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT,
        image TEXT,
        priority INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()
show = False  # Default state: posts are hidden




@app.route('/', methods=['GET', 'POST'])
def index():
    global show
    if request.method == 'POST':
        if 'show' in request.form:
            show = True
        elif 'hide' in request.form:
            show = False
        else:
            # Create post
            title = request.form['title']
            category = request.form['category']
            content = request.form['content']
            image = request.files.get('image')
            image_filename = None
            priority = int(request.form.get('priority', 1))

            if image and image.filename != '':
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

            # Save to DB
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO posts (title, content, category, image, priority)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, content, category, image_filename, priority))
            conn.commit()
            conn.close()

        return redirect('/')

    # GET method


    posts_data = []
    if show:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, content, category, image, priority, created_at 
            FROM posts 
            WHERE DATE(created_at) >= DATE('now', '-2 days')
            ORDER BY priority DESC, created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        posts_data = [{
            'id': row[0],
            'title': row[1],
            'content': row[2],
            'category': row[3],
            'image': row[4],
            'priority': row[5],
            'created_at': row[6]
        } for row in rows]

    return render_template('index.html', posts=posts_data, show=show, tag=None, user=session.get('user'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # ✅ initialize

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect('/')
        else:
            error = 'Invalid username or password' 

    return render_template('login.html', error=error)  


# --- Logout route ---
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


@app.route('/search')
def search_by_tag():
    tag = request.args.get('tag', '').strip()
    posts_data = []

    if tag:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, content, category, image, created_at 
            FROM posts 
            WHERE category LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{tag}%',))
        rows = cursor.fetchall()
        conn.close()

        posts_data = [{
            'title': row[0],
            'content': row[1],
            'category': row[2],
            'image': row[3],
            'created_at': row[4]
        } for row in rows]

    return render_template('index.html', posts=posts_data, show=True, tag=tag, user=session.get('user'))


# --- /range route for tag + date range filtering ---
@app.route('/range')
def posts_by_date_range():
    start = request.args.get('start')
    end = request.args.get('end')
    tag = request.args.get('tag', '').strip()
    posts_data = []

    query = '''
        SELECT title, content, category, image, created_at 
        FROM posts 
        WHERE 1 = 1
    '''
    params = []

    if tag:
        query += ' AND category LIKE ?'
        params.append(f'%{tag}%')

    if start and end:
        query += ' AND DATE(created_at) BETWEEN DATE(?) AND DATE(?)'
        params.extend([start, end])
        tag = f"{tag} (From {start} to {end})" if tag else f"From {start} to {end}"

    query += ' ORDER BY created_at DESC'

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    posts_data = [{
        'title': row[0],
        'content': row[1],
        'category': row[2],
        'image': row[3],
        'created_at': row[4]
    } for row in rows]

    return render_template('index.html', posts=posts_data, show=True, tag=tag, user=session.get('user'))


@app.route('/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()

    return redirect('/')


@app.route('/posts', methods=['GET'])
def get_posts():
    conn = sqlite3.connect(DB_PATH)
    posts = conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([{
            'id': p[0], 'title': p[1], 'content': p[2], 'category': p[3], 'image': p[4], 'created_at': p[5]
    } for p in posts])



@app.route('/suggest', methods=['GET'])
def suggest():
    prefix = request.args.get('prefix', '').strip()
    trie = TagTrie()

    # Load all categories (tags) from DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT category FROM posts WHERE category IS NOT NULL')
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Insert categories into Trie
    for tag in categories:
        trie.insert(tag)

    return jsonify(trie.suggest(prefix))



@app.route('/posts', methods=['POST'])
def add_post():
    data = request.get_json()
    priority = int(data.get('priority', 1))
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO posts (title, content, category, priority) VALUES (?, ?, ?, ?)",
                 (data['title'], data['content'], data['category'], priority))
    conn.commit()
    conn.close()
    socketio.emit('new_post', data, broadcast=True)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=6060)
