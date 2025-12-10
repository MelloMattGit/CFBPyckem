from flask import Flask, logging, redirect, request, session, url_for, render_template
import requests
import os
from dotenv import load_dotenv
import csv
import psycopg2

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

load_dotenv()

# Discord OAuth2 credentials
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5000/callback"
DISCORD_API_BASE = "https://discord.com/api"
AUTHORIZATION_BASE_URL = f"{DISCORD_API_BASE}/oauth2/authorize"
TOKEN_URL = f"{DISCORD_API_BASE}/oauth2/token"
USER_URL = f"{DISCORD_API_BASE}/users/@me"

_logos_cache = None

# Function to load team logos from CSV file
def load_team_logos():
    logos = {}
    with open("static/data/logos.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            team_name = row["Team"]
            logo_url = row["Logo"]
            logos[team_name] = logo_url
    return _logos_cache

import csv

# new function using logos.txt
def load_logos():
    global _logos_cache
    if _logos_cache is None:
        _logos_cache = {}
        with open("static/data/logos", mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                id = row['id']
                _logos_cache[id] = {
                    'color': row['color'],
                    'logo': row['logo'],
                    'dark_logo': row['logos[1]'],
                    'abbrev': row['abbreviation'],
                    'mascot': row['mascot']
                }
    return _logos_cache

# Home/Welcome/Login page
@app.route("/")
def home():
    return render_template("home.html")

# Redirect to Discord OAuth2 login
@app.route("/login")
def login():
    discord_login_url = (
        f"{AUTHORIZATION_BASE_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify"
    )
    return redirect(discord_login_url)

# Handle Discord OAuth2 callback
@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed.", 400

    # Exchange code for access token
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=data, headers=headers)
    if response.status_code != 200:
        return "Failed to retrieve access token.", 400

    access_token = response.json().get("access_token")

    # Fetch user details
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(USER_URL, headers=headers)
    if user_response.status_code != 200:
        return "Failed to fetch user details.", 400

    user_data = user_response.json()
    session["user"] = user_data  # Store user data in session
    return redirect(url_for("dashboard"))

# Dashboard page (after login)
@app.route("/dashboard")
def dashboard():
    user = session.get("user")  # Ensure user data is passed
    return render_template("dashboard.html", user=user)

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# Route for the games page
@app.route("/games")
def games():
    user = session.get("user")
    app.logger.info(f"User data: {user}")
    if not user:
        return redirect(url_for("home"))

    # Connect to the database
    conn = psycopg2.connect(**{
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT")
    })
    cursor = conn.cursor()

    # Fetch games from the database, excluding those where either team's classification is not 'fbs'
    cursor.execute("""
        SELECT match_id, home_id, away_id, date, time, home_class, away_class
        FROM matchups
        WHERE home_class = 'fbs' AND away_class = 'fbs';
    """)
    rows = cursor.fetchall()
    logos_data = load_logos()

    # Transform rows into a list of dictionaries
    games = [
        {
            "date": row[3].strftime("%Y-%m-%d"),
            "time": row[4].strftime("%H:%M"),
            "homeID": str(row[1]).strip(),
            "awayID": str(row[2]).strip(),
            "home_class": row[5],
            "away_class": row[6]
        }
        for row in rows
    ]

    # Close the database connection
    cursor.close()
    conn.close()

    return render_template("games.html", games=games, logos=logos_data)

# Add a context processor to include user data in all templates
@app.context_processor
def inject_user():
    user = session.get("user")
    if user:
        if user.get('avatar'):
            user['avatar_url'] = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
        else:
            discriminator = int(user.get('discriminator', 0))
            user['avatar_url'] = f"https://cdn.discordapp.com/embed/avatars/{discriminator % 5}.png"
    return {"user": user}

if __name__ == "__main__":
    app.run(debug=True)