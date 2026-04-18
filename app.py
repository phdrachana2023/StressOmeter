from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json, os, hashlib, urllib.request, urllib.error
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'osi_stress_2024_secure')

# ── PostgreSQL Connection ─────────────────────────────────────────────────────
# Set DATABASE_URL environment variable on Render/Supabase like:
# postgresql://user:password@host:5432/dbname
DATABASE_URL = os.environ.get('DATABASE_URL', '')
# Fix for Render — psycopg2 needs postgresql:// not postgres://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

def get_db():
    """Get a new DB connection. psycopg2 is not thread-safe so we open per-request."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set.")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn
 



def init_db():
    """Create tables if they don't exist. Called once at startup."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username        TEXT PRIMARY KEY,
            password        TEXT NOT NULL,
            fullname        TEXT NOT NULL,
            email           TEXT NOT NULL,
            registered      TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demographics (
            username        TEXT PRIMARY KEY,
            timestamp       TEXT,
            full_name       TEXT,
            email           TEXT,
            contact         TEXT,
            institute       TEXT,
            teaching_level  TEXT,
            gender          TEXT,
            marital_status  TEXT,
            age_group       TEXT,
            education       TEXT,
            designation     TEXT,
            employment_type TEXT,
            experience      TEXT,
            tenure          TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stress_results (
            username         TEXT PRIMARY KEY,
            timestamp        TEXT,
            total_score      TEXT,
            overall_level    TEXT,
            assessment_type  TEXT,
            sub1  TEXT, sub1_score  TEXT, sub1_level  TEXT,
            sub2  TEXT, sub2_score  TEXT, sub2_level  TEXT,
            sub3  TEXT, sub3_score  TEXT, sub3_level  TEXT,
            sub4  TEXT, sub4_score  TEXT, sub4_level  TEXT,
            sub5  TEXT, sub5_score  TEXT, sub5_level  TEXT,
            sub6  TEXT, sub6_score  TEXT, sub6_level  TEXT,
            sub7  TEXT, sub7_score  TEXT, sub7_level  TEXT,
            sub8  TEXT, sub8_score  TEXT, sub8_level  TEXT,
            sub9  TEXT, sub9_score  TEXT, sub9_level  TEXT,
            sub10 TEXT, sub10_score TEXT, sub10_level TEXT,
            sub11 TEXT, sub11_score TEXT, sub11_level TEXT,
            sub12 TEXT, sub12_score TEXT, sub12_level TEXT,
            top1_subscale TEXT, top1_label TEXT, top1_score TEXT, top1_level TEXT,
            top2_subscale TEXT, top2_label TEXT, top2_score TEXT, top2_level TEXT,
            top3_subscale TEXT, top3_label TEXT, top3_score TEXT, top3_level TEXT,
            model_top1 TEXT, model_top2 TEXT, model_top3 TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            username      TEXT PRIMARY KEY,
            feedback_text TEXT NOT NULL,
            rating        INTEGER CHECK (rating BETWEEN 1 AND 5),
            timestamp     TEXT NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[OSI] Database tables ensured.")

# ── Gemini API Key ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyAHjvTD1xHxnCcFkiSppjJRiDkPNIjPGRY')

# ── Load MODEL TOP 3 once at startup ─────────────────────────────────────────
MODEL_TOP3_PATH = os.path.join(os.path.dirname(__file__), 'model_top3_subscales.pkl')
try:
    import joblib
    MODEL_TOP3 = joblib.load(MODEL_TOP3_PATH)
    print(f"[OSI] Loaded model top 3 from pkl: {MODEL_TOP3}")
except Exception:
    MODEL_TOP3 = ['Sub-Scale I', 'Sub-Scale III', 'Sub-Scale XI']
    print(f"[OSI] model_top3_subscales.pkl not found — using default: {MODEL_TOP3}")

# ── DB helpers ────────────────────────────────────────────────────────────────
def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def get_user(username):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None

def create_user(username, password, fullname, email):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password, fullname, email, registered) VALUES (%s,%s,%s,%s,%s)",
        (username, hash_pw(password), fullname, email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    cur.close(); conn.close()

def get_prev(username):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM stress_results WHERE username = %s", (username,))
    s = cur.fetchone()
    cur.execute("SELECT * FROM demographics WHERE username = %s", (username,))
    d = cur.fetchone()
    cur.close(); conn.close()
    return (dict(s) if s else None), (dict(d) if d else None)

def get_feedback(username):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM feedback WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None

def upsert_demographics(username, ts, demo):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO demographics
          (username, timestamp, full_name, email, contact, institute, teaching_level,
           gender, marital_status, age_group, education, designation, employment_type,
           experience, tenure)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (username) DO UPDATE SET
          timestamp       = EXCLUDED.timestamp,
          full_name       = EXCLUDED.full_name,
          email           = EXCLUDED.email,
          contact         = EXCLUDED.contact,
          institute       = EXCLUDED.institute,
          teaching_level  = EXCLUDED.teaching_level,
          gender          = EXCLUDED.gender,
          marital_status  = EXCLUDED.marital_status,
          age_group       = EXCLUDED.age_group,
          education       = EXCLUDED.education,
          designation     = EXCLUDED.designation,
          employment_type = EXCLUDED.employment_type,
          experience      = EXCLUDED.experience,
          tenure          = EXCLUDED.tenure
    """, (
        username, ts,
        demo.get('full_name',''), demo.get('email',''), demo.get('contact',''),
        demo.get('institute',''), demo.get('teaching_level',''), demo.get('gender',''),
        demo.get('marital_status',''), demo.get('age_group',''), demo.get('education',''),
        demo.get('designation',''), demo.get('employment_type',''),
        demo.get('experience',''), demo.get('tenure','')
    ))
    conn.commit(); cur.close(); conn.close()

def upsert_stress(username, ts, stress, model_top3):
    subs = stress.get('subscales', [])
    top3 = stress.get('top3', [])
    vals = [username, ts,
            stress.get('total_score',''), stress.get('overall_level',''),
            stress.get('assessment_type','advanced')]
    for i in range(12):
        s = subs[i] if i < len(subs) else {}
        vals += [s.get('name',''), s.get('score',''), s.get('level','')]
    for i in range(3):
        t = top3[i] if i < len(top3) else {}
        vals += [t.get('name',''), t.get('label',''), t.get('score',''), t.get('level','')]
    for i in range(3):
        vals.append(model_top3[i] if i < len(model_top3) else '')

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO stress_results (
          username, timestamp, total_score, overall_level, assessment_type,
          sub1,sub1_score,sub1_level, sub2,sub2_score,sub2_level,
          sub3,sub3_score,sub3_level, sub4,sub4_score,sub4_level,
          sub5,sub5_score,sub5_level, sub6,sub6_score,sub6_level,
          sub7,sub7_score,sub7_level, sub8,sub8_score,sub8_level,
          sub9,sub9_score,sub9_level, sub10,sub10_score,sub10_level,
          sub11,sub11_score,sub11_level, sub12,sub12_score,sub12_level,
          top1_subscale,top1_label,top1_score,top1_level,
          top2_subscale,top2_label,top2_score,top2_level,
          top3_subscale,top3_label,top3_score,top3_level,
          model_top1,model_top2,model_top3
        ) VALUES (
          %s,%s,%s,%s,%s,
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        ON CONFLICT (username) DO UPDATE SET
          timestamp=EXCLUDED.timestamp, total_score=EXCLUDED.total_score,
          overall_level=EXCLUDED.overall_level, assessment_type=EXCLUDED.assessment_type,
          sub1=EXCLUDED.sub1, sub1_score=EXCLUDED.sub1_score, sub1_level=EXCLUDED.sub1_level,
          sub2=EXCLUDED.sub2, sub2_score=EXCLUDED.sub2_score, sub2_level=EXCLUDED.sub2_level,
          sub3=EXCLUDED.sub3, sub3_score=EXCLUDED.sub3_score, sub3_level=EXCLUDED.sub3_level,
          sub4=EXCLUDED.sub4, sub4_score=EXCLUDED.sub4_score, sub4_level=EXCLUDED.sub4_level,
          sub5=EXCLUDED.sub5, sub5_score=EXCLUDED.sub5_score, sub5_level=EXCLUDED.sub5_level,
          sub6=EXCLUDED.sub6, sub6_score=EXCLUDED.sub6_score, sub6_level=EXCLUDED.sub6_level,
          sub7=EXCLUDED.sub7, sub7_score=EXCLUDED.sub7_score, sub7_level=EXCLUDED.sub7_level,
          sub8=EXCLUDED.sub8, sub8_score=EXCLUDED.sub8_score, sub8_level=EXCLUDED.sub8_level,
          sub9=EXCLUDED.sub9, sub9_score=EXCLUDED.sub9_score, sub9_level=EXCLUDED.sub9_level,
          sub10=EXCLUDED.sub10, sub10_score=EXCLUDED.sub10_score, sub10_level=EXCLUDED.sub10_level,
          sub11=EXCLUDED.sub11, sub11_score=EXCLUDED.sub11_score, sub11_level=EXCLUDED.sub11_level,
          sub12=EXCLUDED.sub12, sub12_score=EXCLUDED.sub12_score, sub12_level=EXCLUDED.sub12_level,
          top1_subscale=EXCLUDED.top1_subscale, top1_label=EXCLUDED.top1_label,
          top1_score=EXCLUDED.top1_score, top1_level=EXCLUDED.top1_level,
          top2_subscale=EXCLUDED.top2_subscale, top2_label=EXCLUDED.top2_label,
          top2_score=EXCLUDED.top2_score, top2_level=EXCLUDED.top2_level,
          top3_subscale=EXCLUDED.top3_subscale, top3_label=EXCLUDED.top3_label,
          top3_score=EXCLUDED.top3_score, top3_level=EXCLUDED.top3_level,
          model_top1=EXCLUDED.model_top1, model_top2=EXCLUDED.model_top2,
          model_top3=EXCLUDED.model_top3
    """, vals)
    conn.commit(); cur.close(); conn.close()

# ── Gemini helpers (unchanged) ────────────────────────────────────────────────
def build_system_prompt(stress_data, demo_data):
    name        = demo_data.get('full_name', 'the user') if demo_data else 'the user'
    designation = demo_data.get('designation', 'an academician') if demo_data else 'an academician'
    experience  = demo_data.get('experience', 'unknown') if demo_data else 'unknown'
    total_score = stress_data.get('total_score', 'unknown') if stress_data else 'unknown'
    overall_lvl = stress_data.get('overall_level', 'unknown') if stress_data else 'unknown'
    assess_type = stress_data.get('assessment_type', 'advanced') if stress_data else 'advanced'
    subscale_info = ''
    if stress_data:
        sub_lines = []
        for i in range(1, 13):
            sn = stress_data.get(f'sub{i}','')
            sc = stress_data.get(f'sub{i}_score','')
            sl = stress_data.get(f'sub{i}_level','')
            if sn and sc and sl:
                sub_lines.append(f"  - {sn}: Score={sc}, Level={sl}")
        subscale_info = '\n'.join(sub_lines)
    top3_info = ''
    if stress_data:
        top_lines = []
        for i in range(1, 4):
            t_name  = stress_data.get(f'top{i}_subscale','')
            t_label = stress_data.get(f'top{i}_label','')
            t_score = stress_data.get(f'top{i}_score','')
            t_level = stress_data.get(f'top{i}_level','')
            if t_name:
                top_lines.append(f"  #{i}: {t_name} ({t_label}) — Score={t_score}, Level={t_level}")
        top3_info = '\n'.join(top_lines)
    return f"""You are an expert occupational stress counsellor and psychologist specialising in the Occupational Stress Index (OSI) by Srivastava & Singh (1981). You are embedded in an OSI stress assessment web application used by academicians in India.

YOUR ROLE:
- Provide empathetic, evidence-based guidance on occupational stress
- Answer questions about the user's OSI assessment results
- Give practical, actionable coping strategies
- Explain OSI sub-scales and what scores mean
- Recommend professional help when stress is High

STRICT RULES:
- ONLY answer questions related to: occupational stress, mental health at work, OSI scores and sub-scales, burnout, work-life balance, coping strategies, mindfulness, sleep, exercise, anxiety, and general well-being
- If asked ANYTHING unrelated, politely say: "I'm only able to help with occupational stress and well-being topics."
- Never provide medical diagnoses
- Always recommend professional help for High stress
- Keep responses concise (3-5 sentences max) unless detail is needed
- Be warm, empathetic and encouraging

USER'S OSI ASSESSMENT DATA:
- Name: {name}
- Designation: {designation}
- Experience: {experience}
- Assessment Type: {assess_type}
- Total Stress Score: {total_score}
- Overall Stress Level: {overall_lvl}

SUBSCALE SCORES:
{subscale_info if subscale_info else '  (No assessment data available yet)'}

PERSONAL TOP 3 HIGH-STRESS AREAS:
{top3_info if top3_info else '  (No assessment data available yet)'}

OSI SCORE INTERPRETATION:
- Full OSI: Low=46-122, Moderate=123-155, High=156-230
- Sub-scale levels: Low, Moderate, High based on normative ranges

HELPLINES (India):
- iCall-TISS: 9152987821
- Vandrevala Foundation: 1860-2662-345
- NIMHANS: 080-46110007
- Fortis Helpline: 8376804102"""

def call_gemini(user_message, conversation_history, system_prompt):
    if not GEMINI_API_KEY or GEMINI_API_KEY == 'PASTE_YOUR_GEMINI_API_KEY_HERE':
        return None, "API key not configured"
    contents = []
    for turn in conversation_history:
        contents.append({"role": turn["role"], "parts": [{"text": turn["text"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400, "topP": 0.9},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
        ]
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        data = json.dumps(payload).encode('utf-8')
        req  = urllib.request.Request(url, data=data,
                                      headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return result['candidates'][0]['content']['parts'][0]['text'].strip(), None
    except urllib.error.HTTPError as e:
        return None, f"API error {e.code}: {e.read().decode('utf-8')}"
    except Exception as e:
        return None, str(e)

KEYWORD_RESPONSES = [
    (['stress','what is stress','define stress'],
     "Stress is your body's natural response to pressure or demands. Short-term stress can boost performance, but chronic occupational stress leads to burnout, health problems, and reduced productivity."),
    (['osi','occupational stress index','srivastava'],
     "The Occupational Stress Index (OSI) by Srivastava & Singh (1981) measures work-related stress across 12 sub-scales. Total scores range from 46–230: Low (46–122), Moderate (123–155), High (156–230)."),
    (['my score','total score','stress score'],
     "Your stress score is shown on the StressOmeter. Low: 46–122 | Moderate: 123–155 | High: 156–230."),
    (['burnout','burnt out','exhausted'],
     "Burnout is chronic stress leading to exhaustion and cynicism. Please seek professional help immediately if you feel burnt out."),
    (['sleep','insomnia','cant sleep'],
     "Sleep is critical. Aim for 7–8 hours, keep a consistent bedtime, avoid screens 1 hour before sleep."),
    (['exercise','physical activity','workout','walk'],
     "Exercise is one of the most effective stress relievers. Even 20–30 minutes of walking or yoga daily significantly reduces cortisol."),
    (['mindful','mindfulness','meditat'],
     "Try 10 minutes of guided meditation daily. Apps like Headspace or Calm can help."),
    (['breath','breathing','breathe'],
     "Try box breathing: inhale 4 counts → hold 4 → exhale 4 → hold 4. Repeat 5 times."),
    (['helpline','help line','contact','number','support'],
     "Professional support helplines in India: iCall-TISS: 9152987821 | Vandrevala Foundation: 1860-2662-345 | NIMHANS: 080-46110007 | Fortis Helpline: 8376804102."),
    (['chatbot','who are you','what can you do'],
     "I'm your OSI Stress Assistant! I can answer questions about your stress scores, subscales, burnout, coping strategies, mindfulness, sleep, exercise, and helplines."),
]

def keyword_fallback(msg):
    msg_lower = msg.lower()
    for keywords, reply in KEYWORD_RESPONSES:
        if any(kw in msg_lower for kw in keywords):
            return reply
    return "I can only answer questions related to occupational stress and the OSI assessment. Try asking about your score, burnout, mindfulness, sleep, exercise, or helplines."

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'username' in session: return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    err = ''
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        user = get_user(u)
        if user and user['password'] == hash_pw(p):
            session['username'] = u
            session['fullname'] = user['fullname']
            return redirect(url_for('home'))
        err = 'Invalid username or password.'
    return render_template('login.html', error=err)

@app.route('/register', methods=['GET', 'POST'])
def register():
    err = ''
    if request.method == 'POST':
        u  = request.form.get('username', '').strip()
        p  = request.form.get('password', '').strip()
        p2 = request.form.get('confirm',  '').strip()
        fn = request.form.get('fullname', '').strip()
        em = request.form.get('email',    '').strip()
        if not u or not p or not fn or not em:
            err = 'All fields are required.'
        elif p != p2:
            err = 'Passwords do not match.'
        elif get_user(u):
            err = 'Username already exists. Please choose another.'
        else:
            create_user(u, p, fn, em)
            session['username'] = u
            session['fullname'] = fn
            return redirect(url_for('home'))
    return render_template('register.html', error=err)

@app.route('/home')
def home():
    if 'username' not in session: return redirect(url_for('login'))
    s, _ = get_prev(session['username'])
    return render_template('home.html',
        fullname=session['fullname'],
        username=session['username'],
        has_prev=(s is not None))

@app.route('/basic')
def basic():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('basic.html', fullname=session['fullname'])

@app.route('/advanced')
def advanced():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('advanced.html',
        fullname=session['fullname'],
        username=session['username'],
        model_top3=json.dumps(MODEL_TOP3))

@app.route('/result')
def result():
    if 'username' not in session: return redirect(url_for('login'))
    s, d = get_prev(session['username'])
    if not s: return redirect(url_for('home'))
    fb = get_feedback(session['username'])
    return render_template('result.html',
        fullname=session['fullname'],
        stress=s, demo=d,
        model_top3=MODEL_TOP3,
        assessment_type=s.get('assessment_type','advanced'),
        feedback=fb,
        is_previous=False)

@app.route('/previous')
def previous():
    if 'username' not in session: return redirect(url_for('login'))
    s, d = get_prev(session['username'])
    if not s: return redirect(url_for('home'))
    fb = get_feedback(session['username'])
    return render_template('result.html',
        fullname=session['fullname'],
        stress=s, demo=d,
        model_top3=MODEL_TOP3,
        assessment_type=s.get('assessment_type','advanced'),
        feedback=fb,
        is_previous=True)

@app.route('/save', methods=['POST'])
def save():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': 'Not logged in'}), 401
    data  = request.get_json()
    uname = session['username']
    ts    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        upsert_demographics(uname, ts, data.get('demo', {}))
        upsert_stress(uname, ts, data.get('stress', {}), MODEL_TOP3)
        # Clear old feedback so user can submit fresh feedback after retake
        conn2 = get_db(); cur2 = conn2.cursor()
        cur2.execute("DELETE FROM feedback WHERE username = %s", (uname,))
        conn2.commit(); cur2.close(); conn2.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[Save Error] {e}")
        return jsonify({'ok': False, 'msg': str(e)}), 500

@app.route('/save_feedback', methods=['POST'])
def save_feedback():
    if 'username' not in session:
        return jsonify({'ok': False, 'msg': 'Not logged in'}), 401
    data    = request.get_json()
    uname   = session['username']
    fb_text = data.get('feedback_text', '').strip()
    rating  = data.get('rating', None)
    if not fb_text:
        return jsonify({'ok': False, 'msg': 'Feedback cannot be empty.'}), 400
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO feedback (username, feedback_text, rating, timestamp)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET
              feedback_text = EXCLUDED.feedback_text,
              rating        = EXCLUDED.rating,
              timestamp     = EXCLUDED.timestamp
        """, (uname, fb_text, rating, ts))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[Feedback Error] {e}")
        return jsonify({'ok': False, 'msg': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({'reply': 'Please login first.'}), 401
    data          = request.get_json()
    user_message  = data.get('message', '').strip()
    conv_history  = data.get('history', [])
    if not user_message:
        return jsonify({'reply': 'Please type a message.'})
    stress_data, demo_data = get_prev(session['username'])
    if GEMINI_API_KEY and GEMINI_API_KEY != 'PASTE_YOUR_GEMINI_API_KEY_HERE':
        system_prompt = build_system_prompt(stress_data, demo_data)
        reply, error  = call_gemini(user_message, conv_history, system_prompt)
        if reply:
            return jsonify({'reply': reply, 'source': 'ai'})
        print(f"[Gemini Error] {error} — falling back to keyword bot")
    return jsonify({'reply': keyword_fallback(user_message), 'source': 'keyword'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Startup ───────────────────────────────────────────────────────────────────
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"[OSI] DB init skipped (no DATABASE_URL?): {e}")

if __name__ == '__main__':
    app.run(debug=True, port=5050)
