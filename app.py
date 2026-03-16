"""
app.py - Smart City Complaint Analysis System
Main Flask backend with all routes, DB operations, NLP integration
+ Email Notifications (complaint received + resolved)
+ In-app Notification Center
+ Admin Notification Settings
"""

import os
import sqlite3
import json
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g)
from werkzeug.utils import secure_filename
from nlp_utils import (clean_text, predict_category, analyze_sentiment,
                       is_emergency, calculate_priority, check_duplicate,
                       extract_keywords, load_classifier, load_tfidf_dup)
from notifications import (notify_complaint_received, notify_complaint_resolved,
                            notify_admin_new_complaint, notify_admin_resolved)

app = Flask(__name__)
app.secret_key = 'smartcity_secret_key_2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
DATABASE = 'complaints.db'

CLASSIFIER = load_classifier()
TFIDF_DUP  = load_tfidf_dup()

# ─── Database ─────────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                landmark TEXT,
                pincode TEXT,
                location_text TEXT,
                latitude REAL,
                longitude REAL,
                complaint_text TEXT NOT NULL,
                image_path TEXT,
                category TEXT,
                sentiment TEXT,
                keywords TEXT,
                priority_score INTEGER DEFAULT 0,
                priority_label TEXT DEFAULT "LOW",
                is_emergency INTEGER DEFAULT 0,
                is_duplicate INTEGER DEFAULT 0,
                duplicate_of INTEGER,
                similarity_score REAL,
                status TEXT DEFAULT "Pending",
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                email_enabled INTEGER DEFAULT 0,
                sender_email TEXT DEFAULT "",
                sender_password TEXT DEFAULT "",
                notify_on_receive INTEGER DEFAULT 1,
                notify_on_resolve INTEGER DEFAULT 1,
                admin_email TEXT DEFAULT "",
                notify_admin_on_receive INTEGER DEFAULT 1,
                notify_admin_on_resolve INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id INTEGER,
                type TEXT,
                recipient_email TEXT,
                success INTEGER DEFAULT 0,
                message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(complaint_id) REFERENCES complaints(id)
            );
        ''')
        # ── Auto-migrate: add new columns if they don't exist ──────────────
        existing_cols = [row[1] for row in db.execute("PRAGMA table_info(complaints)").fetchall()]
        migrations = [
            ("address",  "ALTER TABLE complaints ADD COLUMN address TEXT"),
            ("landmark", "ALTER TABLE complaints ADD COLUMN landmark TEXT"),
            ("pincode",  "ALTER TABLE complaints ADD COLUMN pincode TEXT"),
        ]
        # Migrate notification_settings table too
        ns_cols = [r[1] for r in db.execute("PRAGMA table_info(notification_settings)").fetchall()]
        ns_migrations = [
            ("admin_email",             "ALTER TABLE notification_settings ADD COLUMN admin_email TEXT DEFAULT ''"),
            ("notify_admin_on_receive", "ALTER TABLE notification_settings ADD COLUMN notify_admin_on_receive INTEGER DEFAULT 1"),
            ("notify_admin_on_resolve", "ALTER TABLE notification_settings ADD COLUMN notify_admin_on_resolve INTEGER DEFAULT 1"),
        ]
        for col, sql in ns_migrations:
            if col not in ns_cols:
                db.execute(sql)
                print(f"  ✅ Migrated: added column '{col}' to notification_settings")
        for col, sql in migrations:
            if col not in existing_cols:
                db.execute(sql)
                print(f"  ✅ Migrated: added column '{col}' to complaints table")

        if not db.execute("SELECT id FROM admin_users WHERE username='admin'").fetchone():
            db.execute("INSERT INTO admin_users (username,password) VALUES (?,?)", ('admin','admin123'))
        if not db.execute("SELECT id FROM notification_settings WHERE id=1").fetchone():
            db.execute("INSERT INTO notification_settings (id) VALUES (1)")
        db.commit()

def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def dict_from_row(row):
    return dict(zip(row.keys(), row))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please login to access admin panel.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─── Validation helpers ───────────────────────────────────────────────────────

def validate_phone(phone):
    """Must be exactly 10 digits, numbers only."""
    return phone.isdigit() and len(phone) == 10

def validate_pincode(pincode):
    """Must be exactly 6 digits, numbers only."""
    return pincode.isdigit() and len(pincode) == 6

# ─── Public ───────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    db = get_db()
    stats = {
        'total':     db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
        'pending':   db.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0],
        'resolved':  db.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0],
        'emergency': db.execute("SELECT COUNT(*) FROM complaints WHERE is_emergency=1").fetchone()[0],
    }
    return render_template('home.html', stats=stats)

@app.route('/submit', methods=['GET','POST'])
def submit_complaint():
    if request.method == 'POST':
        name           = request.form.get('name','').strip()
        phone          = request.form.get('phone','').strip()
        email          = request.form.get('email','').strip()
        address        = request.form.get('address','').strip()
        landmark       = request.form.get('landmark','').strip()
        pincode        = request.form.get('pincode','').strip()
        latitude       = request.form.get('latitude') or None
        longitude      = request.form.get('longitude') or None
        complaint_text = request.form.get('complaint_text','').strip()

        # ── Server-side validation ──────────────────────────────────────────
        errors = []

        if not name:
            errors.append('Full name is required.')

        if not phone:
            errors.append('Mobile number is required.')
        elif not validate_phone(phone):
            errors.append('Mobile number must be exactly 10 digits (numbers only).')

        if not address:
            errors.append('Address is required.')

        if not landmark:
            errors.append('Landmark is required.')

        if not pincode:
            errors.append('Pincode is required.')
        elif not validate_pincode(pincode):
            errors.append('Pincode must be exactly 6 digits (numbers only).')

        if not complaint_text or len(complaint_text) < 20:
            errors.append('Please describe the issue (minimum 20 characters).')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('submit_complaint'))

        # ── Combine address fields into location_text ───────────────────────
        location_parts = [address, landmark, pincode]
        location_text  = ', '.join([p for p in location_parts if p])

        # ── Image upload ────────────────────────────────────────────────────
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"

        # ── NLP processing ──────────────────────────────────────────────────
        category  = predict_category(complaint_text, CLASSIFIER)
        sentiment = analyze_sentiment(complaint_text)
        keywords  = ', '.join(extract_keywords(complaint_text))
        emerg     = is_emergency(complaint_text)

        db = get_db()
        existing_rows = db.execute("SELECT id, complaint_text FROM complaints WHERE status!='Resolved'").fetchall()
        existing = [{'id': r['id'], 'complaint_text': r['complaint_text']} for r in existing_rows]
        is_dup, dup_of, sim_score = check_duplicate(complaint_text, existing, TFIDF_DUP)

        score, label = calculate_priority(complaint_text, is_dup=is_dup, is_emerg=emerg)
        if emerg:
            label = 'HIGH'

        cursor = db.execute('''
            INSERT INTO complaints
            (name, phone, email, address, landmark, pincode, location_text,
             latitude, longitude, complaint_text, image_path, category,
             sentiment, keywords, priority_score, priority_label,
             is_emergency, is_duplicate, duplicate_of, similarity_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (name, phone, email, address, landmark, pincode, location_text,
              latitude, longitude, complaint_text, image_path, category,
              sentiment, keywords, score, label,
              1 if emerg else 0, 1 if is_dup else 0, dup_of, sim_score))
        db.commit()
        complaint_id = cursor.lastrowid

        # ── Send confirmation email ─────────────────────────────────────────
        if email:
            settings = db.execute("SELECT * FROM notification_settings WHERE id=1").fetchone()
            if settings and settings['notify_on_receive']:
                notify_complaint_received(db, {
                    'id': complaint_id, 'name': name, 'email': email,
                    'category': category, 'priority_label': label,
                    'location_text': location_text, 'complaint_text': complaint_text,
                    'is_emergency': emerg,
                    'submitted_at': datetime.now().strftime('%Y-%m-%d %H:%M')
                })

        # Send admin notification
        notify_admin_new_complaint(db, {
            'id': complaint_id, 'name': name, 'phone': phone, 'email': email,
            'address': address, 'landmark': landmark, 'pincode': pincode,
            'location_text': location_text, 'complaint_text': complaint_text,
            'category': category, 'priority_label': label,
            'is_emergency': emerg, 'is_duplicate': is_dup, 'duplicate_of': dup_of,
            'submitted_at': datetime.now().strftime('%Y-%m-%d %H:%M')
        })

        flash(f'✅ Complaint submitted! Your ID is <strong>#{complaint_id}</strong>. Save it for tracking.', 'success')
        if emerg:
            flash('🚨 EMERGENCY detected! Authorities alerted immediately.', 'danger')
        if email:
            flash(f'📧 Confirmation email sent to {email}', 'info')
        return redirect(url_for('home'))

    return render_template('complaint_form.html')

