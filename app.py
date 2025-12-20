from flask import Flask, logging, redirect, request, session, url_for, render_template, jsonify
import requests
import os
from dotenv import load_dotenv
import csv
import json
import datetime
import psycopg2.extras
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
    # app.logger.info(f"User data: {user}")
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
        SELECT match_id, home_id, away_id, date, time, home_class, away_class, season, week, season_type
        FROM matchups
        WHERE home_class = 'fbs' AND away_class = 'fbs'
        ORDER BY 
            CASE season_type
                WHEN 'postseason' THEN 1
                WHEN 'regular' THEN 2
                ELSE 3
            END,
            week DESC NULLS LAST, date, time;
    """)
    rows = cursor.fetchall()
    logos_data = load_logos()

    # Transform rows into a list of dictionaries
    games = [
        {
            "match_id": int(row[0]),
            "team1": str(row[2]).strip(),
            "team2": str(row[1]).strip(),
            "date": row[3].strftime("%Y-%m-%d"),
            "time": row[4].strftime("%H:%M"),
            "homeID": str(row[1]).strip(),
            "awayID": str(row[2]).strip(),
            "home_class": row[5],
            "away_class": row[6],
            "season": int(row[7]) if row[7] is not None else None,
            "week": int(row[8]) if row[8] is not None else None,
            "seasonType": str(row[9]).strip() if row[9] is not None else None
        }
        for row in rows
    ]

    # compute weeks (regular season weeks) and detect postseason
    weeks = sorted({g['week'] for g in games if g['week'] is not None and (g.get('seasonType') != 'postseason')}, reverse=True)
    has_postseason = any(g.get('seasonType') == 'postseason' for g in games)

    # Close the database connection
    cursor.close()
    conn.close()

    return render_template("games.html", games=games, logos=logos_data, weeks=weeks, has_postseason=has_postseason)


@app.route('/submit_picks', methods=['POST'])
def submit_picks():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'authentication required'}), 401

    data = request.get_json()
    if not data or 'picks' not in data:
        return jsonify({'error': 'invalid payload, expected JSON with picks array'}), 400

    picks = data['picks']
    if not isinstance(picks, list) or len(picks) == 0:
        return jsonify({'error': 'picks must be a non-empty list'}), 400

    # basic validation
    for p in picks:
        if not isinstance(p, dict) or 'match_id' not in p or 'team_id' not in p:
            return jsonify({'error': 'each pick must include match_id and team_id'}), 400

    # open DB connection
    conn = psycopg2.connect(**{
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT")
    })
    cur = conn.cursor()

    try:
        # Check match start times to prevent picking locked games
        match_ids = [int(p['match_id']) for p in picks]
        cur.execute("SELECT match_id, date, time FROM matchups WHERE match_id = ANY(%s)", (match_ids,))
        rows = cur.fetchall()
        # map match_id -> start datetime
        starts = {}
        for r in rows:
            mid = int(r[0])
            d = r[1]
            t = r[2]
            if d is None:
                continue
            try:
                start_dt = datetime.datetime.combine(d, t) if t is not None else datetime.datetime.combine(d, datetime.time.min)
            except Exception:
                start_dt = datetime.datetime.now()
            starts[mid] = start_dt

        now = datetime.datetime.now()
        for p in picks:
            mid = int(p['match_id'])
            if mid in starts and starts[mid] <= now:
                return jsonify({'error': f'match {mid} already started; picks locked'}), 400

        # upsert user row
        discord_id = int(user['id'])
        cur.execute(
            """
            INSERT INTO users(discord_id, username, global_name, avatar, is_admin, created_at)
            VALUES (%s,%s,%s,%s,COALESCE(%s, FALSE), now())
            ON CONFLICT (discord_id) DO UPDATE SET username = EXCLUDED.username, global_name = EXCLUDED.global_name, avatar = EXCLUDED.avatar
            RETURNING discord_id
            """,
            (discord_id, user.get('username'), user.get('global_name'), user.get('avatar'), user.get('is_admin', False))
        )
        _ = cur.fetchone()

        # Insert/Upsert each pick directly into `picks` table. Conflict key should be (discord_id, match_id).
        for p in picks:
            cur.execute(
                """
                INSERT INTO picks(discord_id, match_id, team_id, side, created_at, updated_at)
                VALUES (%s,%s,%s,%s, now(), now())
                ON CONFLICT (discord_id, match_id) DO UPDATE
                SET team_id = EXCLUDED.team_id,
                    side = EXCLUDED.side,
                    updated_at = now()
                """,
                (discord_id, int(p['match_id']), str(p['team_id']), p.get('side'))
            )

        conn.commit()
        return jsonify({'ok': True}), 200

    except Exception as e:
        conn.rollback()
        app.logger.exception('Error saving picks')
        return jsonify({'error': 'internal server error', 'detail': str(e)}), 500
    finally:
        cur.close()
        conn.close()

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