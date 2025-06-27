from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

DB_PATH = 'db/board.db'

def init_db():
    if not os.path.exists('db'):
        os.mkdir('db')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS posts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        category TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/posts', methods=['GET'])
def get_posts():
    conn = sqlite3.connect(DB_PATH)
    posts = conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([{
        'id': p[0], 'title': p[1], 'content': p[2], 'category': p[3], 'created_at': p[4]
    } for p in posts])

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
    socketio.run(app, host='0.0.0.0', port=5000)
