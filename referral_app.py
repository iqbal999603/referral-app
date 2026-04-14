import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime, timedelta
import pandas as pd
import urllib.parse

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
    .badge-gold { background: linear-gradient(135deg, #FFD700, #FFA500); color: #333; padding: 5px 12px; border-radius: 20px; font-weight: bold; }
    .badge-silver { background: linear-gradient(135deg, #C0C0C0, #A9A9A9); color: #333; padding: 5px 12px; border-radius: 20px; font-weight: bold; }
    .badge-bronze { background: linear-gradient(135deg, #CD7F32, #B87333); color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }
    .challenge-card { background: linear-gradient(135deg, #ff9f43, #ff6b6b); padding: 15px; border-radius: 15px; color: white; margin: 10px 0; }
    .lucky-card { background: linear-gradient(135deg, #a55eea, #5f27cd); padding: 15px; border-radius: 15px; color: white; }
    .streak-card { background: linear-gradient(135deg, #20bf6b, #26de81); padding: 10px; border-radius: 10px; text-align: center; }
    .profile-pic { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 3px solid white; }
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
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('referral.db', check_same_thread=False)
    c = conn.cursor()
    
    # Users table with new fields
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  mobile TEXT UNIQUE,
                  password TEXT,
                  referral_code TEXT UNIQUE,
                  points INTEGER DEFAULT 0,
                  referred_by TEXT,
                  join_date TEXT,
                  city TEXT,
                  streak_days INTEGER DEFAULT 0,
                  last_referral_date TEXT)''')
    
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
    
    # Repair categories table (expanded)
    c.execute('''CREATE TABLE IF NOT EXISTS repair_categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category_name TEXT,
                  description TEXT,
                  solution TEXT)''')
    
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
    
    # Daily referrals tracking
    c.execute('''CREATE TABLE IF NOT EXISTS daily_referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  referral_date TEXT,
                  count INTEGER DEFAULT 0)''')
    
    # Lucky draw entries
    c.execute('''CREATE TABLE IF NOT EXISTS lucky_draw_entries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  entry_date TEXT,
                  is_winner INTEGER DEFAULT 0)''')
    
    # Challenges table
    c.execute('''CREATE TABLE IF NOT EXISTS challenges
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  challenge_name TEXT,
                  start_date TEXT,
                  end_date TEXT,
                  target INTEGER,
                  reward INTEGER,
                  is_active INTEGER DEFAULT 1)''')
    
    # Challenge participants
    c.execute('''CREATE TABLE IF NOT EXISTS challenge_participants
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  challenge_id INTEGER,
                  referrals_done INTEGER DEFAULT 0,
                  completed INTEGER DEFAULT 0)''')
    
    conn.commit()
    
    # Add expanded repair categories if empty
    c.execute("SELECT COUNT(*) FROM repair_categories")
    if c.fetchone()[0] == 0:
        categories = [
            ("چارجنگ نہیں ہوتی", "موبائل چارج نہیں ہو رہا، بیٹری یا چارجنگ پورٹ میں مسئلہ", "چارجنگ پورٹ چیک کریں، بیٹری تبدیل کریں"),
            ("اسکرین ٹوٹی ہوئی", "ڈسپلے ٹوٹ گیا ہے، ٹچ کام نہیں کر رہا", "اسکرین تبدیل کریں"),
            ("آواز نہیں آتی", "اسپیکر سے آواز نہیں آ رہی، ہینڈفری بھی کام نہیں کر رہا", "اسپیکر چیک کریں، آڈیو IC تبدیل کریں"),
            ("موبائل ہینگ ہے", "موبائل سست چل رہا ہے، بار بار رک جاتا ہے", "رام چیک کریں، فیکٹری ری سیٹ کریں"),
            ("بیٹری جلدی ختم ہوتی ہے", "بیٹری بہت جلدی ڈرین ہو جاتی ہے", "بیٹری تبدیل کریں، بیٹری کیلیبریشن کریں"),
            ("وائی فائی / بلوٹوتھ نہیں چلتا", "وائی فائی آن نہیں ہوتا یا بلوٹوتھ کام نہیں کر رہا", "وائی فائی IC چیک کریں، اینٹینا تبدیل کریں"),
            ("کیمرہ کام نہیں کرتا", "کیمرہ بلیک اسکرین دکھاتا ہے یا کریش ہوتا ہے", "کیمرہ ماڈیول تبدیل کریں، فلیکس چیک کریں"),
            ("موبائل گرم ہوتا ہے", "چارجنگ یا استعمال کے دوران بہت گرم ہو جاتا ہے", "پاور IC چیک کریں، بیٹری تبدیل کریں"),
            ("سینسر کام نہیں کرتے", "پروکسیمٹی، لائٹ، یا جائروسکوپ سینسر خراب", "سینسر کیلیبریشن کریں، فلیکس تبدیل کریں"),
            ("مائیکروفون کام نہیں کرتا", "کال میں آواز نہیں جاتی، ریکارڈنگ نہیں ہوتی", "مائیک چیک کریں، آڈیو IC تبدیل کریں"),
            ("وائبریشن نہیں ہوتی", "موبائل وائبریٹ نہیں کرتا", "وائبریشن موٹر تبدیل کریں"),
            ("سیم کارڈ نہیں چلتا", "سیم کارڈ ڈیٹیکٹ نہیں ہو رہا", "سیم ٹرے چیک کریں، سیم IC تبدیل کریں"),
            ("ڈیٹا کیبل سے کنکشن نہیں", "پی سی سے ڈیٹا ٹرانسفر نہیں ہو رہا", "USB پورٹ چیک کریں، ڈیٹا IC تبدیل کریں"),
            ("فنگر پرنٹ نہیں چلتا", "فنگر پرنٹ سینسر کام نہیں کر رہا", "سینسر کیلیبریشن کریں، فلیکس تبدیل کریں"),
            ("اے ایف پی لاک", "فون لاک ہے، پاس ورڈ بھول گئے", "FRP bypass کریں، فلیش کریں"),
        ]
        for cat, desc, sol in categories:
            c.execute("INSERT INTO repair_categories (category_name, description, solution) VALUES (?,?,?)", (cat, desc, sol))
        conn.commit()
    
    # Add default challenge if not exists
    c.execute("SELECT COUNT(*) FROM challenges")
    if c.fetchone()[0] == 0:
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        c.execute("INSERT INTO challenges (challenge_name, start_date, end_date, target, reward, is_active) VALUES (?,?,?,?,?,?)",
                  ("ہفتہ وار ریفرل چیلنج", start_date, end_date, 5, 100, 1))
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

def update_streak(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT last_referral_date, streak_days FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()
    if result:
        last_date = result[0]
        current_streak = result[1] or 0
        if last_date:
            last = datetime.strptime(last_date, "%Y-%m-%d")
            today_dt = datetime.now()
            diff = (today_dt - last).days
            if diff == 1:
                new_streak = current_streak + 1
                if new_streak % 3 == 0:
                    bonus = 50
                    c.execute("UPDATE users SET points = points + ? WHERE id = ?", (bonus, user_id))
                    add_notification(user_id, f"🔥 لگاتار {new_streak} دن ریفرل! آپ کو {bonus} بونس پوائنٹس ملے!")
            elif diff > 1:
                new_streak = 1
            else:
                new_streak = current_streak
        else:
            new_streak = 1
        c.execute("UPDATE users SET streak_days = ?, last_referral_date = ? WHERE id = ?", 
                  (new_streak, today, user_id))
        conn.commit()
        return new_streak
    return 0

def update_daily_referrals(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT id, count FROM daily_referrals WHERE user_id = ? AND referral_date = ?", (user_id, today))
    existing = c.fetchone()
    if existing:
        new_count = existing[1] + 1
        c.execute("UPDATE daily_referrals SET count = ? WHERE id = ?", (new_count, existing[0]))
    else:
        new_count = 1
        c.execute("INSERT INTO daily_referrals (user_id, referral_date, count) VALUES (?,?,?)", (user_id, today, new_count))
    conn.commit()
    
    # Check for daily best
    c.execute("SELECT user_id, count FROM daily_referrals WHERE referral_date = ? ORDER BY count DESC LIMIT 1", (today,))
    best = c.fetchone()
    if best and best[0] == user_id and best[1] == new_count and new_count > 0:
        add_notification(user_id, f"🏆 مبارک ہو! آج کے بہترین ریفرلر ہیں! آپ کو 50 اضافی پوائنٹس ملے!")
        c.execute("UPDATE users SET points = points + 50 WHERE id = ?", (user_id,))
        conn.commit()
    return new_count

def add_lucky_draw_entry(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO lucky_draw_entries (user_id, entry_date) VALUES (?,?)", (user_id, today))
    conn.commit()
    
    # Check monthly winner (every 30 days)
    c.execute("SELECT COUNT(*) FROM lucky_draw_entries WHERE is_winner = 1 AND entry_date > date('now', '-30 days')")
    recent_winners = c.fetchone()[0]
    if recent_winners == 0:
        c.execute("SELECT user_id, COUNT(*) as entries FROM lucky_draw_entries WHERE entry_date > date('now', '-30 days') GROUP BY user_id ORDER BY entries DESC LIMIT 1")
        winner = c.fetchone()
        if winner:
            c.execute("UPDATE lucky_draw_entries SET is_winner = 1 WHERE user_id = ? AND entry_date > date('now', '-30 days')", (winner[0],))
            c.execute("UPDATE users SET points = points + 500 WHERE id = ?", (winner[0],))
            add_notification(winner[0], "🎉 مبارک ہو! آپ ماہانہ لکی ڈرا کے فاتح ہیں! آپ کو 500 پوائنٹس ملے!")
            conn.commit()

def check_challenge_completion(user_id):
    c.execute("SELECT id, target, reward FROM challenges WHERE is_active = 1")
    challenge = c.fetchone()
    if challenge:
        challenge_id, target, reward = challenge
        c.execute("SELECT id, referrals_done FROM challenge_participants WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
        participant = c.fetchone()
        if participant:
            if participant[1] >= target:
                if not c.execute("SELECT completed FROM challenge_participants WHERE id = ?", (participant[0],)).fetchone()[0]:
                    c.execute("UPDATE challenge_participants SET completed = 1 WHERE id = ?", (participant[0],))
                    c.execute("UPDATE users SET points = points + ? WHERE id = ?", (reward, user_id))
                    add_notification(user_id, f"🎯 چیلنج مکمل! آپ کو {reward} بونس پوائنٹس ملے!")

def get_leaderboard(filter_type="all"):
    today = datetime.now().strftime("%Y-%m-%d")
    if filter_type == "daily":
        c.execute("""SELECT u.name, u.points, u.referral_code, 
                           COALESCE(SUM(dr.count), 0) as daily_refs
                    FROM users u
                    LEFT JOIN daily_referrals dr ON u.id = dr.user_id AND dr.referral_date = ?
                    GROUP BY u.id
                    ORDER BY daily_refs DESC, u.points DESC LIMIT 10""", (today,))
    elif filter_type == "weekly":
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        c.execute("""SELECT u.name, u.points, u.referral_code,
                           COALESCE(SUM(rh.points_earned/50), 0) as weekly_refs
                    FROM users u
                    LEFT JOIN referral_history rh ON u.id = rh.referrer_id AND rh.referral_date > ?
                    GROUP BY u.id
                    ORDER BY weekly_refs DESC, u.points DESC LIMIT 10""", (week_ago,))
    elif filter_type == "monthly":
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        c.execute("""SELECT u.name, u.points, u.referral_code,
                           COALESCE(SUM(rh.points_earned/50), 0) as monthly_refs
                    FROM users u
                    LEFT JOIN referral_history rh ON u.id = rh.referrer_id AND rh.referral_date > ?
                    GROUP BY u.id
                    ORDER BY monthly_refs DESC, u.points DESC LIMIT 10""", (month_ago,))
    else:
        c.execute("SELECT name, points, referral_code FROM users ORDER BY points DESC LIMIT 10")
    return c.fetchall()

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

if admin_secret == "Admin@51214725":
    menu = st.sidebar.radio("📌 منتخب کریں", ["✨ نیا رجسٹریشن", "🔐 لاگ ان", "🏠 میرے پوائنٹس", 
                                                "🏆 لیڈر بورڈ", "📜 ریفرل ہسٹری", "💰 ڈسکاؤنٹ ہسٹری",
                                                "📊 کلکس اینالائٹکس", "🔧 مرمت کی اقسام", "🎯 چیلنجز",
                                                "🎲 لکی ڈرا", "👑 ایڈمن پینل"])
else:
    menu = st.sidebar.radio("📌 منتخب کریں", ["✨ نیا رجسٹریشن", "🔐 لاگ ان", "🏠 میرے پوائنٹس",
                                                "🏆 لیڈر بورڈ", "🔧 مرمت کی اقسام", "🎯 چیلنجز",
                                                "🎲 لکی ڈرا"])

# Header
st.markdown('<div class="main-header"><h1>📱 Ali Mobiles Repairing</h1><p>Ali Laal Road Layyah | 03006762827</p><p>ریفرل کرو، موبائل ریپئرنگ ڈسکاؤنٹ پاؤ</p></div>', unsafe_allow_html=True)

# ==================== REGISTRATION ====================
if menu == "✨ نیا رجسٹریشن":
    if st.session_state.logged_in:
        st.success(f"آپ پہلے سے لاگ ان ہیں۔")
        st.stop()
    
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("مکمل نام")
            mobile = st.text_input("موبائل نمبر")
            city = st.selectbox("شہر", ["لاہور", "کراچی", "اسلام آباد", "راولپنڈی", "ملتان", "فیصل آباد", "گوجرانوالہ", "دیگر"])
        with col2:
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
                            update_streak(referrer_id)
                            update_daily_referrals(referrer_id)
                            add_lucky_draw_entry(referrer_id)
                            c.execute("SELECT id FROM challenge_participants WHERE user_id = ?", (referrer_id,))
                            if c.fetchone():
                                c.execute("UPDATE challenge_participants SET referrals_done = referrals_done + 1 WHERE user_id = ?", (referrer_id,))
                                check_challenge_completion(referrer_id)
                            st.success("🎉 آپ کے ریفرر کو 50 پوائنٹس مل گئے۔")
                        else:
                            st.warning("غلط ریفرل کوڈ۔")
                    
                    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("INSERT INTO users (name, mobile, password, referral_code, points, referred_by, join_date, city, streak_days) VALUES (?,?,?,?,?,?,?,?,?)",
                              (name, mobile, hashed_pass, new_code, 0, ref_code if ref_code else None, join_date, city, 0))
                    user_id = c.lastrowid
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
                st.session_state.user_city = user[9] if len(user) > 9 else ""
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
        city = user[9] if len(user) > 9 else "لاہور"
        streak = user[10] if len(user) > 10 else 0
        discount = points * 0.5
        referral_link = f"https://alimobile-referral.streamlit.app/?ref={code}"
        
        # Profile section
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f'<div style="text-align:center"><div class="profile-pic" style="background:#667eea; display:flex; align-items:center; justify-content:center; font-size:40px; width:80px; height:80px; border-radius:50%;">📱</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"### {name}")
            st.markdown(f"📱 {mobile} | 📍 {city}")
            st.markdown(f'<span class="streak-card">🔥 لگاتار {streak} دن ریفرل</span>', unsafe_allow_html=True)
        
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("🔑 ریفرل کوڈ", code)
        with col_b:
            st.metric("⭐ پوائنٹس", points)
        with col_c:
            st.metric("💰 ڈسکاؤنٹ", f"{discount:.0f} PKR")
        with col_d:
            total_clicks, total_conversions, _ = get_click_stats(st.session_state.user_id)
            st.metric("👆 کل کلکس", total_clicks)
        
        st.markdown("---")
        st.markdown("### 🌐 سوشل میڈیا پر شیئر کریں")
        social_urls = get_social_share_urls(referral_link, code, name)
        cols = st.columns(4)
        with cols[0]:
            st.markdown(f'<a href="{social_urls["whatsapp"]}" target="_blank" class="social-share-btn whatsapp" style="display:block;">📱 واٹس ایپ</a>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<a href="{social_urls["facebook"]}" target="_blank" class="social-share-btn facebook" style="display:block;">📘 فیس بک</a>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<a href="{social_urls["twitter"]}" target="_blank" class="social-share-btn twitter" style="display:block;">🐦 ٹویٹر</a>', unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f'<a href="{social_urls["telegram"]}" target="_blank" class="social-share-btn telegram" style="display:block;">📨 ٹیلی گرام</a>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("📤 آپکا ریفرل لنک")
        st.code(referral_link, language="text")
        
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
            st.info(f"📈 مزید {need} پوائنٹس درکار ہیں (یہ {need*0.5:.2f} PKR ڈسکاؤنٹ کے لیے)")
        
        if st.button("🚪 لاگ آؤٹ"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.user_mobile = None
            st.session_state.user_name = None
            st.session_state.user_code = None
            st.rerun()

# ==================== LEADERBOARD WITH BADGES AND FILTER ====================
elif menu == "🏆 لیڈر بورڈ":
    st.subheader("🏆 ٹاپ ریفررز")
    
    filter_type = st.radio("فلٹر کریں:", ["آل ٹائم", "آج کے", "ہفتہ وار", "ماہانہ"], horizontal=True)
    filter_map = {"آل ٹائم": "all", "آج کے": "daily", "ہفتہ وار": "weekly", "ماہانہ": "monthly"}
    top_users = get_leaderboard(filter_map[filter_type])
    
    if top_users:
        for i, user in enumerate(top_users, 1):
            col1, col2, col3 = st.columns([1, 3, 2])
            with col1:
                if i == 1:
                    st.markdown('<span class="badge-gold">🏆 گولڈ</span>', unsafe_allow_html=True)
                elif i == 2:
                    st.markdown('<span class="badge-silver">🥈 سلور</span>', unsafe_allow_html=True)
                elif i == 3:
                    st.markdown('<span class="badge-bronze">🥉 برونز</span>', unsafe_allow_html=True)
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

# ==================== CHALLENGES ====================
elif menu == "🎯 چیلنجز":
    st.subheader("🎯 ہفتہ وار چیلنجز")
    
    c.execute("SELECT id, challenge_name, target, reward, end_date, is_active FROM challenges WHERE is_active = 1")
    challenge = c.fetchone()
    if challenge:
        challenge_id, name, target, reward, end_date, is_active = challenge
        st.markdown(f'<div class="challenge-card"><h3>{name}</h3><p>🎯 ہدف: {target} ریفرلز</p><p>🎁 انعام: {reward} اضافی پوائنٹس</p><p>⏰ اختتام: {end_date}</p></div>', unsafe_allow_html=True)
        
        if st.session_state.logged_in:
            c.execute("SELECT referrals_done, completed FROM challenge_participants WHERE user_id = ? AND challenge_id = ?", 
                      (st.session_state.user_id, challenge_id))
            participant = c.fetchone()
            if participant:
                referrals_done, completed = participant
                if completed:
                    st.success(f"✅ آپ نے یہ چیلنج مکمل کر لیا! +{reward} پوائنٹس مل چکے ہیں۔")
                else:
                    st.progress(min(referrals_done / target, 1.0))
                    st.write(f"آپ نے {referrals_done} / {target} ریفرلز کر لیے۔")
            else:
                if st.button("🎯 چیلنج میں شامل ہوں"):
                    c.execute("INSERT INTO challenge_participants (user_id, challenge_id, referrals_done) VALUES (?,?,?)",
                              (st.session_state.user_id, challenge_id, 0))
                    conn.commit()
                    st.success("آپ چیلنج میں شامل ہو گئے! اب ریفرل کرنا شروع کریں۔")
                    st.rerun()
    else:
        st.info("اس وقت کوئی فعال چیلنج نہیں ہے۔")

# ==================== LUCKY DRAW ====================
elif menu == "🎲 لکی ڈرا":
    st.subheader("🎲 ماہانہ لکی ڈرا")
    
    st.markdown('<div class="lucky-card"><h3>🎁 ماہانہ لکی ڈرا</h3><p>ہر ریفرل پر آپ لکی ڈرا میں شامل ہو جاتے ہیں!</p><p>🎉 ہر مہینے ایک خوش قسمت فاتح کو 500 اضافی پوائنٹس!</p></div>', unsafe_allow_html=True)
    
    if st.session_state.logged_in:
        c.execute("SELECT COUNT(*) FROM lucky_draw_entries WHERE user_id = ? AND entry_date > date('now', '-30 days')", (st.session_state.user_id,))
        entries = c.fetchone()[0]
        st.info(f"📊 آپ اس ماہ {entries} بار لکی ڈرا میں شامل ہو چکے ہیں۔")
        
        c.execute("SELECT user_id FROM lucky_draw_entries WHERE is_winner = 1 AND entry_date > date('now', '-30 days')")
        winner = c.fetchone()
        if winner:
            c.execute("SELECT name FROM users WHERE id = ?", (winner[0],))
            winner_name = c.fetchone()
            st.success(f"🏆 اس ماہ کے فاتح: {winner_name[0]}! مبارک ہو!")
    else:
        st.info("پچھلے مہینے کے فاتحین جلد اعلان کیے جائیں گے۔")

# ==================== REPAIR CATEGORIES (EXPANDED) ====================
elif menu == "🔧 مرمت کی اقسام":
    st.subheader("🔧 موبائل کی عام خرابیاں")
    
    c.execute("SELECT id, category_name, description, solution FROM repair_categories")
    categories = c.fetchall()
    
    search = st.text_input("🔍 خرابی تلاش کریں")
    filtered_cats = [cat for cat in categories if search.lower() in cat[1].lower()] if search else categories
    
    for cat in filtered_cats[:10]:
        with st.expander(f"🔧 {cat[1]}"):
            st.write(f"**تفصیل:** {cat[2]}")
            st.write(f"**حل:** {cat[3]}")
            if st.session_state.logged_in:
                if st.button(f"یہ مسئلہ ہے", key=f"cat_{cat[0]}"):
                    c.execute("INSERT INTO user_repair_selections (user_id, category_id, selection_date) VALUES (?,?,?)",
                              (st.session_state.user_id, cat[0], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    st.success(f"آپ نے '{cat[1]}' کا مسئلہ رپورٹ کر دیا۔ ہم جلد رابطہ کریں گے۔")
    
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

# ==================== REFERRAL HISTORY ====================
elif menu == "📜 ریفرل ہسٹری":
    if not st.session_state.logged_in:
        st.warning("براہ کرم پہلے لاگ ان کریں۔")
        st.stop()
    
    st.subheader("📜 آپ کی ریفرل ہسٹری")
    c.execute("""SELECT rh.id, u.name, u.city, rh.points_earned, rh.referral_date 
                 FROM referral_history rh 
                 JOIN users u ON rh.referred_user_id = u.id 
                 WHERE rh.referrer_id = ? 
                 ORDER BY rh.referral_date DESC""", (st.session_state.user_id,))
    history = c.fetchall()
    
    if history:
        for h in history:
            st.markdown(f'<div class="notification">✅ {h[4][:10]} کو {h[1]} ({h[2]}) نے رجسٹر کیا → +{h[3]} پوائنٹس</div>', unsafe_allow_html=True)
    else:
        st.info("ابھی تک کوئی ریفرل نہیں۔ اپنا ریفرل لنک دوستوں کو بھیجیں!")

# ==================== DISCOUNT HISTORY ====================
elif menu == "💰 ڈسکاؤنٹ ہسٹری":
    if not st.session_state.logged_in:
        st.warning("براہ کرم پہلے لاگ ان کریں۔")
        st.stop()
    
    st.subheader("💰 آپ کی ڈسکاؤنٹ ہسٹری")
    c.execute("SELECT points_used, discount_amount, claim_date FROM discount_history WHERE user_id = ? ORDER BY claim_date DESC", (st.session_state.user_id,))
    history = c.fetchall()
    
    if history:
        for h in history:
            st.markdown(f'<div class="notification">🎁 {h[2][:10]} کو {h[0]} پوائنٹس استعمال کر کے {h[1]:.2f} PKR کا ڈسکاؤنٹ لیا</div>', unsafe_allow_html=True)
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

# ==================== ADMIN PANEL ====================
elif menu == "👑 ایڈمن پینل":
    admin_pass = st.text_input("ایڈمن پاس ورڈ", type="password")
    
    if admin_pass == "Admin51214725":
        st.success("ایڈمن پینل میں خوش آمدید")
        
        admin_tab = st.tabs(["📊 صارفین", "📥 ڈیٹا ایکسپورٹ", "📈 بلک پوائنٹس", "🔧 خرابی کی رپورٹس", 
                             "📊 کلکس رپورٹ", "🏆 چیلنج رپورٹ", "🎲 لکی ڈرا رپورٹ"])
        
        with admin_tab[0]:
            search = st.text_input("🔍 نام یا موبائل سے تلاش کریں")
            if search:
                c.execute("SELECT id, name, mobile, referral_code, points, city, streak_days FROM users WHERE name LIKE ? OR mobile LIKE ? ORDER BY points DESC", 
                          (f'%{search}%', f'%{search}%'))
            else:
                c.execute("SELECT id, name, mobile, referral_code, points, city, streak_days FROM users ORDER BY points DESC")
            users = c.fetchall()
            
            for user in users:
                col1, col2, col3, col4, col5, col6, col7 = st.columns([1,2,2,1,1,1,2])
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
                    st.write(user[5] if user[5] else "-")
                with col7:
                    deduct = st.number_input("کم کریں", min_value=0, max_value=user[4], step=50, key=f"deduct_{user[0]}")
                    if st.button("کم کریں", key=f"btn_{user[0]}"):
                        new_points = user[4] - deduct
                        c.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user[0]))
                        conn.commit()
                        add_notification(user[0], f"🔄 آپ کے {deduct} پوائنٹس کم کر دیے گئے۔ موجودہ پوائنٹس: {new_points}")
                        st.success(f"{user[1]} کے پوائنٹس {new_points} کر دیے گئے۔")
                        st.rerun()
                st.divider()
        
        with admin_tab[1]:
            st.subheader("📥 ڈیٹا ایکسپورٹ")
            c.execute("SELECT id, name, mobile, referral_code, points, referred_by, city, join_date FROM users")
            data = c.fetchall()
            if data:
                df = pd.DataFrame(data, columns=["ID", "نام", "موبائل", "ریفرل کوڈ", "پوائنٹس", "ریفرڈ بذریعہ", "شہر", "تاریخ"])
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 CSV ڈاؤن لوڈ کریں", csv, "users_data.csv", "text/csv")
            else:
                st.info("کوئی ڈیٹا نہیں")
        
        with admin_tab[2]:
            st.subheader("📈 بلک پوائنٹس ایڈ")
            points_to_add = st.number_input("پوائنٹس (تمام صارفین کو)", min_value=0, step=50)
            if st.button("سب کو پوائنٹس دیں"):
                c.execute("UPDATE users SET points = points + ?", (points_to_add,))
                conn.commit()
                st.success(f"تمام صارفین کو {points_to_add} پوائنٹس دیے گئے!")
        
        with admin_tab[3]:
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
        
        with admin_tab[4]:
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
        
        with admin_tab[5]:
            st.subheader("🏆 چیلنج رپورٹ")
            c.execute("""SELECT u.name, cp.referrals_done, cp.completed, c.target, c.reward
                         FROM challenge_participants cp
                         JOIN users u ON cp.user_id = u.id
                         JOIN challenges c ON cp.challenge_id = c.id
                         ORDER BY cp.referrals_done DESC""")
            challenge_data = c.fetchall()
            if challenge_data:
                for cd in challenge_data:
                    status = "✅ مکمل" if cd[2] else "⏳ جاری"
                    st.write(f"📱 {cd[0]} → ریفرلز: {cd[1]}/{cd[3]} | {status} | انعام: {cd[4]} پوائنٹس")
            else:
                st.info("کوئی چیلنج ڈیٹا نہیں")
        
        with admin_tab[6]:
            st.subheader("🎲 لکی ڈرا رپورٹ")
            c.execute("""SELECT u.name, COUNT(le.id) as entries, 
                                SUM(CASE WHEN le.is_winner = 1 THEN 1 ELSE 0 END) as wins
                         FROM lucky_draw_entries le
                         JOIN users u ON le.user_id = u.id
                         GROUP BY u.id
                         ORDER BY entries DESC LIMIT 10""")
            lucky_data = c.fetchall()
            if lucky_data:
                for ld in lucky_data:
                    st.write(f"🎲 {ld[0]} → اندراجات: {ld[1]} | جیتے: {ld[2]}")
            else:
                st.info("کوئی لکی ڈرا ڈیٹا نہیں")
    
    elif admin_pass:
        st.error("غلط پاس ورڈ۔")
