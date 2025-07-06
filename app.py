from flask import Flask, render_template, request, jsonify,redirect
from flask_socketio import SocketIO, emit
import sqlite3
import os
from werkzeug.utils import secure_filename


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

            if image and image.filename != '':
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

            # Save to DB
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO posts (title, content, category, image)
                VALUES (?, ?, ?, ?)
            ''', (title, content, category, image_filename))
            conn.commit()
            conn.close()

        return redirect('/')

    # GET method
    posts_data = []
    if show:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, content, category, image, created_at 
            FROM posts ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        posts_data = [{
            'title': row[0],
            'content': row[1],
            'category': row[2],
            'image': row[3],
            'created_at': row[4]
        } for row in rows]

    return render_template('index.html', posts=posts_data, show=show, tag=None)


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

    return render_template('index.html', posts=posts_data, show=True, tag=tag)

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
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO posts (title, content, category) VALUES (?, ?, ?)",
                 (data['title'], data['content'], data['category']))
    conn.commit()
    conn.close()
    socketio.emit('new_post', data, broadcast=True)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=6060)
