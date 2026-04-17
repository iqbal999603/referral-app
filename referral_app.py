import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime
import pandas as pd
import urllib.parse
import requests
import re

# ========== PAGE CONFIG ==========
st.set_page_config(page_title="Ali Mobile Repair - Referral System", page_icon="📱", layout="wide")

# ========== CUSTOM CSS (BLUE BACKGROUND, WHITE TEXT) ==========
st.markdown("""
<style>
    /* Main background blue */
    .stApp {
        background: linear-gradient(135deg, #0a2b5e 0%, #1a4a8a 100%);
    }
    /* All main text white */
    .main, .stApp, .stMarkdown, .stText, .stMetric, .stDataFrame, .stSelectbox, .stTextInput, .stNumberInput {
        color: white !important;
    }
    /* Headers white */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown p {
        color: white !important;
    }
    /* Cards remain white with dark text for readability */
    .card, .metric-card, .referral-history-item, .discount-history-item, .notification {
        background: white !important;
        color: #333 !important;
    }
    .card p, .card h3, .metric-card h3, .metric-card h4, .notification {
        color: #333 !important;
    }
    /* Gradient card stays but text white */
    .gradient-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    .gradient-card p, .gradient-card h2 {
        color: white !important;
    }
    /* Buttons */
    .stButton button {
        background: linear-gradient(45deg, #ff9f43, #ff6b6b);
        border: none;
        color: white;
        border-radius: 40px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    /* Sidebar (if any) - but we use top menu, so ignore */
    /* Social share buttons */
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
        transition: 0.3s;
        text-align: center;
    }
    /* Top header */
    .top-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        color: white;
        text-align: center;
    }
    /* Expander */
    .streamlit-expanderHeader {
        color: white !important;
    }
    /* Dataframe */
    .dataframe {
        background: rgba(255,255,255,0.9);
        color: #333;
    }
</style>
""", unsafe_allow_html=True)

