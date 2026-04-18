import streamlit as st
import sqlite3
import hashlib
import random
import string
from datetime import datetime
import pandas as pd
import urllib.parse
import re

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="Ali Mobile Repair - Referral System",
    page_icon="📱",
    layout="wide"
)

# ========== SECURITY HELPERS ==========
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def validate_mobile(mobile: str) -> bool:
    return bool(re.fullmatch(r"03\d{9}", mobile))

# ========== DATABASE ==========
def get_db():
    conn = sqlite3.connect("referral.db", timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    with get_db() as conn:
        c = conn.cursor()

        # USERS
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            points INTEGER DEFAULT 0,
            referred_by_id INTEGER,
            join_date TEXT,
            ip_address TEXT
        )
        """)

        # REFERRAL HISTORY
        c.execute("""
        CREATE TABLE IF NOT EXISTS referral_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_user_id INTEGER,
            points_earned INTEGER,
            referral_date TEXT
        )
        """)

        # DISCOUNT HISTORY
        c.execute("""
        CREATE TABLE IF NOT EXISTS discount_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            points_used INTEGER,
            discount_amount REAL,
            claim_date TEXT,
            status TEXT
        )
        """)

        # NOTIFICATIONS
        c.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
        """)

        # CLICK TRACKING
        c.execute("""
        CREATE TABLE IF NOT EXISTS referral_clicks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referral_code TEXT,
            referrer_id INTEGER,
            ip_address TEXT,
            clicked_at TEXT,
            is_converted INTEGER DEFAULT 0
        )
        """)

        conn.commit()

init_db()

# ========== NOTIFICATIONS ==========
def add_notification(user_id, message):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)",
            (user_id, message, datetime.now().isoformat())
        )

def get_notifications(user_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, message FROM notifications WHERE user_id=? AND is_read=0",
            (user_id,)
        ).fetchall()

def mark_notifications_read(user_id, ids):
    if not ids:
        return
    with get_db() as conn:
        q = ",".join(["?"] * len(ids))
        conn.execute(
            f"UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({q})",
            [user_id] + ids
        )

# ========== REFERRAL ==========
def track_click(ref_code, ip):
    if not ref_code:
        return

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE referral_code=?",
            (ref_code,)
        ).fetchone()

        if user:
            conn.execute("""
            INSERT INTO referral_clicks
            (referral_code, referrer_id, ip_address, clicked_at)
            VALUES (?,?,?,?)
            """, (ref_code, user["id"], ip, datetime.now().isoformat()))

def apply_referral(ref_code, new_user_id, new_user_name):
    with get_db() as conn:
        ref = conn.execute(
            "SELECT id FROM users WHERE referral_code=?",
            (ref_code,)
        ).fetchone()

        if not ref:
            return None

        ref_id = ref["id"]

        # ADD POINTS
        conn.execute(
            "UPDATE users SET points = points + 50 WHERE id=?",
            (ref_id,)
        )

        # HISTORY
        conn.execute("""
        INSERT INTO referral_history
        (referrer_id, referred_user_id, points_earned, referral_date)
        VALUES (?,?,?,?)
        """, (ref_id, new_user_id, 50, datetime.now().isoformat()))

        # MARK CONVERSION
        conn.execute("""
        UPDATE referral_clicks
        SET is_converted=1
        WHERE referral_code=? AND referrer_id=? AND is_converted=0
        """, (ref_code, ref_id))

        add_notification(ref_id, f"🎉 {new_user_name} joined using your code! +50 points")

        return ref_id

