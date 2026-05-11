import os
import sqlite3
import threading
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request, session

from data_manager import DataManager
from flight_search import FlightSearch
from new_user import NewUser
from notification_manager import NotificationManager

DB_FILE = os.path.join(os.path.dirname(__file__), "users.db")
ORIGIN_CITY = "LON"
ALERT_FREQUENCIES = {"instant", "daily", "weekly"}
CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "\u20b9"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        alert_frequency TEXT DEFAULT 'instant',
        preferred_origin TEXT DEFAULT 'LON',
        max_price INTEGER,
        reset_token TEXT,
        reset_token_expires_at TEXT
    )
    """)

    columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()
    }
    for column_name, definition in {
        "password_hash": "TEXT",
        "alert_frequency": "TEXT DEFAULT 'instant'",
        "preferred_origin": "TEXT DEFAULT 'LON'",
        "max_price": "INTEGER",
        "reset_token": "TEXT",
        "reset_token_expires_at": "TEXT",
    }.items():
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {definition}")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wishlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        city TEXT NOT NULL,
        UNIQUE(email, city)
    )
    """)

    conn.commit()
    conn.close()


init_db()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

data_manager = DataManager()
flight_search = FlightSearch()
new_user = NewUser(DB_FILE)
notification_manager = NotificationManager()

search_results = []
search_status = {"running": False, "done": False}


def bootstrap_users_from_json():
    if new_user.count_users() > 0:
        return

    for user in data_manager.get_emails():
        first_name = user.get("firstName", "").strip()
        last_name = user.get("lastName", "").strip()
        email = user.get("email", "").strip().lower()
        if first_name and last_name and new_user.is_valid_email(email):
            new_user.create_imported_user(first_name, last_name, email)


def build_stats(destinations):
    return {
        "subscriber_count": new_user.count_users(),
        "wishlist_count": new_user.count_wishlist_items(),
        "destination_count": len(destinations),
    }


def current_user():
    email = session.get("user_email")
    if not email:
        return None
    return new_user.get_public_user(email)


bootstrap_users_from_json()


def run_flight_search():
    search_results.clear()
    search_status["running"] = True
    search_status["done"] = False

    sheet_data = data_manager.get_data()
    users = new_user.get_all_users()

    if not users:
        search_status["running"] = False
        search_status["done"] = True
        return

    if sheet_data and sheet_data[0]["iataCode"] == "":
        for row in sheet_data:
            row["iataCode"] = flight_search.get_code(row["city"])
        data_manager.data = sheet_data
        data_manager.update_data()

    tomorrow = datetime.now() + timedelta(days=1)
    six_months_from_today = datetime.now() + timedelta(days=180)
    return_date_initial = tomorrow + timedelta(days=7)
    return_date_last = six_months_from_today + timedelta(days=208)
    origins = sorted({(user.get("preferred_origin") or ORIGIN_CITY).upper() for user in users})

    for origin in origins:
        origin_users = new_user.get_users_by_origin(origin)
        for destination in sheet_data:
            flight = flight_search.search_flights(
                origin,
                destination["iataCode"],
                from_time=tomorrow,
                to_time=six_months_from_today,
                return_to=return_date_last,
                return_from=return_date_initial,
            )

            result = {
                "origin": origin,
                "city": destination["city"],
                "iataCode": destination["iataCode"],
                "threshold": destination["lowestPrice"],
                "found": False,
                "is_deal": False,
            }

            if flight:
                result.update({
                    "found": True,
                    "price": flight.price,
                    "from_city": flight.fly_from_city,
                    "from_airport": flight.fly_from_airport,
                    "to_city": flight.destination_city,
                    "to_airport": flight.destination_airport,
                    "out_date": flight.out_date,
                    "return_date": flight.return_date,
                    "via_city": flight.via_city if flight.via_airport else "",
                    "via_airport": flight.via_airport if flight.via_airport else "",
                    "is_deal": flight.price < destination["lowestPrice"],
                })

                if result["is_deal"]:
                    notify_interested_users(origin_users, result)

            search_results.append(result)

    search_status["running"] = False
    search_status["done"] = True


def notify_interested_users(users, result):
    for user in users:
        if user.get("alert_frequency") != "instant":
            continue

        max_price = user.get("max_price")
        if max_price is not None and result["price"] > max_price:
            continue

        message = (
            "Cheap Flight Alert!\n\n"
            f"Origin: {result['origin']}\n"
            f"From: {result['from_city']} ({result['from_airport']})\n"
            f"To: {result['to_city']} ({result['to_airport']})\n\n"
            f"Price: {CURRENCY_SYMBOL}{result['price']}\n"
            f"Target: {CURRENCY_SYMBOL}{result['threshold']}\n\n"
            f"Dates: {result['out_date']} to {result['return_date']}"
        )
        notification_manager.send_email(user["email"], message)


def render_app_page(active_page="home"):
    destinations = data_manager.get_data()
    return render_template(
        "index.html",
        destinations=destinations,
        stats=build_stats(destinations),
        current_user=current_user(),
        currency_symbol=CURRENCY_SYMBOL,
        active_page=active_page,
    )


@app.route("/")
def index():
    return render_app_page("home")


@app.route("/signup")
def signup_page():
    return render_app_page("signup")


@app.route("/login")
def login_page():
    return render_app_page("login")


@app.route("/settings")
def settings_page():
    return render_app_page("settings")


@app.route("/account-tools")
def account_tools_page():
    return render_app_page("account-tools")


@app.route("/wishlists")
def wishlists_page():
    return render_app_page("wishlists")


