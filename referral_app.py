import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime
import pandas as pd
import urllib.parse
import requests

# ========== GET SECRETS FROM STREAMLIT CLOUD ==========
try:
    ADMIN_SECRET = st.secrets["ADMIN_SECRET"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    ADMIN_SECRET = "Admin@51214725"
    ADMIN_PASSWORD = "Admin51214725"

# Page setup
st.set_page_config(page_title="Ali Mobile Repair - ریفرل سسٹم", page_icon="📱", layout="centered")

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
    .referral-history-item {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .discount-history-item {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('referral.db', check_same_thread=False)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  mobile TEXT UNIQUE,
                  password TEXT,
                  referral_code TEXT UNIQUE,
                  points INTEGER DEFAULT 0,
                  referred_by TEXT,
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
    
    # Referral clicks tracking table
    c.execute('''CREATE TABLE IF NOT EXISTS referral_clicks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referral_code TEXT,
                  referrer_id INTEGER,
                  ip_address TEXT,
                  clicked_at TEXT,
                  is_converted INTEGER DEFAULT 0)''')
    
    # NEW: Device tracking table (ایک ڈیوائس سے ایک اکاؤنٹ)
    c.execute('''CREATE TABLE IF NOT EXISTS device_tracking
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ip_address TEXT,
                  user_id INTEGER,
                  created_at TEXT)''')
    
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
    
    return conn

conn = init_db()
c = conn.cursor()

# ==================== HELPER FUNCTIONS ====================
def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def add_notification(user_id, message):
    c.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)",
              (user_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_notifications(user_id):
    c.execute("SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC", (user_id,))
    return c.fetchall()

def mark_notification_read(notif_id):
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()

def track_referral_click(referral_code, ip_address):
    c.execute("SELECT id FROM users WHERE referral_code = ?", (referral_code,))
    user = c.fetchone()
    if user:
        c.execute("INSERT INTO referral_clicks (referral_code, referrer_id, ip_address, clicked_at) VALUES (?,?,?,?)",
                  (referral_code, user[0], ip_address, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    return False

def get_click_stats(user_id):
    c.execute("SELECT COUNT(*) FROM referral_clicks WHERE referrer_id = ?", (user_id,))
    total_clicks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referral_history WHERE referrer_id = ?", (user_id,))
    total_conversions = c.fetchone()[0]
    conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
    return total_clicks, total_conversions, conversion_rate

def get_social_share_urls(referral_link, referral_code, user_name):
    message = f"📱 Ali Mobile Repair - ریفرل پروگرام!\n\nمیرا ریفرل کوڈ: {referral_code}\nرجسٹر کرنے کے لیے لنک پر کلک کریں:\n{referral_link}\n\nہر ریفرل پر 50 پوائنٹس! 500 پوائنٹس = 250 PKR ڈسکاؤنٹ!"
    encoded_msg = urllib.parse.quote(message)
    urls = {
        "whatsapp": f"https://wa.me/?text={encoded_msg}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={urllib.parse.quote(referral_link)}&quote={encoded_msg}",
        "twitter": f"https://twitter.com/intent/tweet?text={encoded_msg}&url={urllib.parse.quote(referral_link)}",
        "telegram": f"https://t.me/share/url?url={urllib.parse.quote(referral_link)}&text={encoded_msg}",
    }
    return urls

def get_user_ip():
    """صارف کا اصلی IP Address حاصل کریں"""
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text
        return ip
    except:
        return "127.0.0.1"

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
    import hashlib
    ip_address = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:15]
    track_referral_click(ref_code, ip_address)

# ==================== SIDEBAR ====================
st.sidebar.image("https://img.icons8.com/color/96/000000/smartphone.png", width=80)

admin_secret = st.sidebar.text_input("🔑 خفیہ کوڈ", type="password", placeholder="ایڈمن کوڈ")

if admin_secret == ADMIN_SECRET:
    menu = st.sidebar.radio("📌 منتخب کریں", ["✨ نیا رجسٹریشن", "🔐 لاگ ان", "🏠 میرے پوائنٹس", 
                                                "🏆 لیڈر بورڈ", "📜 ریفرل ہسٹری", "💰 ڈسکاؤنٹ ہسٹری",
                                                "📊 کلکس اینالائٹکس", "🔧 مرمت کی اقسام", "👑 ایڈمن پینل"])
else:
    menu = st.sidebar.radio("📌 منتخب کریں", ["✨ نیا رجسٹریشن", "🔐 لاگ ان", "🏠 میرے پوائنٹس",
                                                "🏆 لیڈر بورڈ", "🔧 مرمت کی اقسام"])

# Header
st.markdown('<div class="main-header"><h1>📱 Ali Mobiles Repairing</h1><p>Ali Laal Road Layyah | 03006762827</p><p>ریفرل کرو، موبائل ریپئرنگ ڈسکاؤنٹ پاؤ</p></div>', unsafe_allow_html=True)

# ==================== REGISTRATION (WITH DEVICE TRACKING) ====================
if menu == "✨ نیا رجسٹریشن":
    if st.session_state.logged_in:
        st.success(f"آپ پہلے سے لاگ ان ہیں۔")
        st.stop()
    
    # === IP Address کے ذریعے ڈیوائس چیک ===
    user_ip = get_user_ip()
    
    # چیک کریں کہ اس IP سے پہلے اکاؤنٹ بن چکا ہے یا نہیں
    c.execute("SELECT id, user_id FROM device_tracking WHERE ip_address = ?", (user_ip,))
    existing_device = c.fetchone()
    
    if existing_device:
        st.error("❌ اس ڈیوائس سے پہلے ہی ایک اکاؤنٹ بن چکا ہے!")
        st.info("ہر ڈیوائس/پی سی/موبائل سے صرف ایک اکاؤنٹ بنایا جا سکتا ہے۔")
        st.stop()
    
    with st.form("register_form"):
        name = st.text_input("مکمل نام")
        mobile = st.text_input("موبائل نمبر")
        password = st.text_input("پاس ورڈ", type="password")
        confirm = st.text_input("پاس ورڈ کی تصدیق", type="password")
        ref_code = st.text_input("کسی کا ریفرل کوڈ ہے؟ (اختیاری)")
        submitted = st.form_submit_button("رجسٹر کریں")
        
        if submitted:
            if not name or not mobile or not password:
                st.error("براہ کرم تمام ضروری فیلڈز بھریں۔")
            elif password != confirm:
                st.error("پاس ورڈ ایک جیسے نہیں ہیں۔")
            elif len(password) < 4:
                st.error("پاس ورڈ کم از کم 4 حروف کا ہو۔")
            else:
                c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
                if c.fetchone():
                    st.error("یہ موبائل نمبر پہلے سے رجسٹر ہے۔")
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
                            c.execute("UPDATE referral_clicks SET is_converted = 1 WHERE referral_code = ? AND is_converted = 0 ORDER BY clicked_at DESC LIMIT 1", (ref_code,))
                            conn.commit()
                            add_notification(referrer_id, f"🎉 مبارک ہو! {name} نے آپ کے ریفرل کوڈ سے رجسٹر کیا۔ آپ کو 50 پوائنٹس مل گئے۔")
                            st.success("🎉 آپ کے ریفرر کو 50 پوائنٹس مل گئے۔")
                        else:
                            st.warning("غلط ریفرل کوڈ۔")
                    
                    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by, join_date) VALUES (?,?,?,?,?,?,?)",
                              (name, mobile, hashed_pass, new_code, 0, ref_code if ref_code else None, join_date))
                    user_id = c.lastrowid
                    conn.commit()
                    
                    # === IP Address کو ریکارڈ کریں (Device Tracking) ===
                    c.execute("INSERT INTO device_tracking (ip_address, user_id, created_at) VALUES (?,?,?)",
                              (user_ip, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    
                    if referrer_id:
                        c.execute("INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date) VALUES (?,?,?,?)",
                                  (referrer_id, user_id, 50, join_date))
                        conn.commit()
                    
                    st.success(f"✅ رجسٹریشن مکمل! آپ کا ریفرل کوڈ: **{new_code}**")
                    st.info("اب لاگ ان کریں۔")

# ==================== LOGIN ====================
elif menu == "🔐 لاگ ان":
    if st.session_state.logged_in:
        st.success(f"آپ پہلے سے لاگ ان ہیں۔")
        st.stop()
    
    with st.form("login_form"):
        mobile = st.text_input("موبائل نمبر")
        password = st.text_input("پاس ورڈ", type="password")
        submitted = st.form_submit_button("لاگ ان")
        
        if submitted:
            c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
            user = c.fetchone()
            if user and user[3] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.user_mobile = user[2]
                st.session_state.user_name = user[1]
                st.session_state.user_code = user[4]
                st.success("لاگ ان کامیاب!")
                st.rerun()
            else:
                st.error("غلط موبائل نمبر یا پاس ورڈ۔")

# ==================== DASHBOARD ====================
elif menu == "🏠 میرے پوائنٹس":
    if not st.session_state.logged_in:
        st.warning("براہ کرم پہلے لاگ ان کریں۔")
        st.stop()
    
    notifs = get_notifications(st.session_state.user_id)
    if notifs:
        with st.expander("📢 نوٹیفکیشنز"):
            for notif in notifs:
                st.markdown(f'<div class="notification">🔔 {notif[2]}</div>', unsafe_allow_html=True)
                mark_notification_read(notif[0])
    
    c.execute("SELECT * FROM users WHERE id=?", (st.session_state.user_id,))
    user = c.fetchone()
    
    if user:
        name, mobile, code, points = user[1], user[2], user[4], user[5]
        discount = points * 1
        referral_link = f"https://alimobile-referral.streamlit.app/?ref={code}"
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👤 نام", name)
            st.metric("📱 موبائل", mobile)
        with col2:
            st.metric("🔑 ریفرل کوڈ", code)
            st.metric("⭐ پوائنٹس", points)
        
        total_clicks, total_conversions, conversion_rate = get_click_stats(st.session_state.user_id)
        
        st.markdown("---")
        st.markdown("### 📊 آپ کے ریفرل لنک کی کارکردگی")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("👆 کل کلکس", total_clicks)
        with col_b:
            st.metric("✅ رجسٹریشنز", total_conversions)
        with col_c:
            st.metric("📈 کنورژن ریٹ", f"{conversion_rate:.1f}%")
        
        st.markdown("---")
        st.markdown(f"### 💰 ڈسکاؤنٹ کی رقم: **{discount:.2f} PKR**")
        
        st.subheader("📤 آپکا ریفرل لنک")
        st.code(referral_link, language="text")
        
        st.markdown("### 🌐 سوشل میڈیا پر شیئر کریں")
        social_urls = get_social_share_urls(referral_link, code, name)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<a href="{social_urls["whatsapp"]}" target="_blank" class="social-share-btn whatsapp" style="display:block;">📱 واٹس ایپ</a>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<a href="{social_urls["facebook"]}" target="_blank" class="social-share-btn facebook" style="display:block;">📘 فیس بک</a>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<a href="{social_urls["twitter"]}" target="_blank" class="social-share-btn twitter" style="display:block;">🐦 ٹویٹر</a>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<a href="{social_urls["telegram"]}" target="_blank" class="social-share-btn telegram" style="display:block;">📨 ٹیلی گرام</a>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        if points >= 500:
            if st.button("🎁 ڈسکاؤنٹ کلیم کریں"):
                c.execute("INSERT INTO discount_history (user_id, points_used, discount_amount, claim_date, status) VALUES (?,?,?,?,?)",
                          (st.session_state.user_id, points, discount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "claimed"))
                c.execute("UPDATE users SET points = 0 WHERE id=?", (st.session_state.user_id,))
                conn.commit()
                st.success(f"🎉 آپ نے {discount:.2f} PKR کا ڈسکاؤنٹ کلیم کر لیا!")
                st.rerun()
        else:
            need = 500 - points
            st.info(f"📈 مزید {need} پوائنٹس درکار ہیں ( {need:.2f} ڈسکاؤنٹ کے لیے ابھی باقی)")
        
        if st.button("🚪 لاگ آؤٹ"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.user_mobile = None
            st.session_state.user_name = None
            st.session_state.user_code = None
            st.rerun()

# ==================== LEADERBOARD ====================
elif menu == "🏆 لیڈر بورڈ":
    st.subheader("🏆 ٹاپ ریفررز")
    c.execute("SELECT name, points, referral_code FROM users ORDER BY points DESC LIMIT 10")
    top_users = c.fetchall()
    
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
                st.write(f"⭐ {user[1]} پوائنٹس")
        st.divider()
        st.caption("ہر ریفرل پر 50 پوائنٹس | 500 پوائنٹس = 250 PKR ڈسکاؤنٹ")
    else:
        st.info("ابھی کوئی صارف نہیں۔")

# ==================== REFERRAL HISTORY (NEW COLOR) ====================
elif menu == "📜 ریفرل ہسٹری":
    if not st.session_state.logged_in:
        st.warning("براہ کرم پہلے لاگ ان کریں۔")
        st.stop()
    
    st.subheader("📜 آپ کی ریفرل ہسٹری")
    c.execute("""SELECT rh.id, u.name, rh.points_earned, rh.referral_date 
                 FROM referral_history rh 
                 JOIN users u ON rh.referred_user_id = u.id 
                 WHERE rh.referrer_id = ? 
                 ORDER BY rh.referral_date DESC""", (st.session_state.user_id,))
    history = c.fetchall()
    
    if history:
        for h in history:
            st.markdown(f'<div class="referral-history-item">✅ {h[3][:10]} کو {h[1]} نے رجسٹر کیا → +{h[2]} پوائنٹس</div>', unsafe_allow_html=True)
    else:
        st.info("ابھی تک کوئی ریفرل نہیں۔ اپنا ریفرل لنک دوستوں کو بھیجیں!")

# ==================== DISCOUNT HISTORY (NEW COLOR - SAME AS REFERRAL HISTORY) ====================
elif menu == "💰 ڈسکاؤنٹ ہسٹری":
    if not st.session_state.logged_in:
        st.warning("براہ کرم پہلے لاگ ان کریں۔")
        st.stop()
    
    st.subheader("💰 آپ کی ڈسکاؤنٹ ہسٹری")
    c.execute("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id = ? ORDER BY claim_date DESC", (st.session_state.user_id,))
    history = c.fetchall()
    
    if history:
        for h in history:
            st.markdown(f'<div class="discount-history-item">🎁 {h[2][:10]} کو {h[0]} پوائنٹس استعمال کر کے {h[1]:.2f} PKR کا ڈسکاؤنٹ لیا</div>', unsafe_allow_html=True)
    else:
        st.info("ابھی تک کوئی ڈسکاؤنٹ کلیم نہیں کیا۔")

# ==================== CLICK ANALYTICS ====================
elif menu == "📊 کلکس اینالائٹکس":
    if not st.session_state.logged_in:
        st.warning("براہ کرم پہلے لاگ ان کریں۔")
        st.stop()
    
    st.subheader("📊 آپ کے ریفرل لنک کی تفصیلی رپورٹ")
    total_clicks, total_conversions, conversion_rate = get_click_stats(st.session_state.user_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👆 کل کلکس", total_clicks)
    with col2:
        st.metric("✅ کامیاب رجسٹریشنز", total_conversions)
    with col3:
        st.metric("📈 کنورژن ریٹ", f"{conversion_rate:.1f}%")
    
    st.divider()
    st.subheader("📋 حالیہ کلکس کی تفصیلات")
    c.execute("SELECT clicked_at, is_converted FROM referral_clicks WHERE referrer_id = ? ORDER BY clicked_at DESC LIMIT 20", (st.session_state.user_id,))
    recent_clicks = c.fetchall()
    
    if recent_clicks:
        for click in recent_clicks:
            status = "✅ تبدیل ہوا" if click[1] == 1 else "⏳ زیر التواء"
            st.write(f"📅 {click[0][:16]} → {status}")
    else:
        st.info("ابھی تک کسی نے آپ کے لنک پر کلک نہیں کیا۔")

# ==================== REPAIR CATEGORIES ====================
elif menu == "🔧 مرمت کی اقسام":
    st.subheader("🔧 موبائل کی عام خرابیاں")
    c.execute("SELECT id, category_name, description FROM repair_categories")
    categories = c.fetchall()
    
    for cat in categories:
        with st.expander(f"🔧 {cat[1]}"):
            st.write(cat[2])
            if st.session_state.logged_in:
                if st.button(f"یہ مسئلہ ہے", key=f"cat_{cat[0]}"):
                    c.execute("INSERT INTO user_repair_selections (user_id, category_id, selection_date) VALUES (?,?,?)",
                              (st.session_state.user_id, cat[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success(f"آپ نے '{cat[1]}' کا مسئلہ رپورٹ کر دیا۔")
    
    if st.session_state.logged_in:
        st.divider()
        st.subheader("آپ کی رپورٹ کردہ خرابیاں")
        c.execute("""SELECT rc.category_name, us.selection_date 
                     FROM user_repair_selections us 
                     JOIN repair_categories rc ON us.category_id = rc.id 
                     WHERE us.user_id = ? 
                     ORDER BY us.selection_date DESC LIMIT 5""", (st.session_state.user_id,))
        user_issues = c.fetchall()
        if user_issues:
            for issue in user_issues:
                st.write(f"📌 {issue[1][:10]} کو: {issue[0]}")
        else:
            st.info("آپ نے ابھی تک کوئی خرابی رپورٹ نہیں کی۔")

# ==================== ADMIN PANEL ====================
elif menu == "👑 ایڈمن پینل":
    admin_pass = st.text_input("ایڈمن پاس ورڈ", type="password")
    
    if admin_pass == ADMIN_PASSWORD:
        st.success("ایڈمن پینل میں خوش آمدید")
        
        admin_tab = st.tabs(["📊 صارفین", "📥 ڈیٹا ایکسپورٹ", "📤 CSV اپ لوڈ", "📈 بلک پوائنٹس", "🔧 خرابی کی رپورٹس", "📊 کلکس رپورٹ", "📱 ڈیوائس ٹریکنگ"])
        
        # Tab 0: Users
        with admin_tab[0]:
            search = st.text_input("🔍 نام یا موبائل سے تلاش کریں")
            if search:
                c.execute("SELECT id, name, mobile, referral_code, points FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC", 
                          (f'%{search}%', f'%{search}%'))
            else:
                c.execute("SELECT id, name, mobile, referral_code, points FROM users ORDER BY points DESC")
            users = c.fetchall()
            
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
                    deduct = st.number_input("کم کریں", min_value=0, max_value=user[4], step=50, key=f"deduct_{user[0]}")
                    if st.button("کم کریں", key=f"btn_{user[0]}"):
                        new_points = user[4] - deduct
                        c.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user[0]))
                        conn.commit()
                        add_notification(user[0], f"🔄 آپ کے {deduct} پوائنٹس کم کر دیے گئے۔ موجودہ پوائنٹس: {new_points}")
                        st.success(f"{user[1]} کے پوائنٹس {new_points} کر دیے گئے۔")
                        st.rerun()
                st.divider()
        
        # Tab 1: Export Data
        with admin_tab[1]:
            st.subheader("📥 ڈیٹا ایکسپورٹ")
            c.execute("SELECT id, name, mobile, referral_code, points, referred_by, join_date FROM users")
            data = c.fetchall()
            if data:
                df = pd.DataFrame(data, columns=["ID", "نام", "موبائل", "ریفرل کوڈ", "پوائنٹس", "ریفرڈ بذریعہ", "تاریخ"])
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 CSV ڈاؤن لوڈ کریں", csv, f"users_data_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
                st.info(f"📊 کل صارفین: {len(data)}")
            else:
                st.info("کوئی ڈیٹا نہیں")
        
        # Tab 2: CSV Upload
        with admin_tab[2]:
            st.subheader("📤 پرانی CSV فائل اپ لوڈ کریں (ڈیٹا ضم کرنے کے لیے)")
            st.warning("⚠️ نوٹ: یہ موجودہ ڈیٹا کو ڈیلیٹ نہیں کرے گا، صرف نئے صارفین شامل کرے گا۔")
            
            uploaded_file = st.file_uploader("پہلے سے ڈاؤن لوڈ کردہ CSV فائل منتخب کریں", type=["csv"])
            
            if uploaded_file is not None:
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    st.write("اپ لوڈ کردہ ڈیٹا کا نمونہ:", df_upload.head())
                    st.write(f"کل ریکارڈز: {len(df_upload)}")
                    
                    if st.button("🔄 ڈیٹا ضم کریں (Merge Data)"):
                        new_users_added = 0
                        duplicate_skipped = 0
                        
                        for _, row in df_upload.iterrows():
                            mobile = str(row["موبائل"]) if "موبائل" in row else str(row.get("mobile", ""))
                            if not mobile:
                                continue
                            
                            c.execute("SELECT id FROM users WHERE mobile = ?", (mobile,))
                            if not c.fetchone():
                                new_referral_code = generate_code()
                                name = row["نام"] if "نام" in row else row.get("name", "")
                                points = int(row["پوائنٹس"]) if "پوائنٹس" in row else 0
                                referred_by = row["ریفرڈ بذریعہ"] if "ریفرڈ بذریعہ" in row else None
                                
                                if "پاس ورڈ" in row:
                                    hashed_pass = hash_password(str(row["پاس ورڈ"]))
                                else:
                                    hashed_pass = hash_password("123456")
                                
                                try:
                                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by, join_date) VALUES (?,?,?,?,?,?,?)",
                                              (name, mobile, hashed_pass, new_referral_code, points, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                                    new_users_added += 1
                                except sqlite3.IntegrityError:
                                    duplicate_skipped += 1
                            else:
                                duplicate_skipped += 1
                        
                        conn.commit()
                        st.success(f"✅ {new_users_added} نئے صارفین شامل کر دیے گئے۔")
                        if duplicate_skipped > 0:
                            st.info(f"⚠️ {duplicate_skipped} ڈپلیکیٹ صارفین کو چھوڑ دیا گیا۔")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"فائل پڑھنے میں خرابی: {str(e)}")
        
        # Tab 3: Bulk Points
        with admin_tab[3]:
            st.subheader("📈 بلک پوائنٹس ایڈ")
            points_to_add = st.number_input("پوائنٹس (تمام صارفین کو)", min_value=0, step=50)
            if st.button("سب کو پوائنٹس دیں"):
                c.execute("UPDATE users SET points = points + ?", (points_to_add,))
                conn.commit()
                st.success(f"تمام صارفین کو {points_to_add} پوائنٹس دیے گئے!")
        
        # Tab 4: Repair Reports
        with admin_tab[4]:
            st.subheader("🔧 صارفین کی رپورٹ کردہ خرابیاں")
            c.execute("""SELECT u.name, u.mobile, rc.category_name, us.selection_date 
                         FROM user_repair_selections us 
                         JOIN users u ON us.user_id = u.id 
                         JOIN repair_categories rc ON us.category_id = rc.id 
                         ORDER BY us.selection_date DESC LIMIT 20""")
            reports = c.fetchall()
            if reports:
                for r in reports:
                    st.write(f"📱 {r[0]} ({r[1]}) → {r[2]} - {r[3][:10]}")
            else:
                st.info("کوئی رپورٹ نہیں")
        
        # Tab 5: Click Report
        with admin_tab[5]:
            st.subheader("📊 تمام صارفین کے کلکس کی رپورٹ")
            c.execute("""SELECT u.name, u.mobile, u.referral_code, 
                                COUNT(rc.id) as total_clicks,
                                SUM(CASE WHEN rc.is_converted = 1 THEN 1 ELSE 0 END) as conversions
                         FROM users u
                         LEFT JOIN referral_clicks rc ON u.id = rc.referrer_id
                         GROUP BY u.id
                         ORDER BY total_clicks DESC""")
            click_data = c.fetchall()
            if click_data:
                for cd in click_data:
                    conv_rate = (cd[4] / cd[3] * 100) if cd[3] > 0 else 0
                    st.write(f"📱 {cd[0]} ({cd[1]}) → کلکس: {cd[3]} | رجسٹر: {cd[4]} | شرح: {conv_rate:.1f}%")
            else:
                st.info("کوئی کلکس ڈیٹا نہیں")
        
        # Tab 6: Device Tracking (نیا)
        with admin_tab[6]:
            st.subheader("📱 ڈیوائس ٹریکنگ رپورٹ")
            st.info("یہاں وہ تمام IP ایڈریس ہیں جن سے اکاؤنٹ بنائے گئے ہیں۔")
            
            c.execute("""SELECT dt.ip_address, u.name, u.mobile, dt.created_at 
                         FROM device_tracking dt 
                         JOIN users u ON dt.user_id = u.id 
                         ORDER BY dt.created_at DESC""")
            devices = c.fetchall()
            if devices:
                for d in devices:
                    st.write(f"🌐 IP: {d[0]} | 👤 {d[1]} ({d[2]}) | 📅 {d[3][:16]}")
                st.info(f"📊 کل ڈیوائسز: {len(devices)}")
            else:
                st.info("کوئی ڈیوائس ٹریک نہیں۔")
    
    elif admin_pass:
        st.error("غلط پاس ورڈ۔")