# ========== SESSION ==========
def init_session():
    defaults = {
        "logged_in": False,
        "user_id": None,
        "user_name": None,
        "user_code": None,
        "page": "Home"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ========== HEADER ==========
st.title("📱 Ali Mobile Repair Referral System")

# ========== REF TRACK ==========
params = st.query_params
if "ref" in params:
    track_click(params["ref"], "user-ip")

# ========== NAV ==========
menu = ["Home", "Register", "Login"]
if st.session_state.logged_in:
    menu += ["Dashboard"]

page = st.sidebar.selectbox("Menu", menu)
st.session_state.page = page

# ========== HOME ==========
if page == "Home":
    st.subheader("Welcome")
    st.write("Earn points by referring customers.")

# ========== REGISTER ==========
elif page == "Register":
    st.subheader("Register")

    with st.form("reg"):
        name = st.text_input("Name")
        mobile = st.text_input("Mobile")
        pwd = st.text_input("Password", type="password")
        ref = st.text_input("Referral Code")
        ok = st.form_submit_button("Create Account")

    if ok:
        if not name or not mobile or not pwd:
            st.error("All fields required")
        elif not validate_mobile(mobile):
            st.error("Invalid mobile format (03XXXXXXXXX)")
        elif len(pwd) < 4:
            st.error("Weak password")
        else:
            try:
                with get_db() as conn:
                    code = generate_code()
                    conn.execute("""
                    INSERT INTO users
                    (name,mobile,password,referral_code,join_date)
                    VALUES (?,?,?,?,?)
                    """, (name, mobile, hash_password(pwd), code, datetime.now().isoformat()))

                    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                if ref:
                    apply_referral(ref, user_id, name)

                st.success(f"Account created. Your code: {code}")

            except sqlite3.IntegrityError:
                st.error("Mobile already exists")

# ========== LOGIN ==========
elif page == "Login":
    st.subheader("Login")

    mobile = st.text_input("Mobile")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE mobile=?",
                (mobile,)
            ).fetchone()

        if user and user["password"] == hash_password(pwd):
            st.session_state.logged_in = True
            st.session_state.user_id = user["id"]
            st.session_state.user_name = user["name"]
            st.session_state.user_code = user["referral_code"]
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

# ========== DASHBOARD ==========
elif page == "Dashboard":
    if not st.session_state.logged_in:
        st.warning("Login first")
        st.stop()

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (st.session_state.user_id,)
        ).fetchone()

    st.write(f"Welcome {user['name']}")
    st.write(f"Points: {user['points']}")
    st.write(f"Referral Code: {user['referral_code']}")

    link = f"https://yourapp.streamlit.app/?ref={user['referral_code']}"
    st.code(link)

    if st.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
# ========== EXTRA HELPERS ==========
def get_user_stats(user_id):
    with get_db() as conn:
        total_points = conn.execute(
            "SELECT points FROM users WHERE id=?",
            (user_id,)
        ).fetchone()["points"]

        clicks = conn.execute(
            "SELECT COUNT(*) as c FROM referral_clicks WHERE referrer_id=?",
            (user_id,)
        ).fetchone()["c"]

        conversions = conn.execute(
            "SELECT COUNT(*) as c FROM referral_history WHERE referrer_id=?",
            (user_id,)
        ).fetchone()["c"]

    rate = (conversions / clicks * 100) if clicks > 0 else 0
    return total_points, clicks, conversions, rate


def claim_discount(user_id):
    with get_db() as conn:
        user = conn.execute(
            "SELECT points FROM users WHERE id=?",
            (user_id,)
        ).fetchone()

        if not user or user["points"] < 500:
            return False

        conn.execute("""
        INSERT INTO discount_history
        (user_id, points_used, discount_amount, claim_date, status)
        VALUES (?,?,?,?,?)
        """, (user_id, 500, 500, datetime.now().isoformat(), "claimed"))

        conn.execute(
            "UPDATE users SET points = points - 500 WHERE id=?",
            (user_id,)
        )

    add_notification(user_id, "🎁 You claimed 500 PKR discount")
    return True


def get_referral_history(user_id):
    with get_db() as conn:
        return conn.execute("""
        SELECT u.name, rh.points_earned, rh.referral_date
        FROM referral_history rh
        JOIN users u ON rh.referred_user_id = u.id
        WHERE rh.referrer_id=?
        ORDER BY rh.referral_date DESC
        """, (user_id,)).fetchall()


def get_discount_history(user_id):
    with get_db() as conn:
        return conn.execute("""
        SELECT points_used, discount_amount, claim_date
        FROM discount_history
        WHERE user_id=?
        ORDER BY claim_date DESC
        """, (user_id,)).fetchall()


