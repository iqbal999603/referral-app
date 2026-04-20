import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime
import pandas as pd
import urllib.parse

# ========== PAGE CONFIG ==========
st.set_page_config(page_title="Ali Mobile Repair - Referral System", page_icon="📱", layout="wide")

# ========== CUSTOM CSS ==========
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0a2b5e 0%, #1a4a8a 100%); }
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown p, .stMetric label { color: white !important; }
    .card, .metric-card, .referral-history-item, .discount-history-item, .notification {
        background: white; color: #333; padding: 15px; border-radius: 10px; margin: 10px 0;
    }
    .gradient-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 20px; border-radius: 15px;
    }
    .stButton button {
        background: linear-gradient(45deg, #ff9f43, #ff6b6b);
        border: none; color: white; border-radius: 40px; font-weight: bold;
    }
    .whatsapp { background: #25D366; }
    .facebook { background: #1877F2; }
    .twitter { background: #1DA1F2; }
    .telegram { background: #0088cc; }
    .social-share-btn {
        display: inline-block; padding: 8px 18px; margin: 5px; border-radius: 30px;
        text-decoration: none; color: white; font-weight: bold;
    }
    .top-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem 2rem; border-radius: 20px; margin-bottom: 2rem;
        color: white; text-align: center;
    }
</style>
""", unsafe_allow_html=True)
/* Forcefully change background of ALL cards on Home page */
div[class*="card"], div[class*="green-card"], div[class*="custom-card"] {
    background: #d4eaff !important;
    color: #333 !important;
}

# ========== SECRETS ==========
try:
    ADMIN_SECRET = st.secrets["ADMIN_SECRET"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    ADMIN_SECRET = "Admin@51214725"
    ADMIN_PASSWORD = "Admin51214725"
    
# ========== DATABASE ==========
def get_db_connection():
    conn = sqlite3.connect('referral.db', timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
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
        
        c.execute("PRAGMA table_info(users)")
        cols = [col[1] for col in c.fetchall()]
        if 'ip_address' not in cols:
            c.execute("ALTER TABLE users ADD COLUMN ip_address TEXT")
            conn.commit()
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

init_db()

# ========== HELPER FUNCTIONS ==========
def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def add_notification(user_id, message):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)",
                  (user_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

def get_notifications(user_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, message FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC", (user_id,))
        return c.fetchall()

def mark_notifications_read(user_id, notif_ids):
    if not notif_ids:
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        placeholders = ','.join(['?'] * len(notif_ids))
        c.execute(f"UPDATE notifications SET is_read = 1 WHERE user_id = ? AND id IN ({placeholders})", [user_id] + notif_ids)
        conn.commit()

def get_real_ip():
    return "unknown"

def track_referral_click(referral_code, ip_address):
    if ip_address == "unknown":
        return
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE referral_code = ?", (referral_code,))
        user = c.fetchone()
        if user:
            c.execute("INSERT INTO referral_clicks (referral_code, referrer_id, ip_address, clicked_at) VALUES (?,?,?,?)",
                      (referral_code, user[0], ip_address, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()

def get_click_stats(user_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM referral_clicks WHERE referrer_id = ?", (user_id,))
        total_clicks = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM referral_history WHERE referrer_id = ?", (user_id,))
        total_conversions = c.fetchone()[0]
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        return total_clicks, total_conversions, conversion_rate

def get_social_share_urls(referral_link, referral_code, user_name):
    msg = f"📱 Ali Mobile Repair - Referral Program!\n\nMy referral code: {referral_code}\nClick to register: {referral_link}\n\n50 points per referral! 500 points = 500 PKR discount!"
    encoded = urllib.parse.quote(msg)
    encoded_link = urllib.parse.quote(referral_link)
    return {
        "whatsapp": f"https://wa.me/?text={encoded}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={encoded_link}",
        "twitter": f"https://twitter.com/intent/tweet?text={encoded}",
        "telegram": f"https://t.me/share/url?url={encoded_link}&text={encoded}",
    }

def normalize_csv_columns(df):
    mapping = {'نام': 'name', 'موبائل': 'mobile', 'ریفرل کوڈ': 'referral_code', 'پوائنٹس': 'points', 'ریفرڈ بذریعہ': 'referred_by', 'تاریخ': 'join_date'}
    df.rename(columns=mapping, inplace=True)
    return df

def delete_user_and_related(user_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM referral_history WHERE referrer_id = ? OR referred_user_id = ?", (user_id, user_id))
        c.execute("DELETE FROM discount_history WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM user_repair_selections WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM referral_clicks WHERE referrer_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

def reset_user_password(user_id):
    new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed = hash_password(new_pass)
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        name = c.fetchone()[0]
        c.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, user_id))
        conn.commit()
    add_notification(user_id, f"🔐 Your password has been reset by admin. New password: {new_pass}")
    return new_pass, name

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
if 'repair_reported' not in st.session_state:
    st.session_state.repair_reported = set()

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

def on_nav_change():
    st.session_state.page = page_map.get(st.session_state.nav_select, "Home")

nav_cols = st.columns([1, 2, 1])
with nav_cols[1]:
    menu_options = ["🏠 Home", "✨ New Registration", "🔐 Login", "🏆 Leaderboard", "🔧 Repair Categories"]
    if st.session_state.logged_in:
        menu_options += ["🏠 My Points", "📜 Referral History", "💰 Discount History", "📊 Click Analytics"]
    admin_secret_input = st.text_input("WellCome", type="password", placeholder="To Login or Register, Use The Dropdown Box Below:", key="admin_secret_input")
    if admin_secret_input == ADMIN_SECRET:
        menu_options += ["👑 Admin Panel"]
    
    selected_page = st.selectbox(
        "Navigate", 
        menu_options, 
        index=0, 
        label_visibility="collapsed",
        key="nav_select",
        on_change=on_nav_change
    )
    
    if 'page' not in st.session_state or st.session_state.page == "Home":
        st.session_state.page = page_map.get(selected_page, "Home")

# ========== NOTIFICATIONS ==========
if st.session_state.logged_in:
    notifs = get_notifications(st.session_state.user_id)
    if notifs:
        notif_ids = [n[0] for n in notifs]
        with st.expander(f"🔔 You have {len(notifs)} new notification(s)"):
            for n in notifs:
                st.markdown(f'<div class="notification">📢 {n[1]}</div>', unsafe_allow_html=True)
        mark_notifications_read(st.session_state.user_id, notif_ids)

# ========== PAGE RENDER ==========
if st.session_state.page == "Home":
    if not st.session_state.logged_in:
        st.markdown('<div class="gradient-card"><h2>✨ Welcome to Ali Mobile Repair</h2><p>Join our referral program and earn discounts on mobile repairs!</p></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="card"><h3>📝 New Customer?</h3><p>Create an account in seconds.</p></div>', unsafe_allow_html=True)
            if st.button("➡️ Register Now", use_container_width=True):
                st.session_state.page = "Register"
                st.rerun()
        with col2:
            st.markdown('<div class="card"><h3>🔐 Already a member?</h3><p>Login to see your points and referral link.</p></div>', unsafe_allow_html=True)
            if st.button("➡️ Login", use_container_width=True):
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
            <p><strong>Same Day Service</strong></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="gradient-card"><h2>🎉 Welcome back, {st.session_state.user_name}!</h2><p>Your referral program dashboard</p></div>', unsafe_allow_html=True)
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT points, referral_code FROM users WHERE id=?", (st.session_state.user_id,))
            user_data = c.fetchone()
        if user_data:
            points, code = user_data
            discount = min(points, 500)
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
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
                    if c.fetchone():
                        st.error("Mobile number already registered.")
                        st.stop()
                
                new_code = generate_code()
                hashed = hash_password(password)
                referrer_id = None
                user_ip = get_real_ip()
                join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if ref_code:
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute("SELECT id FROM users WHERE referral_code=?", (ref_code,))
                        ref_user = c.fetchone()
                        if ref_user:
                            referrer_id = ref_user[0]
                            c.execute("UPDATE users SET points = points + 50 WHERE id=?", (referrer_id,))
                            c.execute("""INSERT INTO referral_clicks 
                                         (referral_code, referrer_id, ip_address, clicked_at, is_converted) 
                                         VALUES (?,?,?,?,?)""",
                                      (ref_code, referrer_id, user_ip, join_date, 1))
                            conn.commit()
                            add_notification(referrer_id, f"🎉 New user {name} registered using your code! +50 points.")
                            st.success("Referrer got 50 points!")
                        else:
                            st.warning("Invalid referral code.")
                
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("""INSERT INTO users 
                                 (name, mobile, password, referral_code, points, referred_by_id, join_date, ip_address) 
                                 VALUES (?,?,?,?,?,?,?,?)""",
                              (name, mobile, hashed, new_code, 0, referrer_id, join_date, user_ip))
                    user_id = c.lastrowid
                    conn.commit()
                
                if referrer_id:
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute("""INSERT INTO referral_history 
                                     (referrer_id, referred_user_id, points_earned, referral_date) 
                                     VALUES (?,?,?,?)""",
                                  (referrer_id, user_id, 50, join_date))
                        conn.commit()
                
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
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
                user = c.fetchone()
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
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name, mobile, referral_code, points FROM users WHERE id=?", (st.session_state.user_id,))
        user = c.fetchone()
    if user:
        name, mobile, code, points = user
        discount = min(points, 500)
        host = st.query_params.get("host", "alimobile-referral.streamlit.app")
        referral_link = f"https://{host}/?ref={code}"
        total_clicks, total_conversions, conv_rate = get_click_stats(st.session_state.user_id)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👤 Name", name)
            st.metric("📱 Mobile", mobile)
            st.metric("⭐ Points", points)
        with col2:
            st.metric("🔑 Referral Code", code)
            st.metric("💰 Discount Available", f"{discount} PKR")
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
                with get_db_connection() as conn:
                    c = conn.cursor()
                    points_to_use = 500
                    discount_amount = 500.0
                    c.execute("INSERT INTO discount_history (user_id, points_used, discount_amount, claim_date, status) VALUES (?,?,?,?,?)",
                              (st.session_state.user_id, points_to_use, discount_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "claimed"))
                    c.execute("UPDATE users SET points = points - ? WHERE id=?", (points_to_use, st.session_state.user_id))
                    conn.commit()
                add_notification(st.session_state.user_id, f"🎁 You claimed 500 PKR discount! Show this at shop.")
                st.success(f"🎉 You claimed {discount_amount} PKR discount! Show your code at shop.")
                st.rerun()
        else:
            need = 500 - points
            st.info(f"Need {need} more points to claim 500 PKR discount.")
        if st.button("🚪 Logout", use_container_width=True):
            for key in ['logged_in', 'user_id', 'user_mobile', 'user_name', 'user_code']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.page = "Home"
            st.rerun()

elif st.session_state.page == "Leaderboard":
    st.subheader("🏆 Top Referrers")
    with get_db_connection() as conn:
        c = conn.cursor()
        # Join date bhi select kar rahe hain
        c.execute("SELECT name, points, referral_code, join_date FROM users ORDER BY points DESC LIMIT 20")
        top = c.fetchall()
    if top:
        for i, u in enumerate(top[:10], 1):
            col1, col2, col3, col4 = st.columns([1, 3, 2, 3])
            with col1:
                if i == 1: st.markdown("🏆 **1st**")
                elif i == 2: st.markdown("🥈 **2nd**")
                elif i == 3: st.markdown("🥉 **3rd**")
                else: st.write(f"**{i}th**")
            with col2:
                st.write(u[0])  # name
            with col3:
                st.write(f"⭐ {u[1]} points")
            with col4:
                # Full datetime show karein (YYYY-MM-DD HH:MM:SS)
                if u[3]:
                    st.write(f"📅 {u[3]}")
                else:
                    st.write("📅 No date")
        if len(top) > 10:
            with st.expander("Show more"):
                for i, u in enumerate(top[10:], 11):
                    st.write(f"{i}. {u[0]} - ⭐ {u[1]} points - Joined: {u[3] if u[3] else '?'}")
        st.caption("50 points per referral | 500 points = 500 PKR discount")
    else:
        st.info("No users yet.")

elif st.session_state.page == "ReferralHistory":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    st.subheader("📜 Your Referral History")
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""SELECT u.name, rh.points_earned, rh.referral_date 
                     FROM referral_history rh 
                     JOIN users u ON rh.referred_user_id = u.id 
                     WHERE rh.referrer_id = ? 
                     ORDER BY rh.referral_date DESC""", (st.session_state.user_id,))
        hist = c.fetchall()
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
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id = ? ORDER BY claim_date DESC", (st.session_state.user_id,))
        hist = c.fetchall()
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
    st.subheader("Recent Clicks with Date & Time")
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT clicked_at, is_converted FROM referral_clicks WHERE referrer_id = ? ORDER BY clicked_at DESC LIMIT 20", (st.session_state.user_id,))
        recent = c.fetchall()
    if recent:
        for r in recent:
            status = "✅ Converted" if r[1] else "⏳ Pending"
            st.write(f"📅 {r[0]} → {status}")
    else:
        st.info("No clicks yet.")

elif st.session_state.page == "RepairCategories":
    st.subheader("🔧 Common Mobile Issues")
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, category_name, description FROM repair_categories")
        cats = c.fetchall()
    for cat in cats:
        with st.expander(f"🔧 {cat[1]}"):
            st.write(cat[2])
            if st.session_state.logged_in:
                cat_key = f"{st.session_state.user_id}_{cat[0]}"
                if cat_key not in st.session_state.repair_reported:
                    if st.button(f"Report this issue", key=f"cat_{cat[0]}"):
                        with get_db_connection() as conn:
                            c = conn.cursor()
                            c.execute("INSERT INTO user_repair_selections (user_id, category_id, selection_date) VALUES (?,?,?)",
                                      (st.session_state.user_id, cat[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                        st.session_state.repair_reported.add(cat_key)
                        st.success("Thank you! We'll contact you soon.")
                else:
                    st.info("Already reported.")
    if st.session_state.logged_in:
        st.divider()
        st.subheader("Your Reported Issues")
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""SELECT rc.category_name, us.selection_date 
                         FROM user_repair_selections us 
                         JOIN repair_categories rc ON us.category_id = rc.id 
                         WHERE us.user_id = ? 
                         ORDER BY us.selection_date DESC LIMIT 5""", (st.session_state.user_id,))
            issues = c.fetchall()
        for iss in issues:
            st.write(f"📌 {iss[1][:10]}: {iss[0]}")

elif st.session_state.page == "AdminPanel":
    admin_pass = st.text_input("Admin Password", type="password")
    if admin_pass == ADMIN_PASSWORD:
        st.success("Admin Panel")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["👥 Users", "📥 Export", "📤 CSV Upload", "📈 Bulk Points", "📊 Reports", "🔧 Repair Reports"])
        
        with tab1:
            search = st.text_input("Search by name or mobile")
            with get_db_connection() as conn:
                c = conn.cursor()
                if search:
                    c.execute("SELECT id, name, mobile, referral_code, points, join_date, ip_address FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC", (f'%{search}%', f'%{search}%'))
                else:
                    c.execute("SELECT id, name, mobile, referral_code, points, join_date, ip_address FROM users ORDER BY points DESC")
                users = c.fetchall()
            for u in users:
                cols = st.columns([1,2,2,1,1,2,1,2])
                cols[0].write(u[0])
                cols[1].write(u[1])
                cols[2].write(u[2])
                cols[3].write(u[3])
                cols[4].write(f"⭐ {u[4]}")
                cols[5].write(u[5][:10] if u[5] else "N/A")  # Show date only
                cols[6].write(u[6] if u[6] else "N/A")
                with cols[7]:
                    confirm_state_key = f"delete_confirm_{u[0]}"
                    if confirm_state_key not in st.session_state:
                        st.session_state[confirm_state_key] = False
                    if not st.session_state[confirm_state_key]:
                        if st.button("Reset Pwd", key=f"reset_{u[0]}"):
                            new_pass, name = reset_user_password(u[0])
                            st.success(f"Password for {name} reset. New password: `{new_pass}`")
                            st.rerun()
                        if st.button("❌ Delete", key=f"del_{u[0]}"):
                            st.session_state[confirm_state_key] = True
                            st.rerun()
                    else:
                        st.warning(f"Confirm delete {u[1]}?")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✅ Yes", key=f"confirm_yes_{u[0]}"):
                                delete_user_and_related(u[0])
                                st.success(f"User {u[1]} deleted.")
                                del st.session_state[confirm_state_key]
                                st.rerun()
                        with col_b:
                            if st.button("❌ No", key=f"confirm_no_{u[0]}"):
                                del st.session_state[confirm_state_key]
                                st.rerun()
                st.divider()
        
        with tab2:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id, name, mobile, referral_code, points, referred_by_id, join_date, ip_address FROM users")
                data = c.fetchall()
            if data:
                df = pd.DataFrame(data, columns=["ID","Name","Mobile","Referral Code","Points","Referred By ID","Join Date","IP Address"])
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
        
        with tab3:
            uploaded = st.file_uploader("Upload CSV", type=["csv"])
            if uploaded:
                df = pd.read_csv(uploaded)
                df = normalize_csv_columns(df)
                if st.button("Merge Data"):
                    added = 0
                    skipped = 0
                    with get_db_connection() as conn:
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
                                temp_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                                hashed = hash_password(temp_pass)
                                join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                c.execute("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                                          (name, mobile, hashed, new_code, points, join_date))
                                added += 1
                            else:
                                skipped += 1
                        conn.commit()
                    st.success(f"Added {added} new users. Skipped {skipped} duplicates.")
        
        with tab4:
            pts = st.number_input("Points to add to ALL users", min_value=0, step=50)
            if st.button("Add to All"):
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("UPDATE users SET points = points + ?", (pts,))
                    conn.commit()
                st.success(f"Added {pts} points to all users.")
        
        with tab5:
            st.subheader("📊 Referral Clicks & Conversions with Timestamps")
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""SELECT u.name, rc.clicked_at, rc.is_converted 
                             FROM referral_clicks rc 
                             JOIN users u ON rc.referrer_id = u.id 
                             ORDER BY rc.clicked_at DESC""")
                clicks = c.fetchall()
            if clicks:
                for c in clicks:
                    status = "✅ Converted" if c[2] else "⏳ Pending"
                    st.write(f"📱 {c[0]} → {c[1]} → {status}")
            else:
                st.info("No referral clicks yet.")
        
        with tab6:
            st.subheader("🔧 User Reported Issues")
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""SELECT u.name, u.mobile, rc.category_name, us.selection_date 
                             FROM user_repair_selections us 
                             JOIN users u ON us.user_id = u.id 
                             JOIN repair_categories rc ON us.category_id = rc.id 
                             ORDER BY us.selection_date DESC""")
                reports = c.fetchall()
            if reports:
                for r in reports:
                    st.markdown(f"""
                    <div style="background:white; padding:10px; border-radius:10px; margin:5px 0; color:#333;">
                        <strong>{r[0]}</strong> ({r[1]})<br>
                        Issue: {r[2]}<br>
                        Date: {r[3][:16]}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No repair reports yet.")
    elif admin_pass:
        st.error("Wrong password")
        # ... aapka sara code (Home, Register, Login, AdminPanel, etc.) ...

# ========== FOOTER ==========
st.markdown("""
<style>
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        color: white;
        text-align: center;
        padding: 8px;
        font-size: 12px;
        z-index: 999;
        backdrop-filter: blur(5px);
    }
    .main .block-container {
        padding-bottom: 50px;
    }
</style>
<div class="footer">
    © 2026-2027 Ali Mobiles Repairing, Ali Laal Road, Layyah. All Rights Reserved.
</div>
""", unsafe_allow_html=True)
