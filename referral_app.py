import streamlit as st
import sqlite3
import hashlib
import os
import random
import string
from datetime import datetime, timedelta
import pandas as pd
import urllib.parse
import time

# ========== PAGE CONFIG ==========
st.set_page_config(page_title="Ali Mobile Repair – Referral Race", page_icon="📱", layout="wide")

# ========== GAMING THEME (NEON DARK) ==========
st.markdown("""
<style>
    .stApp { background: #0a0a0a; }
    h1, h2, h3, h4, h5, h6, p, label, div, span {
        color: #e0e0e0 !important;
    }
    .neon-text {
        color: #fff;
        text-shadow: 0 0 10px #ff9f43, 0 0 20px #ff6b6b;
    }
    .card, .metric-card, .referral-history-item, .discount-history-item, .notification {
        background: #121212;
        border: 1px solid #333;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        transition: 0.3s;
    }
    .card:hover { border-color: #ff9f43; }
    .gradient-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #ff9f43;
    }
    .stButton button {
        background: linear-gradient(45deg, #ff9f43, #ff6b6b);
        border: none;
        color: white;
        border-radius: 30px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 20px #ff9f43;
    }
    .level-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 20px;
        background: linear-gradient(45deg, #f0932b, #e84393);
        color: white;
        font-size: 12px;
    }
    .progress-bar {
        height: 10px;
        background: #333;
        border-radius: 5px;
        margin: 5px 0;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(45deg, #ff9f43, #ff6b6b);
        border-radius: 5px;
    }
    .whatsapp { background: #25D366; }
    .facebook { background: #1877F2; }
    .twitter { background: #1DA1F2; }
    .telegram { background: #0088cc; }
    .social-share-btn {
        display: inline-block;
        padding: 8px 18px;
        margin: 5px;
        border-radius: 30px;
        text-decoration: none;
        color: white !important;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ========== SECURE SECRETS ==========
try:
    ADMIN_SECRET = st.secrets["ADMIN_SECRET"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    st.error("⚠️ Please set ADMIN_SECRET and ADMIN_PASSWORD in Streamlit Secrets!")
    st.stop()

# ========== HELPER FUNCTIONS ==========
def hash_password(pwd):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', pwd.encode(), salt, 100000)
    return salt.hex() + ':' + dk.hex()

def verify_password(stored, provided):
    try:
        salt_hex, dk_hex = stored.split(':')
        salt = bytes.fromhex(salt_hex)
        new_dk = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt, 100000)
        return new_dk.hex() == dk_hex
    except:
        return False

def generate_unique_code(conn):
    """Generate unique 6-character referral code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE referral_code=?", (code,))
        if not c.fetchone():
            return code

@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect('referral_game.db', check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")  # Increased to 10 seconds
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Core tables
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, mobile TEXT UNIQUE, password TEXT,
                  referral_code TEXT UNIQUE, points INTEGER DEFAULT 0,
                  referred_by_id INTEGER, join_date TEXT, ip_address TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referral_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER, referred_user_id INTEGER,
                  points_earned INTEGER, referral_date TEXT,
                  UNIQUE(referrer_id, referred_user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS discount_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, points_used INTEGER,
                  discount_amount REAL, claim_date TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, message TEXT, is_read INTEGER DEFAULT 0,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS repair_categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category_name TEXT, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_repair_selections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, category_id INTEGER,
                  selection_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referral_clicks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referral_code TEXT, referrer_id INTEGER,
                  ip_address TEXT, clicked_at TEXT,
                  is_converted INTEGER DEFAULT 0)''')
    
    # Game-specific tables
    c.execute('''CREATE TABLE IF NOT EXISTS daily_bonus
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, claim_date TEXT, streak INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS spin_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, points_won INTEGER, spin_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_badges
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, badge_name TEXT, earned_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS store_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item_name TEXT, points_required INTEGER, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS store_purchases
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, item_id INTEGER, purchase_date TEXT)''')
    
    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_referral_history_referrer ON referral_history(referrer_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_referral_clicks_code ON referral_clicks(referral_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)")
    
    # Seed store items if empty
    c.execute("SELECT COUNT(*) FROM store_items")
    if c.fetchone()[0] == 0:
        items = [
            ("🎁 500 PKR Discount", 500, "Show this at shop for 500 PKR off"),
            ("🛡️ Free Screen Guard", 300, "Get a tempered glass screen guard"),
            ("📱 Premium Phone Case", 200, "Silicone back cover (any model)"),
            ("🔋 Power Bank (10000mAh)", 800, "Free power bank with repair"),
        ]
        c.executemany("INSERT INTO store_items (item_name, points_required, description) VALUES (?,?,?)", items)
    
    # Seed repair categories
    c.execute("SELECT COUNT(*) FROM repair_categories")
    if c.fetchone()[0] == 0:
        cats = [
            ("🔋 Charging not working", "Phone not charging, battery or port issue"),
            ("📱 Broken Screen", "Display cracked, touch not working"),
            ("🔊 No sound", "Speaker or headphone jack issue"),
            ("🐌 Phone hanging", "Slow performance, frequent freezing"),
            ("⚡ Battery drains fast", "Battery health degraded"),
            ("📶 WiFi/Bluetooth not working", "Connectivity issues"),
            ("📷 Camera not working", "Black screen or crash"),
            ("🔥 Phone overheating", "Overheating during use or charging")
        ]
        c.executemany("INSERT INTO repair_categories (category_name, description) VALUES (?,?)", cats)

    # Ensure official account
    c.execute("SELECT id FROM users WHERE referral_code='ALIOFFICIAL'")
    if not c.fetchone():
        c.execute("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                  ("🏆 Ali Mobile Official", "03000000000", hash_password("admin123"), "ALIOFFICIAL", 0,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

init_db()

# ========== TRACK REFERRAL CLICKS FROM URL ==========
def track_referral_click():
    """Check URL for ?ref=CODE and record a click if not already tracked today for this IP"""
    params = st.query_params
    ref_code = params.get("ref")
    if ref_code and not st.session_state.get("click_tracked", False):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE referral_code=?", (ref_code.upper(),))
        referrer = c.fetchone()
        if referrer:
            ip = st.session_state.get("session_id", os.urandom(8).hex())
            today = datetime.now().strftime("%Y-%m-%d")
            c.execute("SELECT id FROM referral_clicks WHERE referral_code=? AND ip_address=? AND DATE(clicked_at)=?",
                      (ref_code.upper(), ip, today))
            if not c.fetchone():
                c.execute("INSERT INTO referral_clicks (referral_code, referrer_id, ip_address, clicked_at, is_converted) VALUES (?,?,?,?,0)",
                          (ref_code.upper(), referrer[0], ip, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
        st.session_state.click_tracked = True

track_referral_click()

# ========== GAME FUNCTIONS ==========
def add_notification(user_id, message):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)",
              (user_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def check_and_award_badges(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referral_history WHERE referrer_id=?", (user_id,))
    refs = c.fetchone()[0]
    c.execute("SELECT badge_name FROM user_badges WHERE user_id=?", (user_id,))
    earned = [row[0] for row in c.fetchall()]
    def award(badge):
        if badge not in earned:
            c.execute("INSERT INTO user_badges (user_id, badge_name, earned_date) VALUES (?,?,?)",
                      (user_id, badge, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            add_notification(user_id, f"🏅 You earned the badge: {badge}")
    if refs >= 1: award("First Referral 🥉")
    if refs >= 5: award("5 Referrals 🥈")
    if refs >= 10: award("10 Referrals 🥇")
    if refs >= 25: award("Referral King 👑")
    c.execute("SELECT COUNT(*) FROM discount_history WHERE user_id=?", (user_id,))
    if c.fetchone()[0] > 0:
        award("Discount Claimer 💰")
    conn.commit()

def get_level(points):
    if points < 100: return ("Bronze", "#cd7f32")
    elif points < 300: return ("Silver", "#c0c0c0")
    elif points < 600: return ("Gold", "#ffd700")
    else: return ("Diamond", "#b9f2ff")

def daily_bonus_claim(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM daily_bonus WHERE user_id=? AND claim_date=?", (user_id, today))
    if c.fetchone():
        return 0, "already_claimed"
    c.execute("SELECT claim_date, streak FROM daily_bonus WHERE user_id=? ORDER BY claim_date DESC LIMIT 1", (user_id,))
    last = c.fetchone()
    if last:
        last_date = datetime.strptime(last[0], "%Y-%m-%d").date()
        yesterday = datetime.now().date() - timedelta(days=1)
        if last_date == yesterday:
            new_streak = last[1] + 1
        else:
            new_streak = 1
    else:
        new_streak = 1
    bonus = 5 if new_streak < 7 else 50
    c.execute("INSERT INTO daily_bonus (user_id, claim_date, streak) VALUES (?,?,?)", (user_id, today, new_streak))
    c.execute("UPDATE users SET points = points + ? WHERE id=?", (bonus, user_id))
    conn.commit()
    check_and_award_badges(user_id)
    return bonus, "success"

def spin_wheel(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM spin_history WHERE user_id=? AND spin_date=?", (user_id, today))
    if c.fetchone():
        return 0, "already_spun"
    prizes = [5, 10, 20, 30, 50, 100, 200]
    weights = [40, 25, 15, 10, 5, 3, 2]
    won = random.choices(prizes, weights=weights, k=1)[0]
    c.execute("INSERT INTO spin_history (user_id, points_won, spin_date) VALUES (?,?,?)", (user_id, won, today))
    c.execute("UPDATE users SET points = points + ? WHERE id=?", (won, user_id))
    conn.commit()
    add_notification(user_id, f"🎰 You won {won} points from the lucky wheel!")
    check_and_award_badges(user_id)
    return won, "success"

def get_social_urls(referral_link, code, name):
    msg = f"📱 Ali Mobile Repair - Referral Race!\n\nMy referral code: {code}\nJoin: {referral_link}\n\n50 points per referral! 500 points = 500 PKR discount!"
    encoded = urllib.parse.quote(msg)
    encoded_link = urllib.parse.quote(referral_link)
    return {
        "whatsapp": f"https://wa.me/?text={encoded}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={encoded_link}",
        "twitter": f"https://twitter.com/intent/tweet?text={encoded}",
        "telegram": f"https://t.me/share/url?url={encoded_link}&text={encoded}"
    }

def normalize_csv_columns(df):
    mapping = {'نام': 'name', 'موبائل': 'mobile', 'ریفرل کوڈ': 'referral_code', 'پوائنٹس': 'points'}
    df.rename(columns=mapping, inplace=True, errors='ignore')
    return df

def delete_user(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT referred_by_id FROM users WHERE id=?", (user_id,))
    ref_by = c.fetchone()
    if ref_by and ref_by[0]:
        c.execute("SELECT points_earned FROM referral_history WHERE referrer_id=? AND referred_user_id=?", (ref_by[0], user_id))
        pts = c.fetchone()
        if pts:
            c.execute("UPDATE users SET points = points - ? WHERE id=?", (pts[0], ref_by[0]))
            add_notification(ref_by[0], f"⚠️ A user you referred was deleted. {pts[0]} points removed.")
    c.execute("DELETE FROM referral_history WHERE referrer_id=? OR referred_user_id=?", (user_id, user_id))
    c.execute("DELETE FROM discount_history WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM user_repair_selections WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM referral_clicks WHERE referrer_id=?", (user_id,))
    c.execute("DELETE FROM daily_bonus WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM spin_history WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM user_badges WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM store_purchases WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()

def reset_password(user_id):
    new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed = hash_password(new_pass)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM users WHERE id=?", (user_id,))
    name = c.fetchone()[0]
    c.execute("UPDATE users SET password=? WHERE id=?", (hashed, user_id))
    conn.commit()
    add_notification(user_id, f"🔐 Your password was reset by admin. New password: {new_pass}")
    return new_pass, name

# ========== REGISTRATION WITH AUTO-RETRY LOGIC ==========
def register_with_retry(name, mobile, password, ref_code, retries=3, delay=1):
    """
    Attempt to register user with automatic retry on database lock or timeout.
    """
    for attempt in range(retries):
        conn = None
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Validate referral code
            c.execute("SELECT id FROM users WHERE referral_code=?", (ref_code.upper(),))
            ref_user = c.fetchone()
            if not ref_user:
                return False, "Invalid referral code."
            
            # Check mobile duplicate
            c.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
            if c.fetchone():
                return False, "Mobile already registered."
            
            # Begin transaction
            conn.execute("BEGIN IMMEDIATE")  # Locks database to avoid conflicts
            
            new_code = generate_unique_code(conn)
            hashed = hash_password(password)
            join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Insert new user
            c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by_id, join_date) VALUES (?,?,?,?,?,?,?)",
                      (name, mobile, hashed, new_code, 0, ref_user[0], join_date))
            new_user_id = c.lastrowid
            
            # Add points to referrer and record history
            c.execute("UPDATE users SET points = points + 50 WHERE id=?", (ref_user[0],))
            c.execute("INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date) VALUES (?,?,?,?)",
                      (ref_user[0], new_user_id, 50, join_date))
            
            # Mark click as converted
            c.execute("UPDATE referral_clicks SET is_converted=1 WHERE referral_code=? AND referrer_id=? AND is_converted=0 ORDER BY clicked_at DESC LIMIT 1",
                      (ref_code.upper(), ref_user[0]))
            
            conn.commit()
            add_notification(ref_user[0], f"🎉 New user {name} registered using your code! +50 points.")
            check_and_award_badges(ref_user[0])
            return True, new_code
        
        except sqlite3.OperationalError as e:
            if conn:
                conn.rollback()
            if "locked" in str(e) or "busy" in str(e):
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))  # exponential backoff
                    continue
                else:
                    return False, f"Database busy. Please try again in a few seconds."
            else:
                return False, f"System error: {str(e)}"
        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Unexpected error: {str(e)}"
        finally:
            if conn:
                conn.close()
    return False, "Max retries exceeded."

# ========== SESSION STATE ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.user_code = None
if 'page' not in st.session_state:
    st.session_state.page = "Home"

# ========== TOP HEADER ==========
st.markdown("""
<div style="text-align:center; padding:20px; background:linear-gradient(135deg, #121212, #1e1e2f); border-radius:20px; border:1px solid #ff9f43; margin-bottom:20px;">
    <h1 class="neon-text"> Ali Mobile Repair  Referral System</h1>
    <p style="color:#ff9f43;">Ali Laal Road, Layyah | 📞 03006762827</p>
    <p style="color:#e0e0e0;">⚡ Race to the Top! Refer, Earn, Spin & Win!</p>
</div>
""", unsafe_allow_html=True)

# ========== NAVIGATION ==========
page_map = {
    "🏠 Home": "Home",
    "✨ Register": "Register",
    "🔐 Login": "Login",
    "🏆 Dashboard / Profile": "Dashboard",
    "🏅 Leaderboard": "Leaderboard",
    "📜 Referral History": "ReferralHistory",
    "💰 Discount History": "DiscountHistory",
    "📊 Click Analytics": "ClickAnalytics",
    "🔧 Repair Issues": "RepairCategories",
    "🛒 Points Store": "Store",
    "👑 Admin": "AdminPanel"
}

with st.sidebar:
    st.markdown("## 🧭 Menu")
    menu_options = ["🏠 Home", "✨ Register", "🔐 Login", "🏅 Leaderboard", "🔧 Repair Issues", "🛒 Points Store"]
    if st.session_state.logged_in:
        menu_options = ["🏆 Dashboard / Profile", "🏅 Leaderboard", "📜 Referral History", "💰 Discount History",
                        "📊 Click Analytics", "🔧 Repair Issues", "🛒 Points Store"]
    admin_input = st.text_input("Admin Secret", type="password", placeholder="Enter secret for admin", key="admin_secret")
    if admin_input == ADMIN_SECRET:
        menu_options.append("👑 Admin")
    selected = st.selectbox("Navigate", menu_options, label_visibility="collapsed")
    if st.session_state.page != page_map[selected]:
        st.session_state.page = page_map[selected]
        st.rerun()

# ========== NOTIFICATIONS ==========
if st.session_state.logged_in:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, message FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_at DESC",
              (st.session_state.user_id,))
    notifs = c.fetchall()
    if notifs:
        with st.expander(f"🔔 You have {len(notifs)} new notification(s)"):
            for n in notifs:
                st.markdown(f'📢 {n[1]}')
        ids = [n[0] for n in notifs]
        c.execute(f"UPDATE notifications SET is_read=1 WHERE id IN ({','.join('?'*len(ids))})", ids)
        conn.commit()

# ========== PAGE RENDERING ==========
if st.session_state.page == "Home":
    if not st.session_state.logged_in:
        st.markdown("""
        <div class="gradient-card">
            <h2>Welcome to the Referral System</h2>
            <p>Join now and earn points by referring friends. Spin the wheel, earn badges, and redeem awesome prizes!</p>
            <p><strong>💡 Use referral code <span style="color:#ff9f43;">ALIOFFICIAL</span> to start</strong></p>
        </div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✨ Register Now"):
                st.session_state.page = "Register"
                st.rerun()
        with col2:
            if st.button("🔐 Login"):
                st.session_state.page = "Login"
                st.rerun()
        st.markdown("---")
        st.markdown("### 🛠️ Our Repair Services")
        st.markdown("""
        - 🔧 Screen Replacement
        - 🔋 Battery Replacement
        - ⚡ Charging Port
        - 📶 Software / FRP
        - 📷 Camera
        - 🎧 Audio / Speaker
        """)
    else:
        st.success(f"Welcome back, {st.session_state.user_name}! Head to your Dashboard to play!")
        if st.button("Go to Dashboard"):
            st.session_state.page = "Dashboard"
            st.rerun()

elif st.session_state.page == "Register":
    if st.session_state.logged_in:
        st.warning("Already logged in")
        st.stop()
    with st.form("reg_form"):
        st.subheader("✨ Create Your Account")
        name = st.text_input("Full Name")
        mobile = st.text_input("Mobile Number")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        ref_code = st.text_input("Referral Code (required)", value="ALIOFFICIAL")
        submitted = st.form_submit_button("Register")
        if submitted:
            if not name or not mobile or not password:
                st.error("All fields required.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif len(password) < 4:
                st.error("Password must be at least 4 characters.")
            elif not ref_code:
                st.error("Referral code is required.")
            else:
                with st.spinner("Registering, please wait..."):
                    success, result = register_with_retry(name, mobile, password, ref_code)
                    if success:
                        st.success(f"✅ Registration complete! Your referral code: {result}")
                        st.balloons()
                    else:
                        st.error(f"Registration failed: {result}")

elif st.session_state.page == "Login":
    if st.session_state.logged_in:
        st.warning("Already logged in")
        st.stop()
    with st.form("login_form"):
        st.subheader("🔐 Login")
        mobile = st.text_input("Mobile Number")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
            user = c.fetchone()
            if user and verify_password(user[3], password):
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.user_name = user[1]
                st.session_state.user_code = user[4]
                st.success("Login successful!")
                st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("Invalid credentials.")

elif st.session_state.page == "Dashboard":
    if not st.session_state.logged_in:
        st.warning("Please login")
        st.stop()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, mobile, referral_code, points FROM users WHERE id=?", (st.session_state.user_id,))
    user = c.fetchone()
    name, mobile, code, points = user
    level, color = get_level(points)
    st.markdown(f"""
    <div class="gradient-card">
        <h2>🏆 {name} <span style="color:{color}">[{level}]</span></h2>
        <p>📱 {mobile} | 🔑 Code: {code}</p>
        <div class="progress-bar">
            <div class="progress-fill" style="width:{min(points/600*100,100)}%"></div>
        </div>
        <p>⭐ {points} points (next level at {100 if level=='Bronze' else 300 if level=='Silver' else 600} pts)</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎁 Claim Daily Bonus"):
            bonus, status = daily_bonus_claim(st.session_state.user_id)
            if status == "already_claimed":
                st.warning("Already claimed today!")
            else:
                st.success(f"+{bonus} points! {'🔥 7-day streak bonus!' if bonus==50 else ''}")
                st.rerun()
    with col2:
        if st.button("🎰 Spin the Wheel!"):
            won, status = spin_wheel(st.session_state.user_id)
            if status == "already_spun":
                st.warning("Already spun today!")
            else:
                st.balloons()
                st.success(f"You won {won} points!")
                st.rerun()

    c.execute("SELECT badge_name FROM user_badges WHERE user_id=?", (st.session_state.user_id,))
    badges = [b[0] for b in c.fetchall()]
    if badges:
        st.markdown("### 🏅 Your Badges: " + ", ".join(badges))

    # Referral Link
    try:
        host = st.get_option("server.baseUrlPath") or "alimobile-referral.streamlit.app"
        if host.startswith("/"):
            host = host.lstrip("/")
        base = f"https://{host}" if "://" not in host else host
    except:
        base = "https://alimobile-referral.streamlit.app"
    referral_link = f"{base}/?ref={code}"
    st.markdown("### 📤 Your Referral Link")
    st.code(referral_link)
    urls = get_social_urls(referral_link, code, name)
    cols = st.columns(4)
    for (platform, url), col in zip(urls.items(), cols):
        with col:
            st.markdown(f'<a href="{url}" target="_blank" class="social-share-btn {platform}">{platform.capitalize()}</a>', unsafe_allow_html=True)

    if points >= 500:
        if st.button("🎁 Claim 500 PKR Discount (500 pts)"):
            c.execute("INSERT INTO discount_history (user_id, points_used, discount_amount, claim_date, status) VALUES (?,?,?,?,?)",
                      (st.session_state.user_id, 500, 500.0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "claimed"))
            c.execute("UPDATE users SET points = points - 500 WHERE id=?", (st.session_state.user_id,))
            conn.commit()
            add_notification(st.session_state.user_id, "🎁 You claimed 500 PKR discount! Show this at shop.")
            check_and_award_badges(st.session_state.user_id)
            st.success("🎉 Discount claimed! Show your code at shop.")
            st.rerun()
    else:
        st.info(f"Need {500-points} more points for 500 PKR discount.")

    if st.button("🚪 Logout"):
        for key in ['logged_in', 'user_id', 'user_name', 'user_code', 'click_tracked']:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.page = "Home"
        st.rerun()

elif st.session_state.page == "Leaderboard":
    st.subheader("🏅 Top Players")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.name, u.points, u.referral_code, u.join_date, COUNT(rh.id) as refs
        FROM users u LEFT JOIN referral_history rh ON u.id = rh.referrer_id
        GROUP BY u.id ORDER BY u.points DESC LIMIT 20
    """)
    top = c.fetchall()
    for i, u in enumerate(top[:10], 1):
        col1, col2, col3, col4 = st.columns([1,2,2,1])
        col1.write(f"#{i}")
        col2.write(u[0])
        col3.write(f"⭐ {u[1]}")
        col4.write(f"👥 {u[4]}")
    if len(top) > 10:
        with st.expander("Show more"):
            for i, u in enumerate(top[10:], 11):
                st.write(f"{i}. {u[0]} - ⭐ {u[1]} - 👥 {u[4]} refs")

elif st.session_state.page == "ReferralHistory":
    if not st.session_state.logged_in: st.stop()
    st.subheader("📜 Your Referral History")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT u.name, rh.points_earned, rh.referral_date FROM referral_history rh JOIN users u ON rh.referred_user_id=u.id WHERE rh.referrer_id=? ORDER BY rh.referral_date DESC", (st.session_state.user_id,))
    hist = c.fetchall()
    for h in hist:
        st.write(f"✅ {h[2][:10]} – {h[0]} → +{h[1]} pts")

elif st.session_state.page == "DiscountHistory":
    if not st.session_state.logged_in: st.stop()
    st.subheader("💰 Your Discount Claims")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id=? ORDER BY claim_date DESC", (st.session_state.user_id,))
    hist = c.fetchall()
    for h in hist:
        st.write(f"🎁 {h[2][:10]} – -{h[0]} pts → {h[1]} PKR")

elif st.session_state.page == "ClickAnalytics":
    if not st.session_state.logged_in: st.stop()
    st.subheader("📊 Click Analytics")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referral_clicks WHERE referrer_id=?", (st.session_state.user_id,))
    total_clicks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referral_history WHERE referrer_id=?", (st.session_state.user_id,))
    conversions = c.fetchone()[0]
    rate = (conversions/total_clicks*100) if total_clicks>0 else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("👆 Clicks", total_clicks)
    col2.metric("✅ Signups", conversions)
    col3.metric("📈 Rate", f"{rate:.1f}%")
    c.execute("SELECT clicked_at, is_converted FROM referral_clicks WHERE referrer_id=? ORDER BY clicked_at DESC LIMIT 20", (st.session_state.user_id,))
    recent = c.fetchall()
    for r in recent:
        status = "✅ Converted" if r[1] else "⏳ Pending"
        st.write(f"{r[0]} → {status}")

elif st.session_state.page == "RepairCategories":
    st.subheader("🔧 Report a Repair Issue")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, category_name, description FROM repair_categories")
    cats = c.fetchall()
    for cat in cats:
        with st.expander(cat[1]):
            st.write(cat[2])
            if st.session_state.logged_in:
                if st.button("Report this issue", key=f"rep_{cat[0]}"):
                    c.execute("INSERT INTO user_repair_selections (user_id, category_id, selection_date) VALUES (?,?,?)",
                              (st.session_state.user_id, cat[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success("Issue reported! We'll contact you.")
            else:
                st.caption("Login to report")
    if st.session_state.logged_in:
        st.markdown("---")
        st.subheader("Your Reported Issues")
        c.execute("SELECT rc.category_name, us.selection_date FROM user_repair_selections us JOIN repair_categories rc ON us.category_id=rc.id WHERE us.user_id=? ORDER BY us.selection_date DESC LIMIT 5", (st.session_state.user_id,))
        for r in c.fetchall():
            st.write(f"📌 {r[1][:10]}: {r[0]}")

elif st.session_state.page == "Store":
    st.subheader("🛒 Points Store")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, item_name, points_required, description FROM store_items")
    items = c.fetchall()
    if st.session_state.logged_in:
        c.execute("SELECT points FROM users WHERE id=?", (st.session_state.user_id,))
        points = c.fetchone()[0]
        st.info(f"Your Points: {points}")
        for item in items:
            with st.container():
                st.markdown(f"**{item[1]}** – {item[2]} ({item[2]} points)")
                if points >= item[2]:
                    if st.button(f"Redeem ({item[2]} pts)", key=f"buy_{item[0]}"):
                        c.execute("INSERT INTO store_purchases (user_id, item_id, purchase_date) VALUES (?,?,?)",
                                  (st.session_state.user_id, item[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        c.execute("UPDATE users SET points = points - ? WHERE id=?", (item[2], st.session_state.user_id))
                        conn.commit()
                        add_notification(st.session_state.user_id, f"🛒 You redeemed {item[1]}")
                        st.success(f"Redeemed {item[1]}! Show at shop.")
                        st.rerun()
                else:
                    st.button(f"Need {item[2]-points} more pts", disabled=True, key=f"need_{item[0]}")
    else:
        st.warning("Login to redeem items.")

elif st.session_state.page == "AdminPanel":
    if admin_input != ADMIN_SECRET:
        st.error("Admin secret required")
        st.stop()
    st.success("👑 Admin Panel")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Users", "Export", "Upload CSV", "Bulk Points", "Clicks Report", "Repair Reports"])
    with tab1:
        search = st.text_input("Search")
        conn = get_db_connection()
        c = conn.cursor()
        if search:
            c.execute("SELECT id, name, mobile, referral_code, points, join_date FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC",
                      (f'%{search}%', f'%{search}%'))
        else:
            c.execute("SELECT id, name, mobile, referral_code, points, join_date FROM users ORDER BY points DESC")
        users = c.fetchall()
        for u in users:
            cols = st.columns([1,2,2,1,1,2,2])
            cols[0].write(u[0])
            cols[1].write(u[1])
            cols[2].write(u[2])
            cols[3].write(u[3])
            cols[4].write(f"⭐ {u[4]}")
            cols[5].write(u[5][:10] if u[5] else "N/A")
            with cols[6]:
                if st.button("Reset Pwd", key=f"reset_{u[0]}"):
                    new_pwd, _ = reset_password(u[0])
                    st.success(f"New password: {new_pwd}")
                if st.button("Delete", key=f"del_{u[0]}"):
                    delete_user(u[0])
                    st.success("Deleted")
                    st.rerun()
    with tab2:
        c.execute("SELECT id, name, mobile, referral_code, points, referred_by_id, join_date FROM users")
        df = pd.DataFrame(c.fetchall(), columns=["ID","Name","Mobile","Code","Points","Referred By","Join Date"])
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "users.csv")
    with tab3:
        uploaded = st.file_uploader("Upload CSV")
        if uploaded:
            df = pd.read_csv(uploaded)
            df = normalize_csv_columns(df)
            if st.button("Merge"):
                added = skipped = 0
                conn = get_db_connection()
                c = conn.cursor()
                for _, row in df.iterrows():
                    mobile = str(row.get("mobile", ""))
                    if not mobile: continue
                    c.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
                    if not c.fetchone():
                        c.execute("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                                  (row.get("name",""), mobile, hash_password("temp123"), generate_unique_code(conn), int(row.get("points",0)), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        added += 1
                    else:
                        skipped += 1
                conn.commit()
                st.success(f"Added {added}, skipped {skipped}")
    with tab4:
        pts = st.number_input("Points to add to all", min_value=0, step=50)
        if st.button("Add to All"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("UPDATE users SET points = points + ?", (pts,))
            conn.commit()
            st.success(f"Added {pts} points to everyone.")
    with tab5:
        c.execute("SELECT u.name, rc.clicked_at, rc.is_converted FROM referral_clicks rc JOIN users u ON rc.referrer_id=u.id ORDER BY rc.clicked_at DESC")
        clicks = c.fetchall()
        for cl in clicks:
            st.write(f"{cl[0]} → {cl[1]} → {'Converted' if cl[2] else 'Pending'}")
    with tab6:
        c.execute("SELECT u.name, u.mobile, rc.category_name, us.selection_date FROM user_repair_selections us JOIN users u ON us.user_id=u.id JOIN repair_categories rc ON us.category_id=rc.id ORDER BY us.selection_date DESC")
        reports = c.fetchall()
        for r in reports:
            st.write(f"{r[0]} ({r[1]}) – {r[2]} – {r[3][:16]}")