# ========== EXTEND NAV ==========
if st.session_state.logged_in:
    advanced_menu = [
        "Dashboard",
        "Referral History",
        "Discount History",
        "Analytics",
        "Leaderboard"
    ]

    selected = st.sidebar.radio("User Panel", advanced_menu)

    st.session_state.page = selected


# ========== DASHBOARD ==========
if st.session_state.page == "Dashboard":
    if not st.session_state.logged_in:
        st.warning("Login required")
        st.stop()

    st.subheader("User Dashboard")

    points, clicks, conversions, rate = get_user_stats(st.session_state.user_id)

    col1, col2, col3 = st.columns(3)
    col1.metric("Points", points)
    col2.metric("Clicks", clicks)
    col3.metric("Conversion %", f"{rate:.1f}%")

    st.divider()

    st.subheader("Referral Link")
    link = f"https://yourapp.streamlit.app/?ref={st.session_state.user_code}"
    st.code(link)

    st.subheader("Claim Reward")

    if points >= 500:
        if st.button("Claim 500 PKR"):
            if claim_discount(st.session_state.user_id):
                st.success("Discount claimed successfully")
                st.rerun()
    else:
        st.info(f"You need {500 - points} more points")


# ========== REFERRAL HISTORY ==========
elif st.session_state.page == "Referral History":
    st.subheader("Referral History")

    data = get_referral_history(st.session_state.user_id)

    if not data:
        st.info("No referrals yet")
    else:
        for row in data:
            st.write(f"{row['name']} → +{row['points_earned']} ({row['referral_date'][:10]})")


# ========== DISCOUNT HISTORY ==========
elif st.session_state.page == "Discount History":
    st.subheader("Discount History")

    data = get_discount_history(st.session_state.user_id)

    if not data:
        st.info("No discounts used")
    else:
        for row in data:
            st.write(f"{row['claim_date'][:10]} → {row['discount_amount']} PKR")


# ========== ANALYTICS ==========
elif st.session_state.page == "Analytics":
    st.subheader("Referral Analytics")

    points, clicks, conversions, rate = get_user_stats(st.session_state.user_id)

    st.metric("Total Clicks", clicks)
    st.metric("Registrations", conversions)
    st.metric("Conversion Rate", f"{rate:.2f}%")

    st.divider()

    st.subheader("Recent Activity")

    with get_db() as conn:
        logs = conn.execute("""
        SELECT clicked_at, is_converted
        FROM referral_clicks
        WHERE referrer_id=?
        ORDER BY clicked_at DESC
        LIMIT 20
        """, (st.session_state.user_id,)).fetchall()

    if logs:
        for log in logs:
            status = "Converted" if log["is_converted"] else "Pending"
            st.write(f"{log['clicked_at'][:16]} → {status}")
    else:
        st.info("No activity yet")


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

    if not top:
        st.info("No users yet")
    else:
        for i, user in enumerate(top, 1):
            st.write(f"{i}. {user['name']} — {user['points']} pts")
# ========== ADMIN SECURITY ==========
ADMIN_PASSWORD = "Admin51214725"  # move to st.secrets in production

def is_admin():
    return st.session_state.get("admin_logged", False)

