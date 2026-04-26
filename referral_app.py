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

# ========== GAMING THEME ==========
st.markdown("""
<style>
    .stApp { background: #0a0a0a; }
    h1, h2, h3, h4, h5, h6, p, label, div, span { color: #e0e0e0 !important; }
    .neon-text { color: #fff; text-shadow: 0 0 10px #ff9f43, 0 0 20px #ff6b6b; }
    .card, .metric-card, .referral-history-item, .discount-history-item, .notification {
        background: #121212; border: 1px solid #333; border-radius: 15px; padding: 15px; margin: 10px 0; transition: 0.3s;
    }
    .card:hover { border-color: #ff9f43; }
    .gradient-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 30px; border-radius: 15px; border: 1px solid #ff9f43;
    }
    .stButton button {
        background: linear-gradient(45deg, #ff9f43, #ff6b6b);
        border: none; color: white; border-radius: 30px; font-weight: bold; transition: 0.3s;
    }
    .stButton button:hover { transform: scale(1.05); box-shadow: 0 0 20px #ff9f43; }
    .whatsapp { background: #25D366; }
    .facebook { background: #1877F2; }
    .twitter { background: #1DA1F2; }
    .telegram { background: #0088cc; }
    .social-share-btn {
        display: inline-block; padding: 8px 18px; margin: 5px; border-radius: 30px;
        text-decoration: none; color: white !important; font-weight: bold;
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

# ========== DATABASE FUNCTIONS (no caching - each call opens and closes) ==========
def get_new_connection():
    """Create a brand new database connection (not cached)."""
    conn = sqlite3.connect('referral_game.db', timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetch=False, commit=False, retries=5):
    """Execute a query with retry, always using a fresh connection."""
    for attempt in range(retries):
        conn = None
        try:
            conn = get_new_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit:
                conn.commit()
            if fetch:
                result = cursor.fetchall()
                return result
            else:
                return None
        except sqlite3.OperationalError as e:
            if conn:
                conn.rollback()
            if "locked" in str(e) or "busy" in str(e):
                time.sleep(0.5 * (attempt + 1))
                continue
            else:
                raise
        finally:
            if conn:
                conn.close()
    raise Exception("Database busy after retries. Use Admin -> Force Repair Database.")

# ========== INITIAL DATABASE SETUP ==========
def init_database():
    """Create tables and seed data (runs once at startup)."""
    # Create tables
    execute_query("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mobile TEXT UNIQUE, password TEXT,
        referral_code TEXT UNIQUE, points INTEGER DEFAULT 0, referred_by_id INTEGER,
        join_date TEXT, ip_address TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS referral_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_user_id INTEGER,
        points_earned INTEGER, referral_date TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS discount_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, points_used INTEGER,
        discount_amount REAL, claim_date TEXT, status TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
        is_read INTEGER DEFAULT 0, created_at TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS repair_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, category_name TEXT, description TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS user_repair_selections (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, category_id INTEGER, selection_date TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS referral_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, referral_code TEXT, referrer_id INTEGER,
        ip_address TEXT, clicked_at TEXT, is_converted INTEGER DEFAULT 0)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS daily_bonus (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, claim_date TEXT, streak INTEGER DEFAULT 1)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS spin_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, points_won INTEGER, spin_date TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS user_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, badge_name TEXT, earned_date TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS store_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, points_required INTEGER, description TEXT)""", commit=True)
    execute_query("""CREATE TABLE IF NOT EXISTS store_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_id INTEGER, purchase_date TEXT)""", commit=True)
    
    # Indexes
    execute_query("CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)", commit=True)
    execute_query("CREATE INDEX IF NOT EXISTS idx_referral_history_referrer ON referral_history(referrer_id)", commit=True)
    execute_query("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_referral ON referral_history(referrer_id, referred_user_id)", commit=True)
    
    # Seed store items
    count = execute_query("SELECT COUNT(*) FROM store_items", fetch=True)[0][0]
    if count == 0:
        items = [
            ("🎁 500 PKR Discount", 500, "Show this at shop for 500 PKR off"),
            ("🛡️ Free Screen Guard", 300, "Get a tempered glass screen guard"),
            ("📱 Premium Phone Case", 200, "Silicone back cover (any model)"),
            ("🔋 Power Bank (10000mAh)", 800, "Free power bank with repair"),
        ]
        for item in items:
            execute_query("INSERT INTO store_items (item_name, points_required, description) VALUES (?,?,?)", item, commit=True)
    
    # Seed repair categories
    cat_count = execute_query("SELECT COUNT(*) FROM repair_categories", fetch=True)[0][0]
    if cat_count == 0:
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
        for cat in cats:
            execute_query("INSERT INTO repair_categories (category_name, description) VALUES (?,?)", cat, commit=True)
    
    # Ensure official account
    official = execute_query("SELECT id FROM users WHERE referral_code='ALIOFFICIAL'", fetch=True)
    if not official:
        hashed = hash_password("admin123")
        execute_query("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                      ("🏆 Ali Mobile Official", "03000000000", hashed, "ALIOFFICIAL", 0,
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
    
    # Add streak column if missing (migration)
    cols = execute_query("PRAGMA table_info(daily_bonus)", fetch=True)
    if 'streak' not in [c[1] for c in cols]:
        execute_query("ALTER TABLE daily_bonus ADD COLUMN streak INTEGER DEFAULT 1", commit=True)

# Run init once at startup
try:
    init_database()
except Exception as e:
    st.error(f"Database init error: {e}")
    st.info("Click below to repair automatically (will delete old database and recreate).")
    if st.button("🛠️ Force Repair Database (Admin Only)"):
        try:
            if os.path.exists('referral_game.db'):
                os.remove('referral_game.db')
            st.success("Database deleted. Please refresh the page.")
            st.stop()
        except:
            st.error("Could not delete. Please go to Manage app > Files and delete 'referral_game.db' manually.")
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

def get_level(points):
    if points < 100: return ("Bronze", "#cd7f32")
    elif points < 300: return ("Silver", "#c0c0c0")
    elif points < 600: return ("Gold", "#ffd700")
    else: return ("Diamond", "#b9f2ff")

def add_notification(user_id, message):
    execute_query("INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)",
                  (user_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)

def generate_unique_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        existing = execute_query("SELECT id FROM users WHERE referral_code=?", (code,), fetch=True)
        if not existing:
            return code

def register_user(name, mobile, password, ref_code):
    # Check referrer
    referrer = execute_query("SELECT id FROM users WHERE referral_code=?", (ref_code.upper(),), fetch=True)
    if not referrer:
        return False, "Invalid referral code."
    # Check existing mobile
    existing = execute_query("SELECT id FROM users WHERE mobile=?", (mobile,), fetch=True)
    if existing:
        return False, "Mobile already registered."
    # Generate code
    new_code = generate_unique_code()
    hashed = hash_password(password)
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Begin transaction manually using a single connection
        conn = get_new_connection()
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by_id, join_date) VALUES (?,?,?,?,?,?,?)",
                  (name, mobile, hashed, new_code, 0, referrer[0]['id'], join_date))
        new_id = c.lastrowid
        c.execute("UPDATE users SET points = points + 50 WHERE id=?", (referrer[0]['id'],))
        c.execute("INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date) VALUES (?,?,?,?)",
                  (referrer[0]['id'], new_id, 50, join_date))
        c.execute("UPDATE referral_clicks SET is_converted=1 WHERE referral_code=? AND referrer_id=? AND is_converted=0 ORDER BY clicked_at DESC LIMIT 1",
                  (ref_code.upper(), referrer[0]['id']))
        conn.commit()
        conn.close()
        add_notification(referrer[0]['id'], f"🎉 New user {name} registered using your code! +50 points.")
        # Check badges for referrer
        ref_count = execute_query("SELECT COUNT(*) FROM referral_history WHERE referrer_id=?", (referrer[0]['id'],), fetch=True)[0][0]
        if ref_count == 1:
            add_notification(referrer[0]['id'], "🏅 You earned the badge: First Referral 🥉")
            execute_query("INSERT INTO user_badges (user_id, badge_name, earned_date) VALUES (?,?,?)",
                          (referrer[0]['id'], "First Referral 🥉", join_date), commit=True)
        elif ref_count == 5:
            add_notification(referrer[0]['id'], "🏅 You earned the badge: 5 Referrals 🥈")
            execute_query("INSERT INTO user_badges (user_id, badge_name, earned_date) VALUES (?,?,?)",
                          (referrer[0]['id'], "5 Referrals 🥈", join_date), commit=True)
        elif ref_count == 10:
            add_notification(referrer[0]['id'], "🏅 You earned the badge: 10 Referrals 🥇")
            execute_query("INSERT INTO user_badges (user_id, badge_name, earned_date) VALUES (?,?,?)",
                          (referrer[0]['id'], "10 Referrals 🥇", join_date), commit=True)
        return True, new_code
    except Exception as e:
        return False, f"Registration error: {e}"

