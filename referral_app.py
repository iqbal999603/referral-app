import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime

# Page setup
st.set_page_config(page_title="Ali Mobile Repair ", page_icon="📱", layout="centered")

# Custom CSS for better look
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
    .card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    .referral-code {
        background: #f0f2f6;
        padding: 10px;
        border-radius: 8px;
        font-family: monospace;
        font-size: 20px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Database setup
def init_db():
    conn = sqlite3.connect('referral.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  mobile TEXT UNIQUE,
                  password TEXT,
                  referral_code TEXT UNIQUE,
                  points INTEGER DEFAULT 0,
                  referred_by TEXT,
                  join_date TEXT)''')
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# Helper functions
def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_mobile = None
    st.session_state.user_name = None
    st.session_state.user_code = None

# Sidebar menu with hidden admin
st.sidebar.image("https://img.icons8.com/color/96/000000/smartphone.png", width=80)

# خفیہ کوڈ ڈالنے کا خانہ (صرف آپ کو پتہ ہے)
admin_secret = st.sidebar.text_input("🔑  ", type="password", placeholder=" Becare")

if admin_secret == "Admin@51214725":
    # اگر خفیہ کوڈ درست ہے تو ایڈمن کا آپشن دکھے
    menu = st.sidebar.radio("📌 منتخب کریں", ["✨ نیا رجسٹریشن", "🔐 لاگ ان", "🏠 میرے پوائنٹس", "👑 ایڈمن"])
else:
    # اگر خفیہ کوڈ غلط ہے یا نہیں ڈالا تو صرف 3 آپشن دکھیں
    menu = st.sidebar.radio("📌 منتخب کریں", ["✨ نیا رجسٹریشن", "🔐 لاگ ان", "🏠 میرے پوائنٹس"])

# Header
st.markdown('<div class="main-header"><h1>📱 Ali Mobiles Repairing Ali Laal Road Layyah 03006762827</h1><h1>ریفرل کرو، موبائل ریپئرنگ ڈسکاؤنٹ پاؤ  صرف اسی دن شاپ بند ہونے سے پہلے پہلے</h1></div>', unsafe_allow_html=True)
# ==================== REGISTRATION ====================
if menu == "✨ نیا رجسٹریشن":
    
    if st.session_state.logged_in:
        st.success(f"آپ پہلے سے لاگ ان ہیں۔")
        st.stop()
    
    with st.form("register_form"):
        name = st.text_input("مکمل نام")
        mobile = st.text_input("موبائل نمبر")
        password = st.text_input("پاس ورڈ", type="password")
        confirm = st.text_input("پاس ورڈ کی تصدیق", type="password")
        ref_code = st.text_input("کسی کا ریفرل کوڈ ہے؟ ")
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
                    if ref_code:
                        c.execute("SELECT id, points FROM users WHERE referral_code=?", (ref_code,))
                        referrer = c.fetchone()
                        if referrer:
                            c.execute("UPDATE users SET points = points + 50 WHERE referral_code=?", (ref_code,))
                            conn.commit()
                            st.success("🎉 آپ کے ریفرر کو 50 پوائنٹس مل گئے۔")
                        else:
                            st.warning("غلط ریفرل کوڈ۔")
                    
                    # Insert user
                    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, join_date) VALUES (?,?,?,?,?,?)",
                              (name, mobile, hashed_pass, new_code, 0, join_date))
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
    
    c.execute("SELECT * FROM users WHERE mobile=?", (st.session_state.user_mobile,))
    user = c.fetchone()
    
    if user:
        name, mobile, code, points = user[1], user[2], user[4], user[5]
        discount = points * 0.5
        referral_link = f"https://alimobile-referral.streamlit.app/?ref={code}"
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👤 نام", name)
            st.metric("📱 موبائل", mobile)
        with col2:
            st.metric("🔑 ریفرل کوڈ", code)
            st.metric("⭐ پوائنٹس", points)
        
        st.markdown("---")
        st.markdown(f"### 💰 ڈسکاؤنٹ کی رقم: **{discount:.2f} PKR**")
        
        st.subheader("📤 اپنا ریفرل لنک")
        st.code(referral_link, language="text")
        
        if points >= 200:
            st.success(f"🎁 آپ {discount:.2f} PKR کا ڈسکاؤنٹ حاصل کر سکتے ہیں۔")
        else:
            need = 500 - points
            st.info(f"📈 مزید {need} پوائنٹس درکار ہیں (یہ {need*0.5:.2f} PKR ڈسکاؤنٹ کے لیے)")
        
        if st.button("🚪 لاگ آؤٹ"):
            st.session_state.logged_in = False
            st.session_state.user_mobile = None
            st.session_state.user_name = None
            st.session_state.user_code = None
            st.rerun()

# ==================== ADMIN PANEL ====================
elif menu == "👑 ایڈمن":
    admin_pass = st.text_input("ایڈمن پاس ورڈ", type="password")
    
    if admin_pass == "Admin51214725":
        st.success("ایڈمن پینل میں خوش آمدید")
        
        c.execute("SELECT id, name, mobile, referral_code, points FROM users ORDER BY points DESC")
        users = c.fetchall()
        
        if users:
            for user in users:
                col1, col2, col3, col4, col5 = st.columns([1,2,2,1,2])
                with col1:
                    st.write(user[0])
                with col2:
                    st.write(user[1])
                with col3:
                    st.write(user[2])
                with col4:
                    st.write(f"⭐ {user[4]}")
                with col5:
                    deduct = st.number_input("کم کریں", min_value=0, max_value=user[4], step=10, key=f"deduct_{user[0]}")
                    if st.button("کم کریں", key=f"btn_{user[0]}"):
                        new_points = user[4] - deduct
                        c.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user[0]))
                        conn.commit()
                        st.success(f"{user[1]} کے پوائنٹس {new_points} کر دیے گئے۔")
                        st.rerun()
                st.divider()
        else:
            st.info("ابھی کوئی صارف نہیں۔")
    elif admin_pass:
        st.error("غلط پاس ورڈ۔")
