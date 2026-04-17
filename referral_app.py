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

# ========== GET SECRETS FROM STREAMLIT CLOUD ==========
try:
    ADMIN_SECRET = st.secrets["ADMIN_SECRET"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    ADMIN_SECRET = "Admin@51214725"
    ADMIN_PASSWORD = "Admin51214725"

# Page setup
st.set_page_config(page_title="Ali Mobile Repair - Referral System", page_icon="📱", layout="centered")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        margin-bottom: 30px;
    }
    .notification {
        background: #e7f3ff;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .social-share-btn {
        display: inline-block;
        padding: 8px 15px;
        margin: 5px;
        border-radius: 30px;
        text-decoration: none;
        color: white;
        font-weight: bold;
        transition: 0.3s;
        text-align: center;
    }
    .whatsapp { background: #25D366; }
    .facebook { background: #1877F2; }
    .twitter { background: #1DA1F2; }
    .telegram { background: #0088cc; }
    .copy-btn { background: #6c757d; }
    .referral-history-item, .discount-history-item {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE SETUP (THREAD-SAFE) ====================
# Using st.cache_resource to maintain a single connection per session (thread-safe)
@st.cache_resource
def get_db_connection():
    """Returns a thread-safe SQLite connection. Connection is reused across reruns."""
    conn = sqlite3.connect('referral.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  mobile TEXT UNIQUE,
                  password TEXT,
                  referral_code TEXT UNIQUE,
                  points INTEGER DEFAULT 0,
                  referred_by_id INTEGER,
                  join_date TEXT)''')
    
    # Referral history table
    c.execute('''CREATE TABLE IF NOT EXISTS referral_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER,
                  referred_user_id INTEGER,
                  points_earned INTEGER,
                  referral_date TEXT)''')
    
    # Discount claim history table
    c.execute('''CREATE TABLE IF NOT EXISTS discount_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  points_used INTEGER,
                  discount_amount REAL,
                  claim_date TEXT,
                  status TEXT)''')
    
    # Notifications table
    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  message TEXT,
                  is_read INTEGER DEFAULT 0,
                  created_at TEXT)''')
    
    # Repair categories table
    c.execute('''CREATE TABLE IF NOT EXISTS repair_categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category_name TEXT,
                  description TEXT)''')
    
    # User repair selections table
    c.execute('''CREATE TABLE IF NOT EXISTS user_repair_selections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  category_id INTEGER,
                  selection_date TEXT)''')
    
    # Referral clicks tracking table (stores real IP)
    c.execute('''CREATE TABLE IF NOT EXISTS referral_clicks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referral_code TEXT,
                  referrer_id INTEGER,
                  ip_address TEXT,
                  clicked_at TEXT,
                  is_converted INTEGER DEFAULT 0)''')
    
    # Note: device_tracking table removed (IP-based device tracking is unreliable)
    
    conn.commit()
    
    # Migrate old referred_by (text) to referred_by_id (integer) if needed
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'referred_by' in columns and 'referred_by_id' not in columns:
        # Add new column
        c.execute("ALTER TABLE users ADD COLUMN referred_by_id INTEGER")
        # Migrate data: find user id from referral_code
        c.execute("SELECT id, referred_by FROM users WHERE referred_by IS NOT NULL AND referred_by != ''")
        rows = c.fetchall()
        for user_id, ref_code in rows:
            c.execute("SELECT id FROM users WHERE referral_code = ?", (ref_code,))
            ref_user = c.fetchone()
            if ref_user:
                c.execute("UPDATE users SET referred_by_id = ? WHERE id = ?", (ref_user[0], user_id))
        # Drop old column (optional, but we keep for backward compatibility; can be ignored)
        conn.commit()
    
    # Add default repair categories if empty
    c.execute("SELECT COUNT(*) FROM repair_categories")
    if c.fetchone()[0] == 0:
        categories = [
            ("چارجنگ نہیں ہوتی", "موبائل چارج نہیں ہو رہا، بیٹری یا چارجنگ پورٹ میں مسئلہ"),
            ("اسکرین ٹوٹی ہوئی", "ڈسپلے ٹوٹ گیا ہے، ٹچ کام نہیں کر رہا"),
            ("آواز نہیں آتی", "اسپیکر سے آواز نہیں آ رہی، ہینڈفری بھی کام نہیں کر رہا"),
            ("موبائل ہینگ ہے", "موبائل سست چل رہا ہے، بار بار رک جاتا ہے"),
            ("بیٹری جلدی ختم ہوتی ہے", "بیٹری بہت جلدی ڈرین ہو جاتی ہے"),
            ("وائی فائی / بلوٹوتھ نہیں چلتا", "وائی فائی آن نہیں ہوتا یا بلوٹوتھ کام نہیں کر رہا"),
            ("کیمرہ کام نہیں کرتا", "کیمرہ بلیک اسکرین دکھاتا ہے یا کریش ہوتا ہے"),
            ("موبائل گرم ہوتا ہے", "چارجنگ یا استعمال کے دوران بہت گرم ہو جاتا ہے"),
        ]
        for cat, desc in categories:
            c.execute("INSERT INTO repair_categories (category_name, description) VALUES (?,?)", (cat, desc))
        conn.commit()
    
    conn.close()

# Run DB initialization
init_db()

# ==================== HELPER FUNCTIONS ====================
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
    """Get real IP address from Streamlit Cloud headers or fallback to api.ipify.org"""
    try:
        # Try to get from Streamlit Cloud headers
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            forwarded = st.context.headers.get('X-Forwarded-For')
            if forwarded:
                return forwarded.split(',')[0].strip()
        # Fallback to external API
        ip = requests.get('https://api.ipify.org', timeout=2).text
        return ip
    except:
        return "0.0.0.0"  # Unknown IP

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
    message = f"📱 Ali Mobile Repair - Referral Program!\n\nMy referral code: {referral_code}\nClick to register: {referral_link}\n\n50 points per referral! 500 points = 500 PKR discount!"
    encoded_msg = urllib.parse.quote(message)
    urls = {
        "whatsapp": f"https://wa.me/?text={encoded_msg}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={urllib.parse.quote(referral_link)}&quote={encoded_msg}",
        "twitter": f"https://twitter.com/intent/tweet?text={encoded_msg}&url={urllib.parse.quote(referral_link)}",
        "telegram": f"https://t.me/share/url?url={urllib.parse.quote(referral_link)}&text={encoded_msg}",
    }
    return urls

def normalize_csv_columns(df):
    """Convert CSV columns from Urdu to English for compatibility"""
    column_mapping = {
        'نام': 'name',
        'موبائل': 'mobile',
        'ریفرل کوڈ': 'referral_code',
        'پوائنٹس': 'points',
        'ریفرڈ بذریعہ': 'referred_by',
        'تاریخ': 'join_date'
    }
    df.rename(columns=column_mapping, inplace=True)
    # Ensure required columns exist
    if 'mobile' not in df.columns and 'موبائل' in df.columns:
        df['mobile'] = df['موبائل']
    if 'name' not in df.columns and 'نام' in df.columns:
        df['name'] = df['نام']
    return df

# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_mobile = None
    st.session_state.user_name = None
    st.session_state.user_code = None

# ==================== REFERRAL TRACKING ====================
query_params = st.query_params
if 'ref' in query_params:
    ref_code = query_params['ref']
    ip_address = get_real_ip()
    track_referral_click(ref_code, ip_address)

# ==================== SIDEBAR ====================
st.sidebar.image("https://img.icons8.com/color/96/000000/smartphone.png", width=80)

admin_secret = st.sidebar.text_input("🔑 Admin Secret", type="password", placeholder="Admin Code")

if admin_secret == ADMIN_SECRET:
    menu = st.sidebar.radio("📌 Select Option", ["✨ New Registration", "🔐 Login", "🏠 My Points", 
                                                "🏆 Leaderboard", "📜 Referral History", "💰 Discount History",
                                                "📊 Click Analytics", "🔧 Repair Categories", "👑 Admin Panel"])
else:
    menu = st.sidebar.radio("📌 Select Option", ["✨ New Registration", "🔐 Login", "🏠 My Points",
                                                "🏆 Leaderboard", "🔧 Repair Categories"])

# Header (fixed HTML)
st.markdown('<div class="main-header"><h1>📱 Ali Mobiles Repairing</h1><p><h3>Ali Laal Road Layyah: 03006762827</h3></p><p><h2>Refer and get discount on mobile repair</h2></p></div>', unsafe_allow_html=True)

# ==================== REGISTRATION (WITHOUT DEVICE TRACKING) ====================
if menu == "✨ New Registration":
    if st.session_state.logged_in:
        st.success("You are already logged in.")
        st.stop()
    
    with st.form("register_form"):
        name = st.text_input("Full Name")
        mobile = st.text_input("Mobile Number")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        ref_code = st.text_input("Referral Code (optional)")
        submitted = st.form_submit_button("Register")
        
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
                c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
                if c.fetchone():
                    st.error("This mobile number is already registered.")
                else:
                    new_code = generate_code()
                    hashed_pass = hash_password(password)
                    
                    # Process referral
                    referrer_id = None
                    if ref_code:
                        c.execute("SELECT id, points, name FROM users WHERE referral_code=?", (ref_code,))
                        referrer = c.fetchone()
                        if referrer:
                            referrer_id = referrer[0]
                            c.execute("UPDATE users SET points = points + 50 WHERE referral_code=?", (ref_code,))
                            conn.commit()
                            # Mark click as converted
                            c.execute("UPDATE referral_clicks SET is_converted = 1 WHERE referral_code = ? AND is_converted = 0 ORDER BY clicked_at DESC LIMIT 1", (ref_code,))
                            conn.commit()
                            add_notification(referrer_id, f"🎉 Congratulations! {name} registered using your referral code. You earned 50 points.")
                            st.success("🎉 Your referrer got 50 points.")
                        else:
                            st.warning("Invalid referral code.")
                    
                    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by_id, join_date) VALUES (?,?,?,?,?,?,?)",
                              (name, mobile, hashed_pass, new_code, 0, referrer_id, join_date))
                    user_id = c.lastrowid
                    conn.commit()
                    
                    if referrer_id:
                        c.execute("INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date) VALUES (?,?,?,?)",
                                  (referrer_id, user_id, 50, join_date))
                        conn.commit()
                    
                    conn.close()
                    st.success(f"✅ Registration complete! Your referral code: **{new_code}**")
                    st.info("Please login now.")
    
# ==================== LOGIN ====================
elif menu == "🔐 Login":
    if st.session_state.logged_in:
        st.success("You are already logged in.")
        st.stop()
    
    with st.form("login_form"):
        mobile = st.text_input("Mobile Number")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
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
                st.rerun()
            else:
                st.error("Invalid mobile number or password.")

# ==================== DASHBOARD ====================
elif menu == "🏠 My Points":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    
    notifs = get_notifications(st.session_state.user_id)
    if notifs:
        with st.expander("📢 Notifications"):
            for notif in notifs:
                st.markdown(f'<div class="notification">🔔 {notif[2]}</div>', unsafe_allow_html=True)
                mark_notification_read(notif[0])
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (st.session_state.user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        name, mobile, code, points = user[1], user[2], user[4], user[5]
        discount = points * 1  # 1 point = 1 PKR
        referral_link = f"https://alimobile-referral.streamlit.app/?ref={code}"
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👤 Name", name)
            st.metric("📱 Mobile", mobile)
        with col2:
            st.metric("🔑 Referral Code", code)
            st.metric("⭐ Points", points)
        
        total_clicks, total_conversions, conversion_rate = get_click_stats(st.session_state.user_id)
        
        st.markdown("---")
        st.markdown("### 📊 Your Referral Link Performance")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("👆 Total Clicks", total_clicks)
        with col_b:
            st.metric("✅ Registrations", total_conversions)
        with col_c:
            st.metric("📈 Conversion Rate", f"{conversion_rate:.1f}%")
        
        st.markdown("---")
        st.markdown(f"### 💰 Discount Amount: **{discount:.2f} PKR**")
        
        st.subheader("📤 Your Referral Link")
        st.code(referral_link, language="text")
        
        st.markdown("### 🌐 Share on Social Media")
        social_urls = get_social_share_urls(referral_link, code, name)
        cols = st.columns(4)
        with cols[0]:
            st.markdown(f'<a href="{social_urls["whatsapp"]}" target="_blank" class="social-share-btn whatsapp" style="display:block;">📱 WhatsApp</a>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<a href="{social_urls["facebook"]}" target="_blank" class="social-share-btn facebook" style="display:block;">📘 Facebook</a>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<a href="{social_urls["twitter"]}" target="_blank" class="social-share-btn twitter" style="display:block;">🐦 Twitter</a>', unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f'<a href="{social_urls["telegram"]}" target="_blank" class="social-share-btn telegram" style="display:block;">📨 Telegram</a>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        if points >= 500:
            if st.button("🎁 Claim Discount"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO discount_history (user_id, points_used, discount_amount, claim_date, status) VALUES (?,?,?,?,?)",
                          (st.session_state.user_id, points, discount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "claimed"))
                c.execute("UPDATE users SET points = 0 WHERE id=?", (st.session_state.user_id,))
                conn.commit()
                conn.close()
                st.success(f"🎉 You claimed {discount:.2f} PKR discount! Show your code at the shop.")
                st.rerun()
        else:
            need = 500 - points
            st.info(f"📈 Need {need} more points (that's {need:.2f} PKR discount remaining).")
        
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.user_mobile = None
            st.session_state.user_name = None
            st.session_state.user_code = None
            st.rerun()

# ==================== LEADERBOARD ====================
elif menu == "🏆 Leaderboard":
    st.subheader("🏆 Top Referrers")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, points, referral_code FROM users ORDER BY points DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    if top_users:
        for i, user in enumerate(top_users, 1):
            col1, col2, col3 = st.columns([1, 3, 2])
            with col1:
                if i == 1:
                    st.markdown("🏆 **1st**")
                elif i == 2:
                    st.markdown("🥈 **2nd**")
                elif i == 3:
                    st.markdown("🥉 **3rd**")
                else:
                    st.write(f"**{i}th**")
            with col2:
                st.write(user[0])
            with col3:
                st.write(f"⭐ {user[1]} points")
        st.divider()
        st.caption("50 points per referral | 500 points = 500 PKR discount")
    else:
        st.info("No users yet.")

# ==================== REFERRAL HISTORY ====================
elif menu == "📜 Referral History":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    
    st.subheader("📜 Your Referral History")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""SELECT rh.id, u.name, rh.points_earned, rh.referral_date 
                 FROM referral_history rh 
                 JOIN users u ON rh.referred_user_id = u.id 
                 WHERE rh.referrer_id = ? 
                 ORDER BY rh.referral_date DESC""", (st.session_state.user_id,))
    history = c.fetchall()
    conn.close()
    
    if history:
        for h in history:
            st.markdown(f'<div class="referral-history-item">✅ {h[3][:10]} {h[1]} registered → +{h[2]} points</div>', unsafe_allow_html=True)
    else:
        st.info("No referrals yet. Share your link!")

# ==================== DISCOUNT HISTORY ====================
elif menu == "💰 Discount History":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    
    st.subheader("💰 Your Discount History")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id = ? ORDER BY claim_date DESC", (st.session_state.user_id,))
    history = c.fetchall()
    conn.close()
    
    if history:
        for h in history:
            st.markdown(f'<div class="discount-history-item">🎁 {h[2][:10]} used {h[0]} points → {h[1]:.2f} PKR discount</div>', unsafe_allow_html=True)
    else:
        st.info("No discounts claimed yet.")

# ==================== CLICK ANALYTICS ====================
elif menu == "📊 Click Analytics":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
        st.stop()
    
    st.subheader("📊 Referral Link Detailed Report")
    total_clicks, total_conversions, conversion_rate = get_click_stats(st.session_state.user_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👆 Total Clicks", total_clicks)
    with col2:
        st.metric("✅ Successful Registrations", total_conversions)
    with col3:
        st.metric("📈 Conversion Rate", f"{conversion_rate:.1f}%")
    
    st.divider()
    st.subheader("📋 Recent Clicks")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT clicked_at, is_converted FROM referral_clicks WHERE referrer_id = ? ORDER BY clicked_at DESC LIMIT 20", (st.session_state.user_id,))
    recent_clicks = c.fetchall()
    conn.close()
    
    if recent_clicks:
        for click in recent_clicks:
            status = "✅ Converted" if click[1] == 1 else "⏳ Pending"
            st.write(f"📅 {click[0][:16]} → {status}")
    else:
        st.info("No one has clicked your link yet.")

# ==================== REPAIR CATEGORIES ====================
elif menu == "🔧 Repair Categories":
    st.subheader("🔧 Common Mobile Issues")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, category_name, description FROM repair_categories")
    categories = c.fetchall()
    conn.close()
    
    for cat in categories:
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
                    st.success(f"You reported '{cat[1]}'. We will contact you soon.")
    
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
        user_issues = c.fetchall()
        conn.close()
        if user_issues:
            for issue in user_issues:
                st.write(f"📌 {issue[1][:10]}: {issue[0]}")
        else:
            st.info("You haven't reported any issues yet.")

# ==================== ADMIN PANEL ====================
elif menu == "👑 Admin Panel":
    admin_pass = st.text_input("Admin Password", type="password")
    
    if admin_pass == ADMIN_PASSWORD:
        st.success("Welcome to Admin Panel")
        
        admin_tab = st.tabs(["📊 Users", "📥 Export Data", "📤 CSV Upload", "📈 Bulk Points", "🔧 Repair Reports", "📊 Clicks Report"])
        
        # Tab 0: Users
        with admin_tab[0]:
            search = st.text_input("🔍 Search by name or mobile")
            conn = get_db_connection()
            c = conn.cursor()
            if search:
                c.execute("SELECT id, name, mobile, referral_code, points FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC", 
                          (f'%{search}%', f'%{search}%'))
            else:
                c.execute("SELECT id, name, mobile, referral_code, points FROM users ORDER BY points DESC")
            users = c.fetchall()
            conn.close()
            
            for user in users:
                col1, col2, col3, col4, col5, col6 = st.columns([1,2,2,1,1,2])
                with col1:
                    st.write(user[0])
                with col2:
                    st.write(user[1])
                with col3:
                    st.write(user[2])
                with col4:
                    st.write(user[3])
                with col5:
                    st.write(f"⭐ {user[4]}")
                with col6:
                    deduct = st.number_input("Deduct", min_value=0, max_value=user[4], step=10, key=f"deduct_{user[0]}")
                    if st.button("Deduct", key=f"btn_{user[0]}"):
                        new_points = user[4] - deduct
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user[0]))
                        conn.commit()
                        conn.close()
                        add_notification(user[0], f"🔄 {deduct} points deducted. Current points: {new_points}")
                        st.success(f"{user[1]}'s points updated to {new_points}")
                        st.rerun()
                st.divider()
        
        # Tab 1: Export Data
        with admin_tab[1]:
            st.subheader("📥 Export Data")
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT id, name, mobile, referral_code, points, referred_by_id, join_date FROM users")
            data = c.fetchall()
            conn.close()
            if data:
                df = pd.DataFrame(data, columns=["ID", "Name", "Mobile", "Referral Code", "Points", "Referred By ID", "Join Date"])
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, f"users_data_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
                st.info(f"📊 Total users: {len(data)}")
            else:
                st.info("No data")
        
        # Tab 2: CSV Upload (with backward compatibility)
        with admin_tab[2]:
            st.subheader("📤 Upload CSV (Merge Data)")
            st.warning("⚠️ Only new users will be added. Existing users (by mobile) will be skipped.")
            
            uploaded_file = st.file_uploader("Select CSV file (exported from this system)", type=["csv"])
            
            if uploaded_file is not None:
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    df_upload = normalize_csv_columns(df_upload)  # Handle Urdu column names
                    st.write("Preview:", df_upload.head())
                    st.write(f"Total records: {len(df_upload)}")
                    
                    if st.button("🔄 Merge Data"):
                        new_users_added = 0
                        duplicate_skipped = 0
                        conn = get_db_connection()
                        c = conn.cursor()
                        
                        for _, row in df_upload.iterrows():
                            mobile = str(row.get("mobile", ""))
                            if not mobile:
                                continue
                            
                            c.execute("SELECT id FROM users WHERE mobile = ?", (mobile,))
                            if not c.fetchone():
                                new_code = generate_code()
                                name = row.get("name", "")
                                points = int(row.get("points", 0))
                                referred_by = row.get("referred_by", None)
                                # Try to find referrer ID from code
                                referrer_id = None
                                if referred_by:
                                    c.execute("SELECT id FROM users WHERE referral_code = ?", (referred_by,))
                                    ref_user = c.fetchone()
                                    if ref_user:
                                        referrer_id = ref_user[0]
                                
                                # Default password if not present
                                hashed_pass = hash_password("123456")
                                if "password" in row:
                                    hashed_pass = hash_password(str(row["password"]))
                                
                                join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                try:
                                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by_id, join_date) VALUES (?,?,?,?,?,?,?)",
                                              (name, mobile, hashed_pass, new_code, points, referrer_id, join_date))
                                    new_users_added += 1
                                except sqlite3.IntegrityError:
                                    duplicate_skipped += 1
                            else:
                                duplicate_skipped += 1
                        
                        conn.commit()
                        conn.close()
                        st.success(f"✅ {new_users_added} new users added.")
                        if duplicate_skipped > 0:
                            st.info(f"⚠️ {duplicate_skipped} duplicates (mobile already exists) skipped.")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
        
        # Tab 3: Bulk Points
        with admin_tab[3]:
            st.subheader("📈 Bulk Points Add")
            points_to_add = st.number_input("Points to add to ALL users", min_value=0, step=50)
            if st.button("Add to All"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE users SET points = points + ?", (points_to_add,))
                conn.commit()
                conn.close()
                st.success(f"Added {points_to_add} points to all users!")
        
        # Tab 4: Repair Reports
        with admin_tab[4]:
            st.subheader("🔧 User Reported Issues")
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""SELECT u.name, u.mobile, rc.category_name, us.selection_date 
                         FROM user_repair_selections us 
                         JOIN users u ON us.user_id = u.id 
                         JOIN repair_categories rc ON us.category_id = rc.id 
                         ORDER BY us.selection_date DESC LIMIT 20""")
            reports = c.fetchall()
            conn.close()
            if reports:
                for r in reports:
                    st.write(f"📱 {r[0]} ({r[1]}) → {r[2]} - {r[3][:10]}")
            else:
                st.info("No reports")
        
        # Tab 5: Clicks Report
        with admin_tab[5]:
            st.subheader("📊 All Users Clicks Report")
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""SELECT u.name, u.mobile, u.referral_code, 
                                COUNT(rc.id) as total_clicks,
                                SUM(CASE WHEN rc.is_converted = 1 THEN 1 ELSE 0 END) as conversions
                         FROM users u
                         LEFT JOIN referral_clicks rc ON u.id = rc.referrer_id
                         GROUP BY u.id
                         ORDER BY total_clicks DESC""")
            click_data = c.fetchall()
            conn.close()
            if click_data:
                for cd in click_data:
                    conv_rate = (cd[4] / cd[3] * 100) if cd[3] > 0 else 0
                    st.write(f"📱 {cd[0]} ({cd[1]}) → Clicks: {cd[3]} | Registered: {cd[4]} | Rate: {conv_rate:.1f}%")
            else:
                st.info("No click data")
    
    elif admin_pass:
        st.error("Incorrect password.")
