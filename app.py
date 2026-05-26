import os
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'lovetimeline-secret-key-2026'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

DB = 'lovetimeline.db'

# ---------- couple info ----------
COUPLE = {
    'boy':  {'name': '双双', 'birthday': '2004-12-07', 'zodiac': '射手座', 'zodiac_emoji': '🏹'},
    'girl': {'name': '塔塔', 'birthday': '2007-01-08', 'zodiac': '摩羯座', 'zodiac_emoji': '🐐'},
    'together': '2025-11-14',
}

def zodiac_sign(month, day):
    if (month == 12 and day >= 22) or (month == 1 and day <= 19): return ('摩羯座', '🐐')
    if (month == 1 and day >= 20) or (month == 2 and day <= 18): return ('水瓶座', '🏺')
    if (month == 2 and day >= 19) or (month == 3 and day <= 20): return ('双鱼座', '🐟')
    if (month == 3 and day >= 21) or (month == 4 and day <= 19): return ('白羊座', '🐏')
    if (month == 4 and day >= 20) or (month == 5 and day <= 20): return ('金牛座', '🐂')
    if (month == 5 and day >= 21) or (month == 6 and day <= 21): return ('双子座', '👯')
    if (month == 6 and day >= 22) or (month == 7 and day <= 22): return ('巨蟹座', '🦀')
    if (month == 7 and day >= 23) or (month == 8 and day <= 22): return ('狮子座', '🦁')
    if (month == 8 and day >= 23) or (month == 9 and day <= 22): return ('处女座', '🌾')
    if (month == 9 and day >= 23) or (month == 10 and day <= 23): return ('天秤座', '⚖️')
    if (month == 10 and day >= 24) or (month == 11 and day <= 21): return ('天蝎座', '🦂')
    return ('射手座', '🏹')

