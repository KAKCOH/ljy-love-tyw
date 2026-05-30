import os
import json
import base64
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'lovetimeline-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- VAPID keys for Web Push ---
_VAPID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.vapid_keys')
try:
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
    if os.path.exists(_VAPID_FILE):
        v = Vapid.from_file(_VAPID_FILE)
    else:
        v = Vapid()
        v.generate_keys()
        v.save_key(_VAPID_FILE)
    VAPID_PRIVATE_KEY = v.private_pem()
    _raw_pub = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    VAPID_PUBLIC_KEY = base64.urlsafe_b64encode(_raw_pub).rstrip(b'=').decode()
except ImportError:
    VAPID_PRIVATE_KEY = ''
    VAPID_PUBLIC_KEY = ''

@app.context_processor
def inject_globals():
    return {'vapid_public_key': VAPID_PUBLIC_KEY, 'user': get_current_user()}

# Render PostgreSQL stores UTC; local SQLite stores local (China) time
_TZ_OFFSET = timedelta(hours=8) if os.environ.get('DATABASE_URL', '').startswith('postgres') else timedelta(0)

@app.template_filter('datestr')
def datestr(value):
    """Format a datetime or string to YYYY-MM-DD for templates."""
    if hasattr(value, 'strftime'):
        return (value + _TZ_OFFSET).strftime('%Y-%m-%d')
    return str(value)[:10]

