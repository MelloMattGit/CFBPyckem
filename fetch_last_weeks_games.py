import cfbd
import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()


# Database configuration
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# CFBD API configuration
API_KEY = os.getenv("CFBD_API_KEY")  # Replace with your actual API key

# Initialize the CFBD API client
configuration = cfbd.Configuration(
    access_token=API_KEY
)
configuration.api_key["Authorization"] = API_KEY
configuration.api_key_prefix["Authorization"] = "Bearer"
api_client = cfbd.ApiClient(configuration)
games_api = cfbd.GamesApi(api_client)

def fetch_last_weeks_games():
    # Calculate last week's date range
    today = datetime.now()
    last_week = today - timedelta(weeks=1)
    year = 2025
    seasonType = "postseason"  # ISO week number

    try:
        # Fetch games for last week
        games = games_api.get_games(year=year)
        print(f"Fetched {len(games)} games")
        return games
    except cfbd.ApiException as e:
        print(f"Failed to fetch games: {e}")
        return []

def store_games_in_db(games):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    print(f"Storing {len(games)} games")
    for game in games:
        try:
            cursor.execute("""
                INSERT INTO matchups (match_id, team1, team2, date, time, home_class, away_class, home_id, away_id, week, season, seasonType)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id) DO UPDATE
                SET team1 = EXCLUDED.team1,
                    team2 = EXCLUDED.team2,
                    date = EXCLUDED.date,
                    time = EXCLUDED.time,
                    home_class = EXCLUDED.home_class,
                    away_class = EXCLUDED.away_class,
                    home_id = EXCLUDED.home_id,
                    away_id = EXCLUDED.away_id,
                    week = EXCLUDED.week,
                    season = EXCLUDED.season,
                    seasonType = EXCLUDED.seasonType;
            """, (
                game.id,  # Match ID
                game.home_team,  # Home team
                game.away_team,  # Away team
                game.start_date.date(),  # Extract the date
                game.start_date.time(),  # Extract the time
                game.home_classification,
                game.away_classification,
                game.home_id,
                game.away_id,
                game.week,
                game.season,
                game.season_type
            ))
        except Exception as e:
            print(f"Error storing game {game.id}: {e}")

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    games = fetch_last_weeks_games()
    if games:
        store_games_in_db(games)
        print(f"Stored {len(games)} games in the database.")