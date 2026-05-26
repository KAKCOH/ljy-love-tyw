import os
import base64
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'lovetimeline-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.template_filter('datestr')
def datestr(value):
    """Format a datetime or string to YYYY-MM-DD for templates."""
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]

@app.template_filter('datetimestr')
def datetimestr(value):
    """Format a datetime or string to YYYY-MM-DD HH:MM for templates."""
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M')
    return str(value)[:16]

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
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = bool(DATABASE_URL)

def get_db():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect('lovetimeline.db')
        conn.row_factory = sqlite3.Row
        return conn

def db_execute(sql, params=(), fetch=False, fetchone=False, commit=False):
    """Unified DB helper that works with both SQLite and PostgreSQL."""
    db = get_db()
    try:
        if USE_POSTGRES:
            import psycopg2.extras
            # Convert ? placeholders to %s for PostgreSQL
            sql_pg = sql.replace('?', '%s')
            cur = db.cursor()
            cur.execute(sql_pg, params)
            if commit:
                db.commit()
            if fetchone:
                row = cur.fetchone()
                if row:
                    cols = [desc[0] for desc in cur.description]
                    return dict(zip(cols, row))
                return None
            if fetch:
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, r)) for r in rows]
            cur.close()
        else:
            cur = db.cursor()
            cur.execute(sql, params)
            if commit:
                db.commit()
            if fetchone:
                return cur.fetchone()
            if fetch:
                return cur.fetchall()
            cur.close()
    finally:
        db.close()

