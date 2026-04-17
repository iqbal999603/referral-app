# ===== 🔐 SECURE IMPORTS =====
import streamlit as st
import sqlite3
import bcrypt
import random
import string
from datetime import datetime, timedelta
import pandas as pd
import urllib.parse
import re
import time
import os

# ===== PAGE CONFIG (UNCHANGED UI) =====
st.set_page_config(page_title="Ali Mobile Repair - Referral System", page_icon="📱", layout="wide")

# ===== DATABASE (SECURE) =====
def get_db_connection():
    conn = sqlite3.connect('referral.db', check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            mobile TEXT UNIQUE,
            password BLOB,
            referral_code TEXT UNIQUE,
            points INTEGER DEFAULT 0,
            referred_by_id INTEGER,
            join_date TEXT,
            ip_address TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS referral_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_user_id INTEGER,
            points_earned INTEGER,
            referral_date TEXT,
            UNIQUE(referrer_id, referred_user_id)
        )''')

init_db()

# ===== SECURITY =====
def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt())

def check_password(pwd, hashed):
    return bcrypt.checkpw(pwd.encode(), hashed)

def generate_unique_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_ip():
    try:
        return st.context.headers.get("X-Forwarded-For", "local")
    except:
        return "local"

# ===== RATE LIMIT =====
_rate_store = {}

def rate_limit(key, limit=5, per_seconds=60):
    now = time.time()
    if key not in _rate_store:
        _rate_store[key] = []

    _rate_store[key] = [t for t in _rate_store[key] if now - t < per_seconds]

    if len(_rate_store[key]) >= limit:
        return False

    _rate_store[key].append(now)
    return True

# ===== SESSION =====
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None

# ===== UI HEADER (ORIGINAL STYLE) =====
st.markdown("""
<div style="background:#1e3c72; padding:15px; border-radius:10px; text-align:center; color:white;">
<h1>📱 Ali Mobiles Repairing</h1>
<p>Referral & Discount System</p>
</div>
""", unsafe_allow_html=True)

# ===== NAVIGATION =====
menu = ["🏠 Home", "✨ Register", "🔐 Login", "📊 Dashboard"]
page = st.selectbox("Navigate", menu)

# ===== REGISTER =====
if page == "✨ Register":
    st.subheader("New Registration")

    name = st.text_input("Name")
    mobile = st.text_input("Mobile")
    password = st.text_input("Password", type="password")
    ref_code = st.text_input("Referral Code")

    if st.button("Register"):
        if not rate_limit(f"reg_{mobile}", 3):
            st.error("Too many attempts")
            st.stop()

        if not re.match(r'^[0-9]{10,15}$', mobile):
            st.error("Invalid mobile")
            st.stop()

        with get_db_connection() as conn:
            c = conn.cursor()

            c.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
            if c.fetchone():
                st.error("Already registered")
                st.stop()

            conn.execute("BEGIN IMMEDIATE")

            try:
                new_code = generate_unique_code()
                hashed = hash_password(password)
                referrer_id = None

                if ref_code:
                    c.execute("SELECT id FROM users WHERE referral_code=?", (ref_code,))
                    r = c.fetchone()
                    if r:
                        referrer_id = r[0]
                        c.execute("UPDATE users SET points = points + 50 WHERE id=?", (referrer_id,))

                # Insert new user
                c.execute("""
                INSERT INTO users (name, mobile, password, referral_code, referred_by_id, join_date, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    name,
                    mobile,
                    hashed,
                    new_code,
                    referrer_id,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    get_ip()
                ))

                user_id = c.lastrowid

                # Safe referral history
                if referrer_id:
                    c.execute("""
                    INSERT INTO referral_history (referrer_id, referred_user_id, points_earned, referral_date)
                    VALUES (?, ?, ?, ?)
                    """, (referrer_id, user_id, 50, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                conn.commit()
                st.success(f"Registered! Code: {new_code}")

            except Exception as e:
                conn.rollback()
                st.error(f"Error: {e}")

# ===== LOGIN =====
elif page == "🔐 Login":
    st.subheader("Login")

    mobile = st.text_input("Mobile")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if not rate_limit(f"login_{mobile}", 5):
            st.error("Too many attempts")
            st.stop()

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE mobile=?", (mobile,))
            user = c.fetchone()

        if user and check_password(password, user[3]):
            st.session_state.logged_in = True
            st.session_state.user_id = user[0]
            st.session_state.user_name = user[1]
            st.success("Login successful")
        else:
            st.error("Invalid credentials")

# ===== DASHBOARD =====
elif page == "📊 Dashboard":
    if not st.session_state.logged_in:
        st.warning("Login first")
        st.stop()

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name, referral_code, points FROM users WHERE id=?", (st.session_state.user_id,))
        user = c.fetchone()

    st.subheader(f"Welcome {user[0]}")
    st.write(f"Points: {user[2]}")
    st.write(f"Referral Code: {user[1]}")

    referral_link = f"http://localhost:8501/?ref={user[1]}"
    st.code(referral_link)

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

# ===== HOME =====
else:
    st.write("Welcome to Secure Referral System")