def admin_login():
    st.subheader("Admin Login")
    pwd = st.text_input("Enter Admin Password", type="password")

    if st.button("Login as Admin"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.admin_logged = True
            st.success("Admin access granted")
            st.rerun()
        else:
            st.error("Wrong password")


# ========== SAFE USER DELETE ==========
def delete_user(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM referral_history WHERE referrer_id=? OR referred_user_id=?", (user_id, user_id))
        conn.execute("DELETE FROM discount_history WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM referral_clicks WHERE referrer_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))


# ========== RESET PASSWORD ==========
def reset_password(user_id):
    new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed = hash_password(new_pass)

    with get_db() as conn:
        conn.execute("UPDATE users SET password=? WHERE id=?", (hashed, user_id))

    add_notification(user_id, f"🔐 New password: {new_pass}")
    return new_pass


# ========== BULK POINTS ==========
def add_points_all(points):
    with get_db() as conn:
        conn.execute("UPDATE users SET points = points + ?", (points,))


# ========== EXPORT CSV ==========
def export_users_csv():
    with get_db() as conn:
        data = conn.execute("SELECT id,name,mobile,points FROM users").fetchall()

    df = pd.DataFrame(data, columns=["ID", "Name", "Mobile", "Points"])
    return df.to_csv(index=False).encode("utf-8")


# ========== IMPORT CSV ==========
def import_users_csv(file):
    df = pd.read_csv(file)

    added, skipped = 0, 0

    with get_db() as conn:
        for _, row in df.iterrows():
            mobile = str(row.get("mobile", "")).strip()

            if not mobile:
                continue

            exists = conn.execute(
                "SELECT id FROM users WHERE mobile=?",
                (mobile,)
            ).fetchone()

            if exists:
                skipped += 1
                continue

            name = row.get("name", "User")
            points = int(row.get("points", 0))

            conn.execute("""
            INSERT INTO users (name,mobile,password,referral_code,points,join_date)
            VALUES (?,?,?,?,?,?)
            """, (
                name,
                mobile,
                hash_password("temp1234"),
                generate_code(),
                points,
                datetime.now().isoformat()
            ))

            added += 1

    return added, skipped


# ========== REPAIR SYSTEM ==========
def init_repair_table():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS repairs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            issue TEXT,
            created_at TEXT
        )
        """)

init_repair_table()


def add_repair(user_id, issue):
    with get_db() as conn:
        conn.execute("""
        INSERT INTO repairs (user_id, issue, created_at)
        VALUES (?,?,?)
        """, (user_id, issue, datetime.now().isoformat()))


def get_repairs():
    with get_db() as conn:
        return conn.execute("""
        SELECT u.name, u.mobile, r.issue, r.created_at
        FROM repairs r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
        """).fetchall()


# ========== ADMIN PANEL ==========
if "Admin" not in st.session_state.page and is_admin():
    st.session_state.page = "Admin"

if st.session_state.page == "Admin":
    if not is_admin():
        admin_login()
        st.stop()

    st.subheader("Admin Panel")

    tabs = st.tabs([
        "Users",
        "Actions",
        "CSV",
        "Reports",
        "Repairs"
    ])

    # ========== USERS ==========
    with tabs[0]:
        st.subheader("All Users")

        with get_db() as conn:
            users = conn.execute("SELECT id,name,mobile,points FROM users ORDER BY points DESC").fetchall()

        for u in users:
            cols = st.columns([1,3,3,2,2,2])

            cols[0].write(u["id"])
            cols[1].write(u["name"])
            cols[2].write(u["mobile"])
            cols[3].write(u["points"])

            if cols[4].button("Reset", key=f"r_{u['id']}"):
                new_pass = reset_password(u["id"])
                st.success(f"New password: {new_pass}")

            if cols[5].button("Delete", key=f"d_{u['id']}"):
                delete_user(u["id"])
                st.warning("User deleted")
                st.rerun()

            st.divider()

    # ========== ACTIONS ==========
    with tabs[1]:
        st.subheader("Bulk Actions")

        pts = st.number_input("Add points to all users", min_value=0, step=50)

        if st.button("Apply Points"):
            add_points_all(pts)
            st.success("Points added to all users")

    # ========== CSV ==========
    with tabs[2]:
        st.subheader("CSV Tools")

        st.download_button(
            "Download Users CSV",
            export_users_csv(),
            "users.csv",
            "text/csv"
        )

        file = st.file_uploader("Upload CSV", type=["csv"])

        if file and st.button("Import CSV"):
            added, skipped = import_users_csv(file)
            st.success(f"Added: {added}, Skipped: {skipped}")

    # ========== REPORTS ==========
    with tabs[3]:
        st.subheader("System Report")

        with get_db() as conn:
            total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            total_points = conn.execute("SELECT SUM(points) as s FROM users").fetchone()["s"]

        st.metric("Total Users", total_users)
        st.metric("Total Points", total_points if total_points else 0)

    # ========== REPAIRS ==========
    with tabs[4]:
        st.subheader("Repair Requests")

        repairs = get_repairs()

        if not repairs:
            st.info("No repair requests")
        else:
            for r in repairs:
                st.write(f"{r['name']} ({r['mobile']}) → {r['issue']} [{r['created_at'][:16]}]")