def init_db():
    if USE_POSTGRES:
        db = get_db()
        cur = db.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nickname TEXT,
                avatar_data TEXT DEFAULT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS anniversaries (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS timeline (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT ''
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id SERIAL PRIMARY KEY,
                image_data TEXT NOT NULL,
                mimetype TEXT DEFAULT 'image/jpeg',
                caption TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        # Seed users only if not exists
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO users (username, password, nickname) VALUES (%s, %s, %s), (%s, %s, %s)",
                ('kakcoh', '20070108', '双双', 'tyla', '20041207', '塔塔'))
            cur.execute(
                "INSERT INTO anniversaries (title, date) VALUES (%s, %s)",
                ('在一起纪念日', '2025-11-14'))
            db.commit()
        cur.close()
        db.close()
    else:
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nickname TEXT,
                avatar_data TEXT DEFAULT NULL
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
                image_data TEXT NOT NULL,
                mimetype TEXT DEFAULT 'image/jpeg',
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
        return db_execute('SELECT * FROM users WHERE id=?', (session['user_id'],), fetchone=True)
    return None

# ---------- routes ----------
@app.route('/')
def index():
    anniversaries = db_execute('SELECT * FROM anniversaries ORDER BY date', fetch=True)
    timelines = db_execute('SELECT * FROM timeline ORDER BY date DESC', fetch=True)
    photos = db_execute('SELECT * FROM photos ORDER BY created_at DESC', fetch=True)
    messages = db_execute(
        '''SELECT m.*, u.nickname, u.avatar_data FROM messages m
           JOIN users u ON m.user_id = u.id ORDER BY m.created_at ASC''',
        fetch=True
    )
    user = get_current_user()

    today = date.today()

    together_date = datetime.strptime(COUPLE['together'], '%Y-%m-%d').date()
    days_together = (today - together_date).days

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

    b1_days, b1_age = birthday_countdown(COUPLE['boy']['birthday'])
    b2_days, b2_age = birthday_countdown(COUPLE['girl']['birthday'])

    return render_template('index.html',
        user=user, timelines=timelines, photos=photos, messages=messages,
        countdown_days=countdown_days, countdown_title=countdown_title,
        days_together=days_together,
        b1_days=b1_days, b1_age=b1_age, b1_zodiac=COUPLE['boy']['zodiac'], b1_zemoji=COUPLE['boy']['zodiac_emoji'],
        b2_days=b2_days, b2_age=b2_age, b2_zodiac=COUPLE['girl']['zodiac'], b2_zemoji=COUPLE['girl']['zodiac_emoji'],
        boy=COUPLE['boy'], girl=COUPLE['girl'], together=COUPLE['together'])

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db_execute(
            'SELECT * FROM users WHERE username=? AND password=?',
            (username, password), fetchone=True
        )
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return render_template('login.html', error='账号或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# ---------- image serving ----------
@app.route('/photo/<int:pid>')
def serve_photo(pid):
    photo = db_execute('SELECT image_data, mimetype FROM photos WHERE id=?', (pid,), fetchone=True)
    if photo and photo['image_data']:
        return Response(base64.b64decode(photo['image_data']), mimetype=photo.get('mimetype', 'image/jpeg'))
    return '', 404

@app.route('/avatar/<int:uid>')
def serve_avatar(uid):
    user = db_execute('SELECT avatar_data FROM users WHERE id=?', (uid,), fetchone=True)
    if user and user['avatar_data']:
        return Response(base64.b64decode(user['avatar_data']), mimetype='image/png')
    return '', 404

# ---------- settings ----------
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()
    if request.method == 'POST':
        nickname = request.form.get('nickname', '')
        password = request.form.get('password', '')
        if nickname:
            db_execute('UPDATE users SET nickname=? WHERE id=?', (nickname, user['id']), commit=True)
        if password:
            db_execute('UPDATE users SET password=? WHERE id=?', (password, user['id']), commit=True)
        file = request.files.get('avatar')
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                img_b64 = base64.b64encode(file.read()).decode('utf-8')
                mime = 'image/png' if ext == 'png' else 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/' + ext
                db_execute('UPDATE users SET avatar_data=? WHERE id=?', (img_b64, user['id']), commit=True)
        return redirect(url_for('settings'))
    return render_template('settings.html', user=user)

# ---------- admin ----------
@app.route('/admin')
@login_required
def admin():
    timelines = db_execute('SELECT * FROM timeline ORDER BY date DESC', fetch=True)
    photos = db_execute('SELECT * FROM photos ORDER BY created_at DESC', fetch=True)
    anniversaries = db_execute('SELECT * FROM anniversaries ORDER BY date', fetch=True)
    return render_template('admin.html', user=get_current_user(),
        timelines=timelines, photos=photos, anniversaries=anniversaries)

@app.route('/admin/timeline/add', methods=['POST'])
@login_required
def add_timeline():
    db_execute('INSERT INTO timeline (date, title, description) VALUES (?, ?, ?)',
        (request.form['date'], request.form['title'], request.form.get('description', '')), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/timeline/delete/<int:id>', methods=['POST'])
@login_required
def delete_timeline(id):
    db_execute('DELETE FROM timeline WHERE id=?', (id,), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/anniversary/add', methods=['POST'])
@login_required
def add_anniversary():
    db_execute('INSERT INTO anniversaries (title, date) VALUES (?, ?)',
        (request.form['title'], request.form['date']), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/anniversary/delete/<int:id>', methods=['POST'])
@login_required
def delete_anniversary(id):
    db_execute('DELETE FROM anniversaries WHERE id=?', (id,), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/photo/add', methods=['POST'])
@login_required
def add_photo():
    file = request.files.get('photo')
    if file and file.filename:
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
            img_b64 = base64.b64encode(file.read()).decode('utf-8')
            mime = 'image/png' if ext == 'png' else 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/' + ext
            db_execute('INSERT INTO photos (image_data, mimetype, caption) VALUES (?, ?, ?)',
                (img_b64, mime, request.form.get('caption', '')), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/photo/delete/<int:id>', methods=['POST'])
@login_required
def delete_photo(id):
    db_execute('DELETE FROM photos WHERE id=?', (id,), commit=True)
    return redirect(url_for('admin'))

@app.route('/message/send', methods=['POST'])
@login_required
def send_message():
    content = request.form.get('content', '').strip()
    if content:
        db_execute('INSERT INTO messages (user_id, content) VALUES (?, ?)',
            (session['user_id'], content), commit=True)
    return redirect(url_for('index'))

init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