# ========== SECRETS ==========
try:
    ADMIN_SECRET = st.secrets["ADMIN_SECRET"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    ADMIN_SECRET = "Admin@51214725"
    ADMIN_PASSWORD = "Admin51214725"

# ========== DATABASE ==========
def get_db_connection():
    return sqlite3.connect('referral.db', check_same_thread=False)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table with ip_address column
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  mobile TEXT UNIQUE,
                  password TEXT,
                  referral_code TEXT UNIQUE,
                  points INTEGER DEFAULT 0,
                  referred_by_id INTEGER,
                  join_date TEXT,
                  ip_address TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referral_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER,
                  referred_user_id INTEGER,
                  points_earned INTEGER,
                  referral_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS discount_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  points_used INTEGER,
                  discount_amount REAL,
                  claim_date TEXT,
                  status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  message TEXT,
                  is_read INTEGER DEFAULT 0,
                  created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS repair_categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category_name TEXT,
                  description TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_repair_selections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  category_id INTEGER,
                  selection_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referral_clicks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referral_code TEXT,
                  referrer_id INTEGER,
                  ip_address TEXT,
                  clicked_at TEXT,
                  is_converted INTEGER DEFAULT 0)''')
    
    conn.commit()
    
    # Add ip_address column if not exists
    c.execute("PRAGMA table_info(users)")
    cols = [col[1] for col in c.fetchall()]
    if 'ip_address' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN ip_address TEXT")
        conn.commit()
    
    # Migrate old referred_by (text) to referred_by_id
    if 'referred_by' in cols and 'referred_by_id' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN referred_by_id INTEGER")
        c.execute("SELECT id, referred_by FROM users WHERE referred_by IS NOT NULL AND referred_by != ''")
        rows = c.fetchall()
        for uid, ref_code in rows:
            c.execute("SELECT id FROM users WHERE referral_code = ?", (ref_code,))
            ref_user = c.fetchone()
            if ref_user:
                c.execute("UPDATE users SET referred_by_id = ? WHERE id = ?", (ref_user[0], uid))
        conn.commit()
    
    # Add repair categories if empty
    c.execute("SELECT COUNT(*) FROM repair_categories")
    if c.fetchone()[0] == 0:
        categories = [
            ("🔋 Charging not working", "Phone not charging, battery or port issue"),
            ("📱 Broken Screen", "Display cracked, touch not working"),
            ("🔊 No sound", "Speaker or headphone jack issue"),
            ("🐌 Phone hanging", "Slow performance, frequent freezing"),
            ("⚡ Battery drains fast", "Battery health degraded"),
            ("📶 WiFi/Bluetooth not working", "Connectivity issues"),
            ("📷 Camera not working", "Black screen or crash"),
            ("🔥 Phone overheating", "Overheating during use or charging")
        ]
        for cat, desc in categories:
            c.execute("INSERT INTO repair_categories (category_name, description) VALUES (?,?)", (cat, desc))
        conn.commit()
    
    conn.close()

init_db()

# ========== HELPER FUNCTIONS ==========
def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def add_notification(user_id, message):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)",
              (user_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_notifications(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC", (user_id,))
    notifs = c.fetchall()
    conn.close()
    return notifs

def mark_notification_read(notif_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()

def get_real_ip():
    try:
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            forwarded = st.context.headers.get('X-Forwarded-For')
            if forwarded:
                return forwarded.split(',')[0].strip()
        ip = requests.get('https://api.ipify.org', timeout=2).text
        return ip
    except:
        return "0.0.0.0"

def track_referral_click(referral_code, ip_address):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE referral_code = ?", (referral_code,))
    user = c.fetchone()
    if user:
        c.execute("INSERT INTO referral_clicks (referral_code, referrer_id, ip_address, clicked_at) VALUES (?,?,?,?)",
                  (referral_code, user[0], ip_address, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()

def get_click_stats(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referral_clicks WHERE referrer_id = ?", (user_id,))
    total_clicks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referral_history WHERE referrer_id = ?", (user_id,))
    total_conversions = c.fetchone()[0]
    conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
    conn.close()
    return total_clicks, total_conversions, conversion_rate

def get_social_share_urls(referral_link, referral_code, user_name):
    msg = f"📱 Ali Mobile Repair - Referral Program!\n\nMy referral code: {referral_code}\nClick to register: {referral_link}\n\n50 points per referral! 500 points = 500 PKR discount!"
    encoded = urllib.parse.quote(msg)
    return {
        "whatsapp": f"https://wa.me/?text={encoded}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={urllib.parse.quote(referral_link)}&quote={encoded}",
        "twitter": f"https://twitter.com/intent/tweet?text={encoded}&url={urllib.parse.quote(referral_link)}",
        "telegram": f"https://t.me/share/url?url={urllib.parse.quote(referral_link)}&text={encoded}",
    }

def normalize_csv_columns(df):
    mapping = {'نام': 'name', 'موبائل': 'mobile', 'ریفرل کوڈ': 'referral_code', 'پوائنٹس': 'points', 'ریفرڈ بذریعہ': 'referred_by', 'تاریخ': 'join_date'}
    df.rename(columns=mapping, inplace=True)
    return df

def delete_user_and_related(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM referral_history WHERE referrer_id = ? OR referred_user_id = ?", (user_id, user_id))
    c.execute("DELETE FROM discount_history WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM user_repair_selections WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM referral_clicks WHERE referrer_id = ?", (user_id,))
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def reset_user_password(user_id):
    new_pass = ''.join(random.choices(string.digits, k=6))
    hashed = hash_password(new_pass)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, user_id))
    conn.commit()
    conn.close()
    return new_pass

# ========== SESSION STATE ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_mobile = None
    st.session_state.user_name = None
    st.session_state.user_code = None
if 'page' not in st.session_state:
    st.session_state.page = "Home"
if 'registration_success' not in st.session_state:
    st.session_state.registration_success = False
if 'delete_confirm' not in st.session_state:
    st.session_state.delete_confirm = {}  # store user_id -> confirm state

# ========== REFERRAL TRACKING ==========
query_params = st.query_params
if 'ref' in query_params:
    ref_code = query_params['ref']
    ip = get_real_ip()
    track_referral_click(ref_code, ip)

# ========== TOP HEADER ==========
st.markdown("""
<div class="top-header">
    <h1>📱 Ali Mobiles Repairing</h1>
    <p>Ali Laal Road, Layyah | 📞 03006762827</p>
    <p style="font-size:1rem; margin-top:5px;">⚡ Fast Repair | 💯 Genuine Parts | 🎁 Refer & Earn</p>
</div>
""", unsafe_allow_html=True)

# ========== TOP NAVIGATION ==========
nav_cols = st.columns([1, 2, 1])
with nav_cols[1]:
    menu_options = ["🏠 Home", "✨ New Registration", "🔐 Login", "🏆 Leaderboard", "🔧 Repair Categories"]
    if st.session_state.logged_in:
        menu_options += ["🏠 My Points", "📜 Referral History", "💰 Discount History", "📊 Click Analytics"]
    admin_secret_input = st.text_input("🔑 Admin Access", type="password", placeholder="Enter admin code", key="admin_secret_input")
    if admin_secret_input == ADMIN_SECRET:
        menu_options += ["👑 Admin Panel"]
    selected_page = st.selectbox("Navigate", menu_options, index=0, label_visibility="collapsed")

page_map = {
    "🏠 Home": "Home",
    "✨ New Registration": "Register",
    "🔐 Login": "Login",
    "🏠 My Points": "Dashboard",
    "🏆 Leaderboard": "Leaderboard",
    "📜 Referral History": "ReferralHistory",
    "💰 Discount History": "DiscountHistory",
    "📊 Click Analytics": "ClickAnalytics",
    "🔧 Repair Categories": "RepairCategories",
    "👑 Admin Panel": "AdminPanel"
}
st.session_state.page = page_map.get(selected_page, "Home")

# ========== NOTIFICATIONS ==========
if st.session_state.logged_in:
    notifs = get_notifications(st.session_state.user_id)
    if notifs:
        with st.expander(f"🔔 You have {len(notifs)} new notification(s)"):
            for n in notifs:
                st.markdown(f'<div class="notification">📢 {n[2]}</div>', unsafe_allow_html=True)
                mark_notification_read(n[0])

# ========== PAGE RENDER ==========
if st.session_state.page == "Home":
    if not st.session_state.logged_in:
        st.markdown('<div class="gradient-card"><h2>✨ Welcome to Ali Mobile Repair</h2><p>Join our referral program and earn discounts on mobile repairs!</p></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="card"><h3>📝 New Customer?</h3><p>Create an account in seconds.</p></div>', unsafe_allow_html=True)
            if st.button("➡️ Register Now", key="home_reg_btn", use_container_width=True):
    st.session_state.page = "Register"
    st.rerun()
        with col2:
            st.markdown('<div class="card"><h3>🔐 Already a member?</h3><p>Login to see your points and referral link.</p></div>', unsafe_allow_html=True)
            if st.button("➡️ Login", key="home_login_btn", use_container_width=True):
    st.session_state.page = "Login"
    st.rerun()
        st.markdown("""
        <div class="card">
            <h3>📍 Our Services</h3>
            <ul>
                <li>🔧 Screen Replacement (All Models)</li>
                <li>🔋 Battery Replacement</li>
                <li>⚡ Charging Port Repair</li>
                <li>📶 Software Issues / FRP Unlock</li>
                <li>📷 Camera Repair</li>
                <li>🎧 Audio / Speaker Fix</li>
            </ul>
            <p><strong>Same Day Service | Warranty on Repairs</strong></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="gradient-card"><h2>🎉 Welcome back, {st.session_state.user_name}!</h2><p>Your referral program dashboard</p></div>', unsafe_allow_html=True)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT points, referral_code FROM users WHERE id=?", (st.session_state.user_id,))
        user_data = c.fetchone()
        conn.close()
        if user_data:
            points, code = user_data
            discount = points * 1
            st.markdown(f'<div class="metric-card"><h3>⭐ Your Points: {points}</h3><h4>💰 Discount Available: {discount} PKR</h4></div>', unsafe_allow_html=True)
            st.info(f"🔑 Your Referral Code: **{code}**")
            if st.button("📋 Go to My Dashboard", use_container_width=True):
                st.session_state.page = "Dashboard"
                st.rerun()
        st.markdown("---")
        st.markdown("### 📢 Quick Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Share Referral Link", use_container_width=True):
                st.session_state.page = "Dashboard"
                st.rerun()
        with col2:
            if st.button("🏆 View Leaderboard", use_container_width=True):
                st.session_state.page = "Leaderboard"
                st.rerun()

elif st.session_state.page == "Register":
    if st.session_state.logged_in:
        st.success("You are already logged in.")
        st.stop()
    
    st.session_state.registration_success = False
    
    with st.form("reg_form", clear_on_submit=False):
        st.subheader("✨ New Registration")
        name = st.text_input("Full Name")
        mobile = st.text_input("Mobile Number")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        ref_code = st.text_input("Referral Code (optional)")
        submitted = st.form_submit_button("Register", use_container_width=True)
        
        if submitted:
            if not name or not mobile or not password:
                st.error("Please fill all required fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif len(password) < 4:
                st.error("Password must be at least 4 characters.")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
                if c.fetchone():
                    st.error("Mobile number already registered.")
                else:
                    new_code = generate_code()
                    hashed = hash_password(password)
                    referrer_id = None
                    # Store IP address
                    user_ip = get_real_ip()
                    if ref_code:
                        c.execute("SELECT id, points FROM users WHERE referral_code=?", (ref_code,))
                        ref_user = c.fetchone()
                        if ref_user:
                            referrer_id = ref_user[0]
                            c.execute("UPDATE users SET points = points + 50 WHERE id=?", (ref_user[0],))
                            conn.commit()
                            c.execute("UPDATE referral_clicks SET is_converted = 1 WHERE referral_code = ? AND is_converted = 0 ORDER BY clicked_at DESC LIMIT 1", (ref_code,))
                            conn.commit()
                            add_notification(ref_user[0], f"🎉 New user {name} registered using your code! +50 points.")
                            st.success("Referrer got 50 points!")
                        else:
                            st.warning("Invalid referral code.")
                    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by_id, join_date, ip_address) VALUES (?,?,?,?,?,?,?,?)",
                              (name, mobile, hashed, new_code, 0, referrer_id, join_date, user_ip))
                    user_id = c.lastrowid
                    conn.commit()
                    if referrer_id:
                        c.execute("INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date) VALUES (?,?,?,?)",
                                  (referrer_id, user_id, 50, join_date))
                        conn.commit()
                    conn.close()
                    st.success(f"✅ Registration complete! Your referral code: **{new_code}**")
                    st.session_state.registration_success = True
    
    if st.session_state.registration_success:
        st.info("Please login now.")
        if st.button("🔐 Go to Login", use_container_width=True):
            st.session_state.page = "Login"
            st.session_state.registration_success = False
            st.rerun()

elif st.session_state.page == "Login":
    if st.session_state.logged_in:
        st.success("Already logged in.")
        st.stop()
    with st.form("login_form"):
        st.subheader("🔐 Login")
        mobile = st.text_input("Mobile Number")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
            user = c.fetchone()
            conn.close()
            if user and user[3] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.user_mobile = user[2]
                st.session_state.user_name = user[1]
                st.session_state.user_code = user[4]
                st.success("Login successful!")
                st.session_state.page = "Home"
                st.rerun()
            else:
                st.error("Invalid mobile or password.")

elif st.session_state.page == "Dashboard":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, mobile, referral_code, points FROM users WHERE id=?", (st.session_state.user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        name, mobile, code, points = user
        discount = points * 1
        referral_link = f"https://alimobile-referral.streamlit.app/?ref={code}"
        total_clicks, total_conversions, conv_rate = get_click_stats(st.session_state.user_id)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👤 Name", name)
            st.metric("📱 Mobile", mobile)
            st.metric("⭐ Points", points)
        with col2:
            st.metric("🔑 Referral Code", code)
            st.metric("💰 Discount", f"{discount} PKR")
            st.metric("📈 Conversion Rate", f"{conv_rate:.1f}%")
        st.markdown("---")
        st.subheader("📤 Your Referral Link")
        st.code(referral_link)
        st.markdown("### Share on Social Media")
        urls = get_social_share_urls(referral_link, code, name)
        cols = st.columns(4)
        for idx, (platform, url) in enumerate(urls.items()):
            with cols[idx]:
                st.markdown(f'<a href="{url}" target="_blank" class="social-share-btn {platform}" style="display:block;">📱 {platform.capitalize()}</a>', unsafe_allow_html=True)
        if points >= 500:
            if st.button("🎁 Claim Discount", use_container_width=True):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO discount_history (user_id, points_used, discount_amount, claim_date, status) VALUES (?,?,?,?,?)",
                          (st.session_state.user_id, points, discount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "claimed"))
                c.execute("UPDATE users SET points = 0 WHERE id=?", (st.session_state.user_id,))
                conn.commit()
                conn.close()
                st.success(f"🎉 You claimed {discount} PKR discount! Show your code at shop.")
                st.rerun()
        else:
            need = 500 - points
            st.info(f"Need {need} more points (that's {need} PKR discount remaining).")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.user_mobile = None
            st.session_state.user_name = None
            st.session_state.user_code = None
            st.session_state.page = "Home"
            st.rerun()

elif st.session_state.page == "Leaderboard":
    st.subheader("🏆 Top Referrers")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, points, referral_code FROM users ORDER BY points DESC LIMIT 10")
    top = c.fetchall()
    conn.close()
    if top:
        for i, u in enumerate(top, 1):
            col1, col2, col3 = st.columns([1,3,2])
            with col1:
                if i == 1: st.markdown("🏆 **1st**")
                elif i == 2: st.markdown("🥈 **2nd**")
                elif i == 3: st.markdown("🥉 **3rd**")
                else: st.write(f"**{i}th**")
            with col2: st.write(u[0])
            with col3: st.write(f"⭐ {u[1]} points")
        st.caption("50 points per referral | 500 points = 500 PKR discount")
    else:
        st.info("No users yet.")

elif st.session_state.page == "ReferralHistory":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    st.subheader("📜 Your Referral History")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""SELECT u.name, rh.points_earned, rh.referral_date 
                 FROM referral_history rh 
                 JOIN users u ON rh.referred_user_id = u.id 
                 WHERE rh.referrer_id = ? 
                 ORDER BY rh.referral_date DESC""", (st.session_state.user_id,))
    hist = c.fetchall()
    conn.close()
    if hist:
        for h in hist:
            st.markdown(f'<div class="referral-history-item">✅ {h[2][:10]} – {h[0]} registered → +{h[1]} points</div>', unsafe_allow_html=True)
    else:
        st.info("No referrals yet. Share your link!")

elif st.session_state.page == "DiscountHistory":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    st.subheader("💰 Your Discount History")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id = ? ORDER BY claim_date DESC", (st.session_state.user_id,))
    hist = c.fetchall()
    conn.close()
    if hist:
        for h in hist:
            st.markdown(f'<div class="discount-history-item">🎁 {h[2][:10]} – Used {h[0]} points → {h[1]:.0f} PKR discount</div>', unsafe_allow_html=True)
    else:
        st.info("No discounts claimed yet.")

elif st.session_state.page == "ClickAnalytics":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    st.subheader("📊 Click Analytics")
    total_clicks, total_conversions, conv_rate = get_click_stats(st.session_state.user_id)
    col1, col2, col3 = st.columns(3)
    col1.metric("👆 Total Clicks", total_clicks)
    col2.metric("✅ Registrations", total_conversions)
    col3.metric("📈 Conversion Rate", f"{conv_rate:.1f}%")
    st.divider()
    st.subheader("Recent Clicks")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT clicked_at, is_converted FROM referral_clicks WHERE referrer_id = ? ORDER BY clicked_at DESC LIMIT 20", (st.session_state.user_id,))
    recent = c.fetchall()
    conn.close()
    if recent:
        for r in recent:
            status = "✅ Converted" if r[1] else "⏳ Pending"
            st.write(f"📅 {r[0][:16]} → {status}")
    else:
        st.info("No clicks yet.")

elif st.session_state.page == "RepairCategories":
    st.subheader("🔧 Common Mobile Issues")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, category_name, description FROM repair_categories")
    cats = c.fetchall()
    conn.close()
    for cat in cats:
        with st.expander(f"🔧 {cat[1]}"):
            st.write(cat[2])
            if st.session_state.logged_in:
                if st.button(f"Report this issue", key=f"cat_{cat[0]}"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO user_repair_selections (user_id, category_id, selection_date) VALUES (?,?,?)",
                              (st.session_state.user_id, cat[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.success("Thank you! We'll contact you soon.")
    if st.session_state.logged_in:
        st.divider()
        st.subheader("Your Reported Issues")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""SELECT rc.category_name, us.selection_date 
                     FROM user_repair_selections us 
                     JOIN repair_categories rc ON us.category_id = rc.id 
                     WHERE us.user_id = ? 
                     ORDER BY us.selection_date DESC LIMIT 5""", (st.session_state.user_id,))
        issues = c.fetchall()
        conn.close()
        for iss in issues:
            st.write(f"📌 {iss[1][:10]}: {iss[0]}")

elif st.session_state.page == "AdminPanel":
    admin_pass = st.text_input("Admin Password", type="password")
    if admin_pass == ADMIN_PASSWORD:
        st.success("Admin Panel")
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Users", "📥 Export", "📤 CSV Upload", "📈 Bulk Points", "📊 Reports"])
        with tab1:
            search = st.text_input("Search by name or mobile")
            conn = get_db_connection()
            c = conn.cursor()
            if search:
                c.execute("SELECT id, name, mobile, referral_code, points, ip_address FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC", (f'%{search}%', f'%{search}%'))
            else:
                c.execute("SELECT id, name, mobile, referral_code, points, ip_address FROM users ORDER BY points DESC")
            users = c.fetchall()
            conn.close()
            for u in users:
                cols = st.columns([1,2,2,1,1,1,1,2])
                # id, name, mobile, referral_code, points, ip, actions
                cols[0].write(u[0])
                cols[1].write(u[1])
                cols[2].write(u[2])
                cols[3].write(u[3])
                cols[4].write(f"⭐ {u[4]}")
                cols[5].write(u[5] if u[5] else "N/A")
                # Reset password button
                with cols[6]:
                    if st.button("Reset Pwd", key=f"reset_{u[0]}"):
                        new_pass = reset_user_password(u[0])
                        st.success(f"New password for {u[1]}: {new_pass}")
                        st.rerun()
                # Delete button with confirmation using session state
                with cols[7]:
                    # Use a unique key for delete button
                    delete_key = f"del_{u[0]}"
                    if delete_key not in st.session_state.delete_confirm:
                        st.session_state.delete_confirm[delete_key] = False
                    if not st.session_state.delete_confirm[delete_key]:
                        if st.button("❌ Delete", key=delete_key):
                            st.session_state.delete_confirm[delete_key] = True
                            st.rerun()
                    else:
                        st.warning(f"Confirm delete {u[1]}?")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✅ Yes", key=f"confirm_yes_{u[0]}"):
                                delete_user_and_related(u[0])
                                st.success(f"User {u[1]} deleted.")
                                # Reset confirmation state
                                st.session_state.delete_confirm[delete_key] = False
                                st.rerun()
                        with col_b:
                            if st.button("❌ No", key=f"confirm_no_{u[0]}"):
                                st.session_state.delete_confirm[delete_key] = False
                                st.rerun()
                st.divider()
        with tab2:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT id, name, mobile, referral_code, points, referred_by_id, join_date, ip_address FROM users")
            data = c.fetchall()
            conn.close()
            if data:
                df = pd.DataFrame(data, columns=["ID","Name","Mobile","Referral Code","Points","Referred By ID","Join Date","IP Address"])
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, f"users_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        with tab3:
            uploaded = st.file_uploader("Upload CSV", type=["csv"])
            if uploaded:
                df = pd.read_csv(uploaded)
                df = normalize_csv_columns(df)
                if st.button("Merge Data"):
                    added = 0
                    skipped = 0
                    conn = get_db_connection()
                    c = conn.cursor()
                    for _, row in df.iterrows():
                        mobile = str(row.get("mobile", ""))
                        if not mobile:
                            continue
                        c.execute("SELECT id FROM users WHERE mobile = ?", (mobile,))
                        if not c.fetchone():
                            new_code = generate_code()
                            name = row.get("name", "")
                            points = int(row.get("points", 0))
                            hashed = hash_password("123456")
                            c.execute("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                                      (name, mobile, hashed, new_code, points, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            added += 1
                        else:
                            skipped += 1
                    conn.commit()
                    conn.close()
                    st.success(f"Added {added} new users. Skipped {skipped} duplicates.")
        with tab4:
            pts = st.number_input("Points to add to ALL users", min_value=0, step=50)
            if st.button("Add to All"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE users SET points = points + ?", (pts,))
                conn.commit()
                conn.close()
                st.success(f"Added {pts} points to all users.")
        with tab5:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""SELECT u.name, COUNT(rc.id) as clicks, SUM(rc.is_converted) as conv
                         FROM users u LEFT JOIN referral_clicks rc ON u.id = rc.referrer_id
                         GROUP BY u.id ORDER BY clicks DESC""")
            rep = c.fetchall()
            conn.close()
            for r in rep:
                rate = (r[2]/r[1]*100) if r[1] else 0
                st.write(f"📱 {r[0]} → Clicks: {r[1]}, Reg: {r[2]}, Rate: {rate:.1f}%")
    elif admin_pass:
        st.error("Wrong password")