@app.route("/tracked-destinations")
def tracked_destinations_page():
    return render_app_page("tracked-destinations")


@app.route("/live-searches")
def live_searches_page():
    return render_app_page("live-searches")


@app.route("/auth/status")
def auth_status():
    return jsonify({"user": current_user()})


@app.route("/api/settings")
def settings():
    user = current_user()
    if not user:
        return jsonify({"error": "Log in to view settings"}), 401
    return jsonify({"user": user})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    user = current_user()
    if not user:
        return jsonify({"error": "Log in to update settings"}), 401

    data = request.get_json() or {}
    alert_frequency = data.get("alertFrequency", "").strip().lower()
    preferred_origin = data.get("preferredOrigin", "").strip().upper()
    max_price_raw = str(data.get("maxPrice", "")).strip()

    if alert_frequency not in ALERT_FREQUENCIES:
        return jsonify({"error": "Choose instant, daily, or weekly alerts"}), 400

    if len(preferred_origin) != 3 or not preferred_origin.isalpha():
        return jsonify({"error": "Preferred origin must be a 3-letter airport code"}), 400

    max_price = None
    if max_price_raw:
        if not max_price_raw.isdigit():
            return jsonify({"error": "Max price must be a whole number"}), 400
        max_price = int(max_price_raw)

    updated_user = new_user.update_preferences(
        user["email"],
        alert_frequency,
        preferred_origin,
        max_price,
    )
    return jsonify({
        "message": "Settings updated.",
        "user": updated_user,
    })


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    first_name = data.get("firstName", "").strip()
    last_name = data.get("lastName", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not first_name or not last_name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if not new_user.is_valid_email(email):
        return jsonify({"error": "Invalid email address"}), 400

    if len(password) < 8:
        return jsonify({"error": "Use at least 8 characters for your password"}), 400

    created = new_user.register_new_user(first_name, last_name, email, password)
    if not created:
        return jsonify({"error": "That email already has an account. Log in instead."}), 409

    session["user_email"] = email
    destinations = data_manager.get_data()
    return jsonify({
        "message": f"Welcome, {first_name}! Your account is ready.",
        "stats": build_stats(destinations),
        "user": current_user(),
    })


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = new_user.authenticate_user(email, password)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_email"] = user["email"]
    return jsonify({
        "message": f"Welcome back, {user['first_name']}.",
        "user": user,
    })


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_email", None)
    return jsonify({"message": "Signed out."})


@app.route("/password-reset/request", methods=["POST"])
def request_password_reset():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if email and new_user.is_valid_email(email):
        token = new_user.create_reset_token(email)
        if token:
            message = (
                "Password Reset Request\n\n"
                "Use this reset token within 30 minutes:\n"
                f"{token}"
            )
            notification_manager.send_email(email, message)

            response = {
                "message": "If the account exists, a password reset token has been prepared.",
            }
            if not notification_manager.email_configured():
                response["resetToken"] = token
            return jsonify(response)

    return jsonify({
        "message": "If the account exists, a password reset token has been prepared.",
    })


@app.route("/password-reset/confirm", methods=["POST"])
def confirm_password_reset():
    data = request.get_json() or {}
    token = data.get("token", "").strip()
    password = data.get("password", "")

    if not token or not password:
        return jsonify({"error": "Reset token and new password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Use at least 8 characters for your password"}), 400

    if not new_user.reset_password(token, password):
        return jsonify({"error": "Invalid or expired reset token"}), 400

    return jsonify({"message": "Password updated. You can now log in."})


@app.route("/account", methods=["DELETE"])
def delete_account():
    user = current_user()
    if not user:
        return jsonify({"error": "Log in to delete your account"}), 401

    data = request.get_json() or {}
    confirmation = data.get("confirmation", "").strip()
    if confirmation != "DELETE":
        return jsonify({"error": "Type DELETE to confirm account deletion"}), 400

    new_user.delete_account(user["email"])
    session.pop("user_email", None)
    destinations = data_manager.get_data()
    return jsonify({
        "message": "Account deleted.",
        "stats": build_stats(destinations),
    })


@app.route("/search", methods=["POST"])
def search():
    if not flight_search.is_configured():
        return jsonify({
            "status": "unavailable",
            "error": "Search is unavailable until KIWI_API_KEY is configured.",
        }), 503

    if search_status["running"]:
        return jsonify({"status": "already_running"})

    thread = threading.Thread(target=run_flight_search, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/search/status")
def search_state():
    return jsonify({
        "running": search_status["running"],
        "done": search_status["done"],
        "results": search_results,
        "count": len(search_results),
    })


@app.route("/wishlist/add", methods=["POST"])
def add_to_wishlist():
    user = current_user()
    if not user:
        return jsonify({"error": "Log in to save wishlist items"}), 401

    data = request.get_json() or {}
    city = data.get("city", "").strip()
    if not city:
        return jsonify({"error": "Destination city is required"}), 400

    created = new_user.add_to_wishlist(user["email"], city)
    if not created:
        return jsonify({"error": f"{city} is already on your wishlist"}), 409

    destinations = data_manager.get_data()
    return jsonify({
        "message": f"{city} saved to your wishlist",
        "wishlist": new_user.get_wishlist(user["email"]),
        "stats": build_stats(destinations),
    })


@app.route("/wishlist")
def get_wishlist():
    user = current_user()
    if not user:
        return jsonify({"error": "Log in to view your wishlist"}), 401
    return jsonify({"wishlist": new_user.get_wishlist(user["email"])})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