# ─── Admin ────────────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        db   = get_db()
        user = db.execute("SELECT * FROM admin_users WHERE username=? AND password=?",
                          (request.form.get('username'), request.form.get('password'))).fetchone()
        if user:
            session['admin_logged_in'] = True
            session['admin_username']  = user['username']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin/dashboard')
@admin_required
def dashboard():
    db = get_db()
    cf = request.args.get('category','')
    pf = request.args.get('priority','')
    sf = request.args.get('status','')
    ef = request.args.get('emergency','')

    q, p = "SELECT * FROM complaints WHERE 1=1", []
    if cf: q += " AND category=?";       p.append(cf)
    if pf: q += " AND priority_label=?"; p.append(pf)
    if sf: q += " AND status=?";         p.append(sf)
    if ef: q += " AND is_emergency=1"
    q += " ORDER BY is_emergency DESC, priority_score DESC, submitted_at DESC"

    complaints = [dict_from_row(r) for r in db.execute(q, p).fetchall()]
    active_emergencies = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE is_emergency=1 AND status='Pending'"
    ).fetchone()[0]
    unread_notifs = db.execute("SELECT COUNT(*) FROM notifications WHERE success=1").fetchone()[0]

    categories = ['Roads / Potholes','Garbage / Sanitation','Water Supply',
                  'Streetlight / Electricity','Traffic Signal','Noise Complaint','Other']
    return render_template('dashboard.html', complaints=complaints, categories=categories,
                           active_emergencies=active_emergencies, unread_notifs=unread_notifs,
                           filters={'category':cf,'priority':pf,'status':sf,'emergency':ef})