@app.template_filter('datetimestr')
def datetimestr(value):
    """Format a datetime or string to YYYY-MM-DD HH:MM for templates."""
    if hasattr(value, 'strftime'):
        return (value + _TZ_OFFSET).strftime('%Y-%m-%d %H:%M')
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
        # Migrations: add columns if missing
        for col, dtype in [('recalled', 'INTEGER DEFAULT 0'), ('image_data', 'TEXT DEFAULT NULL'), ('image_mimetype', 'TEXT DEFAULT NULL')]:
            try:
                cur.execute(f"ALTER TABLE messages ADD COLUMN {col} {dtype}")
                db.commit()
            except Exception:
                db.rollback()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS special_messages (
                id SERIAL PRIMARY KEY,
                from_user_id INTEGER NOT NULL REFERENCES users(id),
                to_user_id INTEGER NOT NULL REFERENCES users(id),
                type TEXT NOT NULL,
                content TEXT DEFAULT '',
                meet_time TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP DEFAULT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                subscription_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, subscription_json)
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
        # Migrations: add columns if missing (for existing DBs)
        for col_def in ['recalled INTEGER DEFAULT 0', 'image_data TEXT DEFAULT NULL', 'image_mimetype TEXT DEFAULT NULL']:
            try:
                db.execute(f"ALTER TABLE messages ADD COLUMN {col_def}")
                db.commit()
            except Exception:
                pass
        db.execute('''
            CREATE TABLE IF NOT EXISTS special_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                content TEXT DEFAULT '',
                meet_time TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subscription_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, subscription_json),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
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
@app.route('/sw.js')
def service_worker():
    with open(os.path.join(app.static_folder, 'js', 'sw.js'), encoding='utf-8') as f:
        return Response(f.read(), mimetype='application/javascript')


@app.route('/')
def index():
    anniversaries = db_execute('SELECT * FROM anniversaries ORDER BY date', fetch=True)
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
        user=user,
        countdown_days=countdown_days, countdown_title=countdown_title,
        days_together=days_together,
        b1_days=b1_days, b1_age=b1_age, b1_zodiac=COUPLE['boy']['zodiac'], b1_zemoji=COUPLE['boy']['zodiac_emoji'],
        b2_days=b2_days, b2_age=b2_age, b2_zodiac=COUPLE['girl']['zodiac'], b2_zemoji=COUPLE['girl']['zodiac_emoji'],
        boy=COUPLE['boy'], girl=COUPLE['girl'], together=COUPLE['together'])

@app.route('/timeline')
def timeline_page():
    timelines = db_execute('SELECT * FROM timeline ORDER BY date DESC', fetch=True)
    return render_template('timeline.html', user=get_current_user(), timelines=timelines)

@app.route('/photos')
def photos_page():
    photos = db_execute('SELECT * FROM photos ORDER BY created_at DESC', fetch=True)
    return render_template('photos.html', user=get_current_user(), photos=photos)

@app.route('/messages')
@login_required
def messages_page():
    messages = db_execute(
        '''SELECT m.*, u.nickname, u.avatar_data FROM messages m
           JOIN users u ON m.user_id = u.id ORDER BY m.created_at ASC''',
        fetch=True
    )
    specials = db_execute('SELECT * FROM special_messages ORDER BY created_at ASC', fetch=True)
    return render_template('messages.html', user=get_current_user(), messages=messages, specials=specials)

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

def send_push_to_user(to_user_id, title, body, tag):
    """Send Web Push notification to all devices of a user."""
    subs = db_execute('SELECT subscription_json FROM push_subscriptions WHERE user_id=?',
        (to_user_id,), fetch=True)
    if not subs:
        print(f'[push] no subscriptions found for user {to_user_id}', flush=True)
        return
    try:
        from pywebpush import webpush, WebPushException
    except ImportError as ie:
        print(f'[push] pywebpush import failed: {ie}', flush=True)
        return
    if not VAPID_PRIVATE_KEY:
        print('[push] VAPID_PRIVATE_KEY is empty, cannot send', flush=True)
        return
    for s in subs:
        try:
            webpush(
                subscription_info=json.loads(s['subscription_json']),
                data=json.dumps({'title': title, 'body': body, 'tag': tag}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={'sub': 'mailto:lovetimeline@app.local'}
            )
            print(f'[push] sent to user {to_user_id}: {title}', flush=True)
        except Exception as e:
            print(f'[push] send failed: {type(e).__name__}: {e}', flush=True)


@app.route('/message/send', methods=['POST'])
@login_required
def send_message():
    content = request.form.get('content', '').strip()
    file = request.files.get('image')
    image_data = None
    image_mimetype = None
    if file and file.filename:
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
            image_data = base64.b64encode(file.read()).decode('utf-8')
            image_mimetype = 'image/png' if ext == 'png' else 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/' + ext
    if content or image_data:
        db_execute('INSERT INTO messages (user_id, content, image_data, image_mimetype) VALUES (?, ?, ?, ?)',
            (session['user_id'], content or '', image_data, image_mimetype), commit=True)
        to_id = get_other_user_id()
        if to_id:
            user = get_current_user()
            preview = content[:60] if content else '[图片]'
            send_push_to_user(to_id, user['nickname'] or '对方', preview, 'new_msg')
    return redirect(url_for('messages_page'))

@app.route('/message/image/<int:mid>')
@login_required
def serve_message_image(mid):
    msg = db_execute('SELECT image_data, image_mimetype FROM messages WHERE id=?', (mid,), fetchone=True)
    if msg and msg['image_data']:
        return Response(base64.b64decode(msg['image_data']), mimetype=msg.get('image_mimetype', 'image/jpeg'))
    return '', 404

@app.route('/message/recall/<int:id>', methods=['POST'])
@login_required
def recall_message(id):
    msg = db_execute('SELECT user_id FROM messages WHERE id=?', (id,), fetchone=True)
    if msg and msg['user_id'] == session['user_id']:
        db_execute('UPDATE messages SET recalled=1 WHERE id=?', (id,), commit=True)
    return redirect(url_for('messages_page'))

def get_other_user_id():
    users = db_execute('SELECT id FROM users WHERE id!=?', (session['user_id'],), fetch=True)
    return users[0]['id'] if users else None

@app.route('/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json()
    if data:
        endpoint = data.get('endpoint', '')[:80] if data else ''
        try:
            if USE_POSTGRES:
                db_execute(
                    'INSERT INTO push_subscriptions (user_id, subscription_json) VALUES (?, ?) '
                    'ON CONFLICT (user_id, subscription_json) DO NOTHING',
                    (session['user_id'], json.dumps(data)), commit=True)
            else:
                db_execute(
                    'INSERT OR IGNORE INTO push_subscriptions (user_id, subscription_json) VALUES (?, ?)',
                    (session['user_id'], json.dumps(data)), commit=True)
            print(f'[push] subscription saved for user {session["user_id"]}: {endpoint}...', flush=True)
        except Exception as e:
            print(f'[push] subscribe error: {type(e).__name__}: {e}', flush=True)
    return '', 200


@app.route('/special/send', methods=['POST'])
@login_required
def send_special():
    to_id = get_other_user_id()
    if to_id:
        sp_type = request.form['type']
        db_execute(
            'INSERT INTO special_messages (from_user_id, to_user_id, type, content) VALUES (?, ?, ?, ?)',
            (session['user_id'], to_id, sp_type, request.form.get('content', '')), commit=True)
        user = get_current_user()
        label = '想见你' if sp_type == 'meet' else '有任务'
        send_push_to_user(to_id, label, user['nickname'] + '发来了一条' + label, 'new_special')
    return redirect(url_for('messages_page'))

@app.route('/special/respond/<int:id>', methods=['POST'])
@login_required
def respond_special(id):
    sp = db_execute('SELECT * FROM special_messages WHERE id=? AND to_user_id=?',
        (id, session['user_id']), fetchone=True)
    if sp and sp['type'] == 'meet' and sp['status'] == 'pending':
        status = request.form['status']
        meet_time = request.form.get('meet_time', '')
        db_execute("UPDATE special_messages SET status=?, meet_time=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, meet_time, id), commit=True)
        user = get_current_user()
        send_push_to_user(sp['from_user_id'], '见面请求已回复',
            user['nickname'] + ('同意了' if status == 'accepted' else '拒绝了') + '见面请求', 'meet_resp')
    return redirect(url_for('messages_page'))

@app.route('/special/done/<int:id>', methods=['POST'])
@login_required
def done_special(id):
    sp = db_execute('SELECT * FROM special_messages WHERE id=? AND to_user_id=?',
        (id, session['user_id']), fetchone=True)
    if sp and sp['type'] == 'task' and sp['status'] == 'pending':
        db_execute("UPDATE special_messages SET status='done', completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (id,), commit=True)
        user = get_current_user()
        send_push_to_user(sp['from_user_id'], '任务已完成',
            user['nickname'] + '完成了任务', 'task_done')
    return redirect(url_for('messages_page'))

init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
