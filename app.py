# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random

app = Flask(__name__)
app.secret_key = "super_secret_key_here"   # change this in production

# MySQL Configuration (update with your MySQL credentials)
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "jyothi",
    "database": "bank_db"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("You must log in first!", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def generate_account_number():
    return "AC" + str(random.randint(1000000000, 9999999999))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"].lower()
        password = generate_password_hash(request.form["password"])
        phone = request.form.get("phone")
        address = request.form.get("address")
        dob = request.form.get("dob")

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already registered. Try login!", "danger")
                return redirect(url_for("signup"))

            cursor.execute(
                "INSERT INTO users (full_name,email,password,phone,address,dob) VALUES (%s,%s,%s,%s,%s,%s)",
                (full_name, email, password, phone, address, dob),
            )
            conn.commit()
            user_id = cursor.lastrowid

            acct_num = generate_account_number()
            cursor.execute(
                "INSERT INTO accounts (user_id,account_number,balance) VALUES (%s,%s,%s)",
                (user_id, acct_num, 0.0),
            )
            conn.commit()

            flash("Signup successful. Please login.", "success")
            return redirect(url_for("login"))
        except Error as e:
            flash(f"MySQL Error: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "danger")
        cursor.close()
        conn.close()
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    cursor.execute("SELECT * FROM accounts WHERE user_id=%s", (session["user_id"],))
    account = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template("dashboard.html", user=user, account=account)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == "POST":
        full_name = request.form["full_name"]
        phone = request.form["phone"]
        address = request.form["address"]
        dob = request.form["dob"]

        cursor.execute(
            "UPDATE users SET full_name=%s, phone=%s, address=%s, dob=%s WHERE id=%s",
            (full_name, phone, address, dob, session["user_id"]),
        )
        conn.commit()
        session["full_name"] = full_name
        flash("Profile updated!", "success")
        return redirect(url_for("profile"))

    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template("profile.html", user=user)


@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM accounts WHERE user_id=%s", (session["user_id"],))
    account = cursor.fetchone()

    if request.method == "POST":
        action = request.form["action"]
        amount = float(request.form["amount"])
        description = request.form.get("description", "")

        if action == "deposit":
            new_balance = float(account["balance"]) + float(amount)
            cursor.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_balance, account["id"]))
            cursor.execute(
                "INSERT INTO transactions (account_id,type,amount,description) VALUES (%s,%s,%s,%s)",
                (account["id"], "deposit", float(amount), description),
            )
            conn.commit()
            flash(f"Deposited ₹{amount}", "success")

        elif action == "withdraw":
            if float(account["balance"]) < float(amount):
                flash("Insufficient balance", "danger")
            else:
                new_balance = float(account["balance"]) - float(amount)
                cursor.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_balance, account["id"]))
                cursor.execute(
                    "INSERT INTO transactions (account_id,type,amount,description) VALUES (%s,%s,%s,%s)",
                    (account["id"], "withdraw", float(amount), description),
                )
                conn.commit()
                flash(f"Withdrew ₹{amount}", "warning")

        return redirect(url_for("transactions"))

    cursor.execute("SELECT * FROM transactions WHERE account_id=%s ORDER BY created_at DESC", (account["id"],))
    transactions = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("transactions.html", account=account, transactions=transactions)


if __name__ == "__main__":
    app.run(debug=True)
