import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime
import pandas as pd
import urllib.parse
import re

# ========== CONFIG ==========
st.set_page_config(page_title="Ali Mobile Referral", layout="wide")

# ========== SECURITY ==========
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def validate_mobile(m):
    return bool(re.fullmatch(r"03\d{9}", m))

# ========== DB ==========
def get_db():
    conn = sqlite3.connect("referral.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            name TEXT,
            mobile TEXT UNIQUE,
            password TEXT,
            referral_code TEXT,
            points INTEGER DEFAULT 0,
            join_date TEXT
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS referral_history(
            id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            referred_user_id INTEGER,
            points_earned INTEGER,
            referral_date TEXT
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS referral_clicks(
            id INTEGER PRIMARY KEY,
            referral_code TEXT,
            referrer_id INTEGER,
            clicked_at TEXT,
            is_converted INTEGER DEFAULT 0
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS discount_history(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            discount_amount INTEGER,
            claim_date TEXT
        )""")

init_db()

# ========== SESSION ==========
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "admin_logged" not in st.session_state:
    st.session_state.admin_logged = False
if "page" not in st.session_state:
    st.session_state.page = "Home"

# ========== SIDEBAR ==========
menu = ["Home", "Register", "Login"]

if st.session_state.logged_in:
    menu += ["Dashboard", "Referral History", "Analytics", "Leaderboard"]

selected = st.sidebar.selectbox("Menu", menu)

# 🔐 ADMIN ACCESS BUTTON
if st.sidebar.checkbox("Admin Panel"):
    st.session_state.page = "Admin"
else:
    st.session_state.page = selected

# ========== HOME ==========
if st.session_state.page == "Home":
    st.title("Ali Mobile Referral System")
    st.write("Refer Users And Earn Repairing Rewards. (ALI LaaL Road Layyah) 03006762827")

# ========== REGISTER ==========
elif st.session_state.page == "Register":
    st.subheader("Register")

    name = st.text_input("Name")
    mobile = st.text_input("Mobile")
    pwd = st.text_input("Password", type="password")
    ref = st.text_input("Referral Code")

    if st.button("Register"):
        if not validate_mobile(mobile):
            st.error("Invalid mobile format")
        else:
            try:
                with get_db() as conn:
                    code = generate_code()
                    conn.execute("INSERT INTO users VALUES (NULL,?,?,?,?,?,?)",
                                 (name, mobile, hash_password(pwd), code, 0, datetime.now()))
                st.success(f"Account created. Code: {code}")
            except:
                st.error(f"Error: {e}")

# ========== LOGIN ==========
elif st.session_state.page == "Login":
    st.subheader("Login")

    mobile = st.text_input("Mobile")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        with get_db() as conn:
            u = conn.execute("SELECT * FROM users WHERE mobile=?", (mobile,)).fetchone()

        if u and u["password"] == hash_password(pwd):
            st.session_state.logged_in = True
            st.session_state.user_id = u["id"]
            st.session_state.user_name = u["name"]
            st.session_state.user_code = u["referral_code"]
            st.success("Logged in")
            st.rerun()
        else:
            st.error("Invalid login")
# ========== HELPER FUNCTIONS ==========
def get_user(user_id):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

def get_stats(user_id):
    with get_db() as conn:
        points = conn.execute("SELECT points FROM users WHERE id=?", (user_id,)).fetchone()["points"]

        clicks = conn.execute(
            "SELECT COUNT(*) as c FROM referral_clicks WHERE referrer_id=?",
            (user_id,)
        ).fetchone()["c"]

        conversions = conn.execute(
            "SELECT COUNT(*) as c FROM referral_history WHERE referrer_id=?",
            (user_id,)
        ).fetchone()["c"]

    rate = (conversions / clicks * 100) if clicks else 0
    return points, clicks, conversions, rate


def track_click(ref_code):
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE referral_code=?",
            (ref_code,)
        ).fetchone()

        if user:
            conn.execute("""
            INSERT INTO referral_clicks (referral_code, referrer_id, clicked_at)
            VALUES (?,?,?)
            """, (ref_code, user["id"], datetime.now()))


def apply_referral(ref_code, new_user_id):
    with get_db() as conn:
        ref = conn.execute(
            "SELECT id FROM users WHERE referral_code=?",
            (ref_code,)
        ).fetchone()

        if not ref:
            return

        ref_id = ref["id"]

        conn.execute("UPDATE users SET points = points + 50 WHERE id=?", (ref_id,))

        conn.execute("""
        INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date)
        VALUES (?,?,?,?)
        """, (ref_id, new_user_id, 50, datetime.now()))

        conn.execute("""
        UPDATE referral_clicks
        SET is_converted=1
        WHERE referral_code=? AND referrer_id=? AND is_converted=0
        """, (ref_code, ref_id))


def claim_discount(user_id):
    with get_db() as conn:
        user = conn.execute("SELECT points FROM users WHERE id=?", (user_id,)).fetchone()

        if user["points"] < 500:
            return False

        conn.execute("""
        INSERT INTO discount_history (user_id, discount_amount, claim_date)
        VALUES (?,?,?)
        """, (user_id, 500, datetime.now()))

        conn.execute("UPDATE users SET points = points - 500 WHERE id=?", (user_id,))
        return True


# ========== REFERRAL TRACK FROM URL ==========
params = st.query_params
if "ref" in params:
    track_click(params["ref"])


# ========== DASHBOARD ==========
if st.session_state.page == "Dashboard":
    if not st.session_state.logged_in:
        st.warning("Login required")
        st.stop()

    st.subheader("Dashboard")

    user = get_user(st.session_state.user_id)
    points, clicks, conversions, rate = get_stats(st.session_state.user_id)

    col1, col2, col3 = st.columns(3)
    col1.metric("Points", points)
    col2.metric("Clicks", clicks)
    col3.metric("Conversion %", f"{rate:.1f}%")

    st.divider()

    # Referral Link
    st.subheader("Your Referral Link")
    link = f"https://yourapp.streamlit.app/?ref={user['referral_code']}"
    st.code(link)

    # Discount
    st.subheader("Reward")
    if points >= 500:
        if st.button("Claim 500 PKR"):
            if claim_discount(user["id"]):
                st.success("Discount claimed")
                st.rerun()
    else:
        st.info(f"Need {500 - points} more points")

    # Logout
    if st.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ========== REFERRAL HISTORY ==========
elif st.session_state.page == "Referral History":
    st.subheader("Referral History")

    with get_db() as conn:
        data = conn.execute("""
        SELECT u.name, rh.points_earned, rh.referral_date
        FROM referral_history rh
        JOIN users u ON rh.referred_user_id=u.id
        WHERE rh.referrer_id=?
        """, (st.session_state.user_id,)).fetchall()

    if not data:
        st.info("No referrals")
    else:
        for r in data:
            st.write(f"{r['name']} → +{r['points_earned']}")


# ========== ANALYTICS ==========
elif st.session_state.page == "Analytics":
    st.subheader("Analytics")

    points, clicks, conversions, rate = get_stats(st.session_state.user_id)

    st.metric("Clicks", clicks)
    st.metric("Registrations", conversions)
    st.metric("Conversion Rate", f"{rate:.2f}%")

    st.divider()

    with get_db() as conn:
        logs = conn.execute("""
        SELECT clicked_at, is_converted
        FROM referral_clicks
        WHERE referrer_id=?
        ORDER BY clicked_at DESC
        LIMIT 20
        """, (st.session_state.user_id,)).fetchall()

    for log in logs:
        status = "Converted" if log["is_converted"] else "Pending"
        st.write(f"{log['clicked_at']} → {status}")


# ========== LEADERBOARD ==========
elif st.session_state.page == "Leaderboard":
    st.subheader("Top Users")

    with get_db() as conn:
        top = conn.execute("""
        SELECT name, points
        FROM users
        ORDER BY points DESC
        LIMIT 20
        """).fetchall()

    for i, u in enumerate(top, 1):
        st.write(f"{i}. {u['name']} — {u['points']} pts")
# ========== ADMIN CONFIG ==========
ADMIN_PASSWORD = "Admin51214725"   # Recommended: move to st.secrets later

# ========== ADMIN LOGIN ==========
def admin_login():
    st.subheader("🔐 Admin Login")

    pwd = st.text_input("Enter Admin Password", type="password", key="admin_pwd")

    if st.button("Login", key="admin_login_btn"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.admin_logged = True
            st.success("Admin access granted")
            st.rerun()
        else:
            st.error("Wrong password")

def is_admin():
    return st.session_state.get("admin_logged", False)


# ========== ADMIN PAGE ROUTE ==========
if st.session_state.page == "Admin":

    # 🔐 If not logged in → show login
    if not is_admin():
        admin_login()
        st.stop()

    # ✅ ADMIN PANEL UI STARTS HERE
    st.title("👑 Admin Panel")

    # 🔓 Logout
    if st.button("🚪 Logout Admin"):
        st.session_state.admin_logged = False
        st.session_state.page = "Home"
        st.rerun()

    tabs = st.tabs([
        "👥 Users",
        "⚙ Actions",
        "📁 CSV",
        "📊 Reports"
    ])

    # ========== USERS TAB ==========
    with tabs[0]:
        st.subheader("All Users")

        with get_db() as conn:
            users = conn.execute("SELECT id,name,mobile,points FROM users ORDER BY points DESC").fetchall()

        if not users:
            st.info("No users found")
        else:
            for u in users:
                cols = st.columns([1,3,3,2,2,2])

                cols[0].write(u["id"])
                cols[1].write(u["name"])
                cols[2].write(u["mobile"])
                cols[3].write(u["points"])

                # 🔐 Reset Password
                if cols[4].button("Reset", key=f"reset_{u['id']}"):
                    new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE users SET password=? WHERE id=?",
                            (hash_password(new_pass), u["id"])
                        )
                    st.success(f"New password: {new_pass}")

                # ❌ Delete User
                if cols[5].button("Delete", key=f"delete_{u['id']}"):
                    with get_db() as conn:
                        conn.execute("DELETE FROM users WHERE id=?", (u["id"],))
                    st.warning("User deleted")
                    st.rerun()

                st.divider()

    # ========== ACTIONS TAB ==========
    with tabs[1]:
        st.subheader("Bulk Actions")

        pts = st.number_input("Add points to ALL users", min_value=0, step=50)

        if st.button("Apply Points"):
            with get_db() as conn:
                conn.execute("UPDATE users SET points = points + ?", (pts,))
            st.success("Points added to all users")

    # ========== CSV TAB ==========
    with tabs[2]:
        st.subheader("CSV Tools")

        # EXPORT
        with get_db() as conn:
            data = conn.execute("SELECT id,name,mobile,points FROM users").fetchall()

        df = pd.DataFrame(data, columns=["ID","Name","Mobile","Points"])
        st.download_button("📥 Download CSV", df.to_csv(index=False), "users.csv", "text/csv")

        # IMPORT
        file = st.file_uploader("Upload CSV", type=["csv"])

        if file and st.button("Import CSV"):
            df = pd.read_csv(file)
            added, skipped = 0, 0

            with get_db() as conn:
                for _, row in df.iterrows():
                    mobile = str(row.get("Mobile", "")).strip()

                    if not mobile:
                        continue

                    exists = conn.execute(
                        "SELECT id FROM users WHERE mobile=?",
                        (mobile,)
                    ).fetchone()

                    if exists:
                        skipped += 1
                        continue

                    conn.execute("""
                    INSERT INTO users (name,mobile,password,referral_code,points,join_date)
                    VALUES (?,?,?,?,?,?)
                    """, (
                        row.get("Name","User"),
                        mobile,
                        hash_password("temp1234"),
                        generate_code(),
                        int(row.get("Points",0)),
                        datetime.now()
                    ))

                    added += 1

            st.success(f"Added: {added} | Skipped: {skipped}")

    # ========== REPORTS TAB ==========
    with tabs[3]:
        st.subheader("System Report")

        with get_db() as conn:
            total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            total_points = conn.execute("SELECT SUM(points) as s FROM users").fetchone()["s"]

        st.metric("Total Users", total_users)
        st.metric("Total Points", total_points if total_points else 0)