@app.route('/admin/resolve/<int:cid>', methods=['POST'])
@admin_required
def resolve_complaint(cid):
    db = get_db()
    db.execute("UPDATE complaints SET status='Resolved', resolved_at=CURRENT_TIMESTAMP WHERE id=?", (cid,))
    db.commit()
    c = db.execute("SELECT * FROM complaints WHERE id=?", (cid,)).fetchone()
    if c:
        cd = dict_from_row(c)
        if cd.get('email'):
            settings = db.execute("SELECT * FROM notification_settings WHERE id=1").fetchone()
            if settings and settings['notify_on_resolve']:
                cd['resolved_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                notify_complaint_resolved(db, cd)
    # Send admin resolution confirmation
    if c:
        notify_admin_resolved(db, dict_from_row(c) | {'resolved_at': datetime.now().strftime('%Y-%m-%d %H:%M')})
    flash(f'✅ Complaint #{cid} resolved. Resolution email sent to citizen.', 'success')
    return redirect(url_for('dashboard'))

# ─── Notification Center ──────────────────────────────────────────────────────

@app.route('/admin/notifications')
@admin_required
def notification_center():
    db = get_db()
    notifications = [dict_from_row(r) for r in db.execute('''
        SELECT n.*, c.name, c.category, c.priority_label
        FROM notifications n LEFT JOIN complaints c ON n.complaint_id=c.id
        ORDER BY n.sent_at DESC LIMIT 100
    ''').fetchall()]

    total_sent    = db.execute("SELECT COUNT(*) FROM notifications WHERE success=1").fetchone()[0]
    total_failed  = db.execute("SELECT COUNT(*) FROM notifications WHERE success=0").fetchone()[0]
    received_sent = db.execute("SELECT COUNT(*) FROM notifications WHERE type='received' AND success=1").fetchone()[0]
    resolved_sent = db.execute("SELECT COUNT(*) FROM notifications WHERE type='resolved' AND success=1").fetchone()[0]
    settings = dict_from_row(db.execute("SELECT * FROM notification_settings WHERE id=1").fetchone())

    return render_template('notifications.html', notifications=notifications,
                           total_sent=total_sent, total_failed=total_failed,
                           received_sent=received_sent, resolved_sent=resolved_sent,
                           settings=settings)

@app.route('/admin/notification-settings', methods=['GET','POST'])
@admin_required
def notification_settings():
    db = get_db()
    if request.method == 'POST':
        db.execute('''
            UPDATE notification_settings SET
              email_enabled=?, sender_email=?, sender_password=?,
              notify_on_receive=?, notify_on_resolve=?,
              admin_email=?, notify_admin_on_receive=?, notify_admin_on_resolve=?,
              updated_at=CURRENT_TIMESTAMP
            WHERE id=1
        ''', (1 if request.form.get('email_enabled') else 0,
              request.form.get('sender_email','').strip(),
              request.form.get('sender_password','').strip(),
              1 if request.form.get('notify_on_receive') else 0,
              1 if request.form.get('notify_on_resolve') else 0,
              request.form.get('admin_email','').strip(),
              1 if request.form.get('notify_admin_on_receive') else 0,
              1 if request.form.get('notify_admin_on_resolve') else 0))
        db.commit()
        flash('✅ Settings saved!', 'success')

        if request.form.get('test_email'):
            test_addr = request.form.get('test_email_addr','').strip()
            if test_addr:
                from notifications import send_email, get_email_config
                ok, msg = send_email(test_addr, "✅ Test — Smart City Hub",
                    "<h2>✅ Email is working!</h2><p>Your notification system is configured correctly.</p>",
                    get_email_config(db))
                flash(f'Test: {"✅ Sent to " + test_addr if ok else "❌ " + msg}',
                      'success' if ok else 'danger')
        return redirect(url_for('notification_settings'))

    settings = dict_from_row(db.execute("SELECT * FROM notification_settings WHERE id=1").fetchone())
    return render_template('notification_settings.html', settings=settings)

# ─── Analytics ────────────────────────────────────────────────────────────────

@app.route('/admin/analytics')
@admin_required
def analytics():
    db = get_db()
    cat_data  = db.execute("SELECT category, COUNT(*) as count FROM complaints GROUP BY category").fetchall()
    pri_data  = db.execute("SELECT priority_label, COUNT(*) as count FROM complaints GROUP BY priority_label").fetchall()
    stat_data = db.execute("SELECT status, COUNT(*) as count FROM complaints GROUP BY status").fetchall()
    hotspots  = db.execute('''
        SELECT ROUND(latitude,2) as lat, ROUND(longitude,2) as lng,
               COUNT(*) as count, location_text
        FROM complaints WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude,2),ROUND(longitude,2) ORDER BY count DESC LIMIT 10
    ''').fetchall()
    top_cat = db.execute("SELECT category,COUNT(*) as c FROM complaints GROUP BY category ORDER BY c DESC LIMIT 1").fetchone()
    avg_res = db.execute("SELECT AVG((julianday(resolved_at)-julianday(submitted_at))*24) FROM complaints WHERE resolved_at IS NOT NULL").fetchone()[0]
    total       = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    high        = db.execute("SELECT COUNT(*) FROM complaints WHERE priority_label='HIGH'").fetchone()[0]
    duplicates  = db.execute("SELECT COUNT(*) FROM complaints WHERE is_duplicate=1").fetchone()[0]
    emergencies = db.execute("SELECT COUNT(*) FROM complaints WHERE is_emergency=1").fetchone()[0]
    return render_template('analytics.html',
                           cat_data=json.dumps([dict(r) for r in cat_data]),
                           pri_data=json.dumps([dict(r) for r in pri_data]),
                           stat_data=json.dumps([dict(r) for r in stat_data]),
                           hotspots=[dict(r) for r in hotspots],
                           top_cat=top_cat['category'] if top_cat else 'N/A',
                           avg_res=round(avg_res,1) if avg_res else 0,
                           total=total, high=high, duplicates=duplicates, emergencies=emergencies)

@app.route('/api/emergency-status')
def api_emergency_status():
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM complaints WHERE is_emergency=1 AND status='Pending'").fetchone()[0]
    return jsonify({'active_emergencies': count})

if __name__ == '__main__':
    os.makedirs('static/uploads', exist_ok=True)
    init_db()
    print("\n✅ Smart City System Starting...")
    print("📍 Home:          http://127.0.0.1:5000")
    print("🔑 Admin:         http://127.0.0.1:5000/admin/login  (admin/admin123)")
    print("🔔 Notifications: http://127.0.0.1:5000/admin/notifications")
    print("⚙️  Email Setup:   http://127.0.0.1:5000/admin/notification-settings\n")
    app.run(debug=True, host='0.0.0.0', port=5000)