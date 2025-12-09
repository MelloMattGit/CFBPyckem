from flask import Flask, redirect, request, session, url_for, render_template
import requests
import os
from dotenv import load_dotenv
import csv

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

# Function to load team logos from CSV file
def load_team_logos():
    logos = {}
    with open("static/data/logos.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            team_name = row["Team"]
            logo_url = row["Logo"]
            logos[team_name] = logo_url
    return logos

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
    user = session.get("user")
    if not user:
        return redirect(url_for("home"))
    #Include check later to use a stored name of the user
    return f"Welcome, {user['username']}! Your Discord ID is {user['id']}. <a href='/games'>Go to Games</a>"

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# Route for the games page
@app.route("/games")
def games():
    user = session.get("user")
    if not user:
        return redirect(url_for("home"))

    team_logos = load_team_logos()
    teams = {1: ["Clemson", "South Carolina"], 2: ["Alabama", "Auburn"], 3: ["Michigan", "Ohio State"]}
    games = []
    for game_id, (team1, team2) in teams.items():
        games.append({
            "name": f"{team1} vs {team2}",
            "date": "2025-12-10",  # Placeholder date
            "time": "18:00",  # Placeholder time
            "team1": team1,  # Add team1
            "team2": team2,  # Add team2
            "logo1": team_logos.get(team1),
            "logo2": team_logos.get(team2)
        })
    return render_template("games.html", games=games)

# Add a context processor to include user data in all templates
@app.context_processor
def inject_user():
    user = session.get("user")
    return {"user": user}

if __name__ == "__main__":
    app.run(debug=True)