# ---------- database ----------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nickname TEXT,
            avatar TEXT DEFAULT '/static/uploads/avatars/default.png'
        );

        CREATE TABLE IF NOT EXISTS anniversaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            caption TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        INSERT OR IGNORE INTO users (username, password, nickname) VALUES
            ('kakcoh', '20070108', '双双'),
            ('tyla',   '20041207', '塔塔');

        INSERT OR IGNORE INTO anniversaries (title, date) VALUES
            ('在一起纪念日', '2025-11-14');
    ''')
    db.commit()
    db.close()

def birthday_countdown(birth_str):
    today = date.today()
    bdate = datetime.strptime(birth_str, '%Y-%m-%d').date()
    this_year = bdate.replace(year=today.year)
    if this_year < today:
        this_year = this_year.replace(year=today.year + 1)
    return (this_year - today).days, this_year.year - bdate.year

# ---------- auth ----------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' in session:
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
        db.close()
        return user
    return None

# ---------- routes ----------
@app.route('/')
def index():
    db = get_db()
    anniversaries = db.execute('SELECT * FROM anniversaries ORDER BY date').fetchall()
    timelines = db.execute('SELECT * FROM timeline ORDER BY date DESC').fetchall()
    photos = db.execute('SELECT * FROM photos ORDER BY created_at DESC').fetchall()
    messages = db.execute(
        '''SELECT m.*, u.nickname, u.avatar FROM messages m
           JOIN users u ON m.user_id = u.id ORDER BY m.created_at ASC'''
    ).fetchall()
    user = get_current_user()
    db.close()

    today = date.today()

    # days together
    together_date = datetime.strptime(COUPLE['together'], '%Y-%m-%d').date()
    days_together = (today - together_date).days

    # anniversary countdown
    countdown_days = None
    countdown_title = ''
    for a in anniversaries:
        adate = datetime.strptime(a['date'], '%Y-%m-%d').date()
        next_date = adate.replace(year=today.year)
        if next_date < today:
            next_date = next_date.replace(year=today.year + 1)
        delta = (next_date - today).days
        if countdown_days is None or delta < countdown_days:
            countdown_days = delta
            countdown_title = a['title']

    # birthday countdowns
    b1_days, b1_age = birthday_countdown(COUPLE['boy']['birthday'])
    b1_zodiac = COUPLE['boy']['zodiac']
    b1_zemoji = COUPLE['boy']['zodiac_emoji']
    b2_days, b2_age = birthday_countdown(COUPLE['girl']['birthday'])
    b2_zodiac = COUPLE['girl']['zodiac']
    b2_zemoji = COUPLE['girl']['zodiac_emoji']

    return render_template('index.html',
        user=user, timelines=timelines, photos=photos, messages=messages,
        countdown_days=countdown_days, countdown_title=countdown_title,
        days_together=days_together,
        b1_days=b1_days, b1_age=b1_age, b1_zodiac=b1_zodiac, b1_zemoji=b1_zemoji,
        b2_days=b2_days, b2_age=b2_age, b2_zodiac=b2_zodiac, b2_zemoji=b2_zemoji,
        boy=COUPLE['boy'], girl=COUPLE['girl'], together=COUPLE['together'])

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username=? AND password=?',
            (username, password)
        ).fetchone()
        db.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return render_template('login.html', error='账号或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# ---------- settings ----------
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()
    if request.method == 'POST':
        nickname = request.form.get('nickname', '')
        password = request.form.get('password', '')
        db = get_db()
        if nickname:
            db.execute('UPDATE users SET nickname=? WHERE id=?', (nickname, user['id']))
        if password:
            db.execute('UPDATE users SET password=? WHERE id=?', (password, user['id']))
        file = request.files.get('avatar')
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                filename = f"avatar_{user['id']}.{ext}"
                path = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', filename)
                file.save(path)
                db.execute('UPDATE users SET avatar=? WHERE id=?',
                    (f'/static/uploads/avatars/{filename}', user['id']))
        db.commit()
        db.close()
        return redirect(url_for('settings'))
    return render_template('settings.html', user=user)

# ---------- admin ----------
@app.route('/admin')
@login_required
def admin():
    db = get_db()
    timelines = db.execute('SELECT * FROM timeline ORDER BY date DESC').fetchall()
    photos = db.execute('SELECT * FROM photos ORDER BY created_at DESC').fetchall()
    anniversaries = db.execute('SELECT * FROM anniversaries ORDER BY date').fetchall()
    db.close()
    return render_template('admin.html', user=get_current_user(),
        timelines=timelines, photos=photos, anniversaries=anniversaries)

@app.route('/admin/timeline/add', methods=['POST'])
@login_required
def add_timeline():
    db = get_db()
    db.execute('INSERT INTO timeline (date, title, description) VALUES (?, ?, ?)',
        (request.form['date'], request.form['title'], request.form.get('description', '')))
    db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/admin/timeline/delete/<int:id>', methods=['POST'])
@login_required
def delete_timeline(id):
    db = get_db()
    db.execute('DELETE FROM timeline WHERE id=?', (id,))
    db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/admin/anniversary/add', methods=['POST'])
@login_required
def add_anniversary():
    db = get_db()
    db.execute('INSERT INTO anniversaries (title, date) VALUES (?, ?)',
        (request.form['title'], request.form['date']))
    db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/admin/anniversary/delete/<int:id>', methods=['POST'])
@login_required
def delete_anniversary(id):
    db = get_db()
    db.execute('DELETE FROM anniversaries WHERE id=?', (id,))
    db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/admin/photo/add', methods=['POST'])
@login_required
def add_photo():
    file = request.files.get('photo')
    if file and file.filename:
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'photos', filename))
            db = get_db()
            db.execute('INSERT INTO photos (filename, caption) VALUES (?, ?)',
                (filename, request.form.get('caption', '')))
            db.commit()
            db.close()
    return redirect(url_for('admin'))

@app.route('/admin/photo/delete/<int:id>', methods=['POST'])
@login_required
def delete_photo(id):
    db = get_db()
    photo = db.execute('SELECT * FROM photos WHERE id=?', (id,)).fetchone()
    if photo:
        path = os.path.join(app.config['UPLOAD_FOLDER'], 'photos', photo['filename'])
        if os.path.exists(path):
            os.remove(path)
        db.execute('DELETE FROM photos WHERE id=?', (id,))
        db.commit()
    db.close()
    return redirect(url_for('admin'))

@app.route('/message/send', methods=['POST'])
@login_required
def send_message():
    content = request.form.get('content', '').strip()
    if content:
        db = get_db()
        db.execute('INSERT INTO messages (user_id, content) VALUES (?, ?)',
            (session['user_id'], content))
        db.commit()
        db.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