def daily_bonus_claim(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    claimed = execute_query("SELECT id FROM daily_bonus WHERE user_id=? AND claim_date=?", (user_id, today), fetch=True)
    if claimed:
        return 0, "already_claimed"
    last = execute_query("SELECT claim_date, streak FROM daily_bonus WHERE user_id=? ORDER BY claim_date DESC LIMIT 1", (user_id,), fetch=True)
    if last:
        last_date = datetime.strptime(last[0][0], "%Y-%m-%d").date()
        yesterday = datetime.now().date() - timedelta(days=1)
        if last_date == yesterday:
            new_streak = last[0][1] + 1
        else:
            new_streak = 1
    else:
        new_streak = 1
    bonus = 5 if new_streak < 7 else 50
    execute_query("INSERT INTO daily_bonus (user_id, claim_date, streak) VALUES (?,?,?)", (user_id, today, new_streak), commit=True)
    execute_query("UPDATE users SET points = points + ? WHERE id=?", (bonus, user_id), commit=True)
    return bonus, "success"

def spin_wheel(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    spun = execute_query("SELECT id FROM spin_history WHERE user_id=? AND spin_date=?", (user_id, today), fetch=True)
    if spun:
        return 0, "already_spun"
    prizes = [5, 10, 20, 30, 50, 100, 200]
    weights = [40, 25, 15, 10, 5, 3, 2]
    won = random.choices(prizes, weights=weights, k=1)[0]
    execute_query("INSERT INTO spin_history (user_id, points_won, spin_date) VALUES (?,?,?)", (user_id, won, today), commit=True)
    execute_query("UPDATE users SET points = points + ? WHERE id=?", (won, user_id), commit=True)
    add_notification(user_id, f"🎰 You won {won} points from the lucky wheel!")
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

def delete_user(user_id):
    # Get referrer
    ref_by = execute_query("SELECT referred_by_id FROM users WHERE id=?", (user_id,), fetch=True)
    if ref_by and ref_by[0][0]:
        pts = execute_query("SELECT points_earned FROM referral_history WHERE referrer_id=? AND referred_user_id=?", (ref_by[0][0], user_id), fetch=True)
        if pts:
            execute_query("UPDATE users SET points = points - ? WHERE id=?", (pts[0][0], ref_by[0][0]), commit=True)
            add_notification(ref_by[0][0], f"⚠️ A user you referred was deleted. {pts[0][0]} points removed.")
    execute_query("DELETE FROM referral_history WHERE referrer_id=? OR referred_user_id=?", (user_id, user_id), commit=True)
    execute_query("DELETE FROM discount_history WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM notifications WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM user_repair_selections WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM referral_clicks WHERE referrer_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM daily_bonus WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM spin_history WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM user_badges WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM store_purchases WHERE user_id=?", (user_id,), commit=True)
    execute_query("DELETE FROM users WHERE id=?", (user_id,), commit=True)

def reset_password(user_id):
    new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed = hash_password(new_pass)
    name = execute_query("SELECT name FROM users WHERE id=?", (user_id,), fetch=True)[0][0]
    execute_query("UPDATE users SET password=? WHERE id=?", (hashed, user_id), commit=True)
    add_notification(user_id, f"🔐 Your password was reset by admin. New password: {new_pass}")
    return new_pass, name

# ========== TRACK REFERRAL CLICKS ==========
def track_referral_click():
    params = st.query_params
    ref_code = params.get("ref")
    if ref_code and not st.session_state.get("click_tracked", False):
        try:
            referrer = execute_query("SELECT id FROM users WHERE referral_code=?", (ref_code.upper(),), fetch=True)
            if referrer:
                ip = st.session_state.get("session_id", os.urandom(8).hex())
                today = datetime.now().strftime("%Y-%m-%d")
                existing = execute_query("SELECT id FROM referral_clicks WHERE referral_code=? AND ip_address=? AND DATE(clicked_at)=?",
                                         (ref_code.upper(), ip, today), fetch=True)
                if not existing:
                    execute_query("INSERT INTO referral_clicks (referral_code, referrer_id, ip_address, clicked_at, is_converted) VALUES (?,?,?,?,0)",
                                  (ref_code.upper(), referrer[0]['id'], ip, datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
        except:
            pass
        st.session_state.click_tracked = True

track_referral_click()

# ========== SESSION STATE ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.user_code = None
if 'page' not in st.session_state:
    st.session_state.page = "Home"

# ========== UI ==========
st.markdown("""
<div style="text-align:center; padding:20px; background:linear-gradient(135deg, #121212, #1e1e2f); border-radius:20px; border:1px solid #ff9f43; margin-bottom:20px;">
    <h1 class="neon-text"> Ali Mobile Repair  Referral System</h1>
    <p style="color:#ff9f43;">Ali Laal Road, Layyah | 📞 03006762827</p>
    <p style="color:#e0e0e0;">⚡ Race to the Top! Refer, Earn, Spin & Win!</p>
</div>
""", unsafe_allow_html=True)

# Navigation
page_map = {
    "🏠 Home": "Home", "✨ Register": "Register", "🔐 Login": "Login",
    "🏆 Dashboard / Profile": "Dashboard", "🏅 Leaderboard": "Leaderboard",
    "📜 Referral History": "ReferralHistory", "💰 Discount History": "DiscountHistory",
    "📊 Click Analytics": "ClickAnalytics", "🔧 Repair Issues": "RepairCategories",
    "🛒 Points Store": "Store", "👑 Admin": "AdminPanel"
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

# Notifications
if st.session_state.logged_in:
    notifs = execute_query("SELECT id, message FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_at DESC",
                           (st.session_state.user_id,), fetch=True)
    if notifs:
        with st.expander(f"🔔 You have {len(notifs)} new notification(s)"):
            for n in notifs:
                st.markdown(f'📢 {n[1]}')
        ids = [n[0] for n in notifs]
        execute_query(f"UPDATE notifications SET is_read=1 WHERE id IN ({','.join('?'*len(ids))})", ids, commit=True)

# Page rendering
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
        st.markdown("- 🔧 Screen Replacement\n- 🔋 Battery Replacement\n- ⚡ Charging Port\n- 📶 Software / FRP\n- 📷 Camera\n- 🎧 Audio / Speaker")
    else:
        st.success(f"Welcome back, {st.session_state.user_name}!")
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
        if st.form_submit_button("Register"):
            if not name or not mobile or not password:
                st.error("All fields required.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif len(password) < 4:
                st.error("Password must be at least 4 characters.")
            else:
                with st.spinner("Registering..."):
                    success, result = register_user(name, mobile, password, ref_code)
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
            user = execute_query("SELECT * FROM users WHERE mobile=?", (mobile,), fetch=True)
            if user and verify_password(user[0][3], password):
                st.session_state.logged_in = True
                st.session_state.user_id = user[0][0]
                st.session_state.user_name = user[0][1]
                st.session_state.user_code = user[0][4]
                st.success("Login successful!")
                st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("Invalid credentials.")

elif st.session_state.page == "Dashboard":
    if not st.session_state.logged_in:
        st.warning("Please login")
        st.stop()
    user = execute_query("SELECT name, mobile, referral_code, points FROM users WHERE id=?", (st.session_state.user_id,), fetch=True)[0]
    name, mobile, code, points = user
    level, color = get_level(points)
    st.markdown(f"""
    <div class="gradient-card">
        <h2>🏆 {name} <span style="color:{color}">[{level}]</span></h2>
        <p>📱 {mobile} | 🔑 Code: {code}</p>
        <div class="progress-bar"><div class="progress-fill" style="width:{min(points/600*100,100)}%"></div></div>
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
    
    badges = execute_query("SELECT badge_name FROM user_badges WHERE user_id=?", (st.session_state.user_id,), fetch=True)
    if badges:
        st.markdown("### 🏅 Your Badges: " + ", ".join([b[0] for b in badges]))
    
    # Referral link
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
            execute_query("INSERT INTO discount_history (user_id, points_used, discount_amount, claim_date, status) VALUES (?,?,?,?,?)",
                          (st.session_state.user_id, 500, 500.0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "claimed"), commit=True)
            execute_query("UPDATE users SET points = points - 500 WHERE id=?", (st.session_state.user_id,), commit=True)
            add_notification(st.session_state.user_id, "🎁 You claimed 500 PKR discount! Show this at shop.")
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
    top = execute_query("""
        SELECT u.name, u.points, u.referral_code, u.join_date, COUNT(rh.id) as refs
        FROM users u LEFT JOIN referral_history rh ON u.id = rh.referrer_id
        GROUP BY u.id ORDER BY u.points DESC LIMIT 20
    """, fetch=True)
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
    hist = execute_query("""
        SELECT u.name, rh.points_earned, rh.referral_date
        FROM referral_history rh JOIN users u ON rh.referred_user_id=u.id
        WHERE rh.referrer_id=? ORDER BY rh.referral_date DESC
    """, (st.session_state.user_id,), fetch=True)
    for h in hist:
        st.write(f"✅ {h[2][:10]} – {h[0]} → +{h[1]} pts")

elif st.session_state.page == "DiscountHistory":
    if not st.session_state.logged_in: st.stop()
    st.subheader("💰 Your Discount Claims")
    hist = execute_query("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id=? ORDER BY claim_date DESC",
                         (st.session_state.user_id,), fetch=True)
    for h in hist:
        st.write(f"🎁 {h[2][:10]} – -{h[0]} pts → {h[1]} PKR")

elif st.session_state.page == "ClickAnalytics":
    if not st.session_state.logged_in: st.stop()
    st.subheader("📊 Click Analytics")
    total_clicks = execute_query("SELECT COUNT(*) FROM referral_clicks WHERE referrer_id=?", (st.session_state.user_id,), fetch=True)[0][0]
    conversions = execute_query("SELECT COUNT(*) FROM referral_history WHERE referrer_id=?", (st.session_state.user_id,), fetch=True)[0][0]
    rate = (conversions/total_clicks*100) if total_clicks>0 else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("👆 Clicks", total_clicks)
    col2.metric("✅ Signups", conversions)
    col3.metric("📈 Rate", f"{rate:.1f}%")
    recent = execute_query("SELECT clicked_at, is_converted FROM referral_clicks WHERE referrer_id=? ORDER BY clicked_at DESC LIMIT 20",
                           (st.session_state.user_id,), fetch=True)
    for r in recent:
        status = "✅ Converted" if r[1] else "⏳ Pending"
        st.write(f"{r[0]} → {status}")

elif st.session_state.page == "RepairCategories":
    st.subheader("🔧 Report a Repair Issue")
    cats = execute_query("SELECT id, category_name, description FROM repair_categories", fetch=True)
    for cat in cats:
        with st.expander(cat[1]):
            st.write(cat[2])
            if st.session_state.logged_in:
                if st.button("Report this issue", key=f"rep_{cat[0]}"):
                    execute_query("INSERT INTO user_repair_selections (user_id, category_id, selection_date) VALUES (?,?,?)",
                                  (st.session_state.user_id, cat[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
                    st.success("Issue reported! We'll contact you.")
            else:
                st.caption("Login to report")
    if st.session_state.logged_in:
        st.markdown("---")
        st.subheader("Your Reported Issues")
        reports = execute_query("""
            SELECT rc.category_name, us.selection_date
            FROM user_repair_selections us JOIN repair_categories rc ON us.category_id=rc.id
            WHERE us.user_id=? ORDER BY us.selection_date DESC LIMIT 5
        """, (st.session_state.user_id,), fetch=True)
        for r in reports:
            st.write(f"📌 {r[1][:10]}: {r[0]}")

elif st.session_state.page == "Store":
    st.subheader("🛒 Points Store")
    items = execute_query("SELECT id, item_name, points_required, description FROM store_items", fetch=True)
    if st.session_state.logged_in:
        points = execute_query("SELECT points FROM users WHERE id=?", (st.session_state.user_id,), fetch=True)[0][0]
        st.info(f"Your Points: {points}")
        for item in items:
            with st.container():
                st.markdown(f"**{item[1]}** – {item[2]} points")
                if points >= item[2]:
                    if st.button(f"Redeem ({item[2]} pts)", key=f"buy_{item[0]}"):
                        execute_query("INSERT INTO store_purchases (user_id, item_id, purchase_date) VALUES (?,?,?)",
                                      (st.session_state.user_id, item[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
                        execute_query("UPDATE users SET points = points - ? WHERE id=?", (item[2], st.session_state.user_id), commit=True)
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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Users", "Export", "Upload CSV", "Bulk Points", "Clicks Report", "Repair Reports", "Database Tools"])
    
    with tab1:
        search = st.text_input("Search")
        if search:
            users = execute_query("SELECT id, name, mobile, referral_code, points, join_date FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC",
                                  (f'%{search}%', f'%{search}%'), fetch=True)
        else:
            users = execute_query("SELECT id, name, mobile, referral_code, points, join_date FROM users ORDER BY points DESC", fetch=True)
        for u in users:
            cols = st.columns([1,2,2,1,1,2,2])
            cols[0].write(u[0]); cols[1].write(u[1]); cols[2].write(u[2]); cols[3].write(u[3]); cols[4].write(f"⭐ {u[4]}"); cols[5].write(u[5][:10] if u[5] else "N/A")
            with cols[6]:
                if st.button("Reset Pwd", key=f"reset_{u[0]}"):
                    new_pwd, _ = reset_password(u[0])
                    st.success(f"New password: {new_pwd}")
                if st.button("Delete", key=f"del_{u[0]}"):
                    delete_user(u[0])
                    st.success("Deleted")
                    st.rerun()
    with tab2:
        df_data = execute_query("SELECT id, name, mobile, referral_code, points, referred_by_id, join_date FROM users", fetch=True)
        df = pd.DataFrame(df_data, columns=["ID","Name","Mobile","Code","Points","Referred By","Join Date"])
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "users.csv")
    with tab3:
        uploaded = st.file_uploader("Upload CSV")
        if uploaded:
            df = pd.read_csv(uploaded)
            # Simple normalization
            if 'موبائل' in df.columns:
                df.rename(columns={'موبائل': 'mobile', 'نام': 'name'}, inplace=True)
            if 'mobile' in df.columns:
                added = 0
                for _, row in df.iterrows():
                    mob = str(row.get("mobile", ""))
                    if not mob:
                        continue
                    existing = execute_query("SELECT id FROM users WHERE mobile=?", (mob,), fetch=True)
                    if not existing:
                        new_code = generate_unique_code()
                        hashed = hash_password("temp123")
                        execute_query("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                                      (row.get("name",""), mob, hashed, new_code, int(row.get("points",0)), datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
                        added += 1
                st.success(f"Added {added} users.")
    with tab4:
        pts = st.number_input("Points to add to all", min_value=0, step=50)
        if st.button("Add to All"):
            execute_query("UPDATE users SET points = points + ?", (pts,), commit=True)
            st.success(f"Added {pts} points to everyone.")
    with tab5:
        clicks = execute_query("SELECT u.name, rc.clicked_at, rc.is_converted FROM referral_clicks rc JOIN users u ON rc.referrer_id=u.id ORDER BY rc.clicked_at DESC", fetch=True)
        for cl in clicks:
            st.write(f"{cl[0]} → {cl[1]} → {'Converted' if cl[2] else 'Pending'}")
    with tab6:
        reports = execute_query("SELECT u.name, u.mobile, rc.category_name, us.selection_date FROM user_repair_selections us JOIN users u ON us.user_id=u.id JOIN repair_categories rc ON us.category_id=rc.id ORDER BY us.selection_date DESC", fetch=True)
        for r in reports:
            st.write(f"{r[0]} ({r[1]}) – {r[2]} – {r[3][:16]}")
    with tab7:
        st.warning("⚠️ This tool will delete the entire database and recreate it. All user data will be lost!")
        if st.button("🔥 Force Delete & Recreate Database (Admin Only)"):
            try:
                if os.path.exists('referral_game.db'):
                    os.remove('referral_game.db')
                st.success("Database deleted. Refreshing...")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Could not delete: {e}. Please delete manually via Manage app > Files.")
