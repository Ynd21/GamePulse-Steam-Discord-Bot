from flask import Flask, send_from_directory, render_template, request, jsonify, url_for, redirect, session, flash
from functools import wraps
from requests_oauthlib import OAuth2Session
import os
import sqlite3
from datetime import datetime, timedelta
import logging
import configparser  # Import configparser for working with INI files
import re
from oauthlib.oauth2 import OAuth2Error
import requests


# Load configuration from config.ini
def load_config():
    config = configparser.ConfigParser()
    config.read('settings.ini')
    return config

# Save configuration to config.ini
def save_config(config_data):
    with open('settings.ini', 'w') as config_file:
        config_data.write(config_file)

# Load configuration from config.ini
config = load_config()


def get_discord_widget(guild_id):
    response = requests.get(f"https://discord.com/api/guilds/{guild_id}/widget.json")
    if response.status_code == 200:
        widget_data = response.json()
        widget_id = widget_data.get('id')  # Assuming 'id' is the correct key
        return widget_id
    else:
        return None

# Set Werkzeug logger to only display warnings and errors
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

app = Flask(__name__, template_folder='../pages')  # Adjust based on your structure

assets_dir = os.path.join(app.root_path, '../assets')


guild_id = config.get('DISCORD', 'guild_id') 

############################################################## DISCORD OAUTH

app.secret_key = os.urandom(24)  # Use a secure, random secret key

# Your Discord Client ID and Client Secret
CLIENT_ID = config['DISCORD']['client_id']
CLIENT_SECRET = config['DISCORD']['client_secret']
REDIRECT_URI = config['DISCORD']['redirect_uri']
GUILD_ID = config['DISCORD']['guild_id']

# OAuth endpoints given in the Discord API documentation
AUTHORIZATION_BASE_URL = 'https://discord.com/api/oauth2/authorize'
TOKEN_URL = 'https://discord.com/api/oauth2/token'

# This is required for local development without HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

@app.route('/login')
def login():
    discord = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=['identify', 'guilds'])
    authorization_url, _ = discord.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth_redirect'] = request.referrer or url_for('home')
    return redirect(authorization_url)

@app.route('/auth/callback')
def callback():
    if 'error' in request.args:
        # Handle the error scenario here
        flash('Authorization failed. Please try again.', 'error')
        return redirect(url_for('login'))

    discord = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    try:
        token = discord.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET,
                                    authorization_response=request.url)
        session['oauth_token'] = token
        return_to = session.pop('oauth_redirect', url_for('home'))  # Default to index if not set
        return redirect(return_to)
    except OAuth2Error as e:
        # Log the error and provide feedback to the user
        print(e)
        flash('Authorization failed. Please try again.', 'error')
        return redirect(url_for('login'))

def is_user_admin(user_id):
    authorized_user_ids = config['DISCORD']['allowed_user_ids'].split(',')
    authorized_user_ids = [id.strip() for id in authorized_user_ids]  # Remove any leading/trailing whitespace
    return user_id in authorized_user_ids

# Context processor that adds 'is_admin' to the context of all templates
@app.context_processor
def inject_admin_status():
    if 'oauth_token' in session:
        discord = OAuth2Session(config['DISCORD']['client_id'], token=session.get('oauth_token'))
        user_info = discord.get('https://discord.com/api/users/@me').json()
        user_id = str(user_info.get('id'))
        is_admin = is_user_admin(user_id)
    else:
        is_admin = False
    return dict(is_admin=is_admin)

@app.route('/sign-out')
def sign_out():
    # Clear the session
    session.clear()
    
    # Redirect to home page or sign-in page
    return redirect(url_for('home'))  # Assuming 'home' is the function name for your home page view

@app.route('/profile')
def profile():
    if 'oauth_token' not in session:
        # If there's no 'oauth_token' in the session, redirect to login
        return redirect(url_for('login'))
    
    try:
        discord = OAuth2Session(CLIENT_ID, token=session.get('oauth_token'))
        user_info = discord.get('https://discord.com/api/users/@me').json()
        user_id = str(user_info['id'])  # Convert user ID to string for consistency

        if is_user_admin(user_id):
            return 'Welcome, Admin!'  # Proceed to the protected page
        else:
            return render_template('403.html'), 403
    except KeyError:
        # If the token is not present or is invalid, redirect to login
        return redirect(url_for('login'))
    
# Decorator function to require Discord OAuth and admin status
def require_discord_oauth_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'oauth_token' not in session:
            # Redirect to login if there's no OAuth session
            return redirect(url_for('login'))
        
        discord = OAuth2Session(config['DISCORD']['client_id'], token=session.get('oauth_token'))
        user_info = discord.get('https://discord.com/api/users/@me').json()
        user_id = str(user_info.get('id'))  # Ensure string comparison
        
        if not is_user_admin(user_id):
            # Abort with 403 if the user is not authorized
            return render_template('403.html'), 403
        
        return f(*args, **kwargs)
    return decorated_function

##############################################################################
@app.route('/discord-widget')
def discord_widget():
    # Read the guild_id from settings.ini
    config = configparser.ConfigParser()
    config.read('settings.ini')
    guild_id = config['DISCORD']['guild_id']

    # Acquire the widget data from Discord API
    widget_data = get_discord_widget(guild_id)
    if widget_data:
        # Assuming 'id' is present in the widget data. You may need to adjust based on actual API response.
        iframe_src = f"https://discord.com/widget?id={guild_id}&theme=dark"  # widget_id might be guild_id itself
        return render_template('discord_widget.html', iframe_src=iframe_src)
    else:
        return "Discord widget not available", 404

@app.route('/')
def home():
    # Connect to the database
    conn = sqlite3.connect('./bot_storage.db')
    conn.row_factory = sqlite3.Row  # This line is crucial
    cur = conn.cursor()
    
    # Servers Watched
    cur.execute("SELECT COUNT(*) FROM servers")
    servers_watched = cur.fetchone()[0]


    # Fetch the latest news items
    cur.execute('SELECT * FROM latest_news ORDER BY timestamp DESC LIMIT 3')
    latest_news_items = cur.fetchall()

    # Server Status on Home Page
    cur.execute('''
        SELECT s.id, s.server_name, s.server_image,
        r.Server_Status, r.Server_MS, r.Timestamp, r.Game_Type, r.Players_Count
        FROM servers s
        JOIN real_time_status r ON s.server_name = r.Game_Name
    ''')
    server_data = cur.fetchall()

    # Server Average MS
    cur.execute('''
        SELECT AVG(Server_MS) 
        FROM real_time_status;
    ''')
    ms_data = cur.fetchone()[0]  # Get the first item from the tuple, which is the average ms
    if ms_data is not None:
        ms_data = round(ms_data, 2)  # Optionally round the result to 2 decimal places
    else:
        ms_data = "N/A"  # Or some default value or message if there's no data 
    
    # Hour Online Total for Last Day
    cur.execute("""
        SELECT 
            SUM(max_players_online_per_server) AS total_connected_today
        FROM (
            SELECT 
                game_name, 
                MAX(players_online) AS max_players_online_per_server
            FROM online_players
            WHERE date(timestamp) = date('now', 'localtime')
            GROUP BY game_name
        );
    """)
    total_connected_today = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT 
            SUM(max_players_online_per_server) AS total_connected_yesterday
        FROM (
            SELECT 
                game_name, 
                MAX(players_online) AS max_players_online_per_server
            FROM online_players
            WHERE date(timestamp) = date('now', 'localtime', '-1 day')
            GROUP BY game_name
        );                
        """)
    total_connected_yesterday = cur.fetchone()[0] or 0
    
    # Calculate percentage change
    if total_connected_yesterday > 0:
        percentage_change = ((total_connected_today - total_connected_yesterday) / total_connected_yesterday) * 100
    else:
        percentage_change = 0  # Or some default value or message indicating there's no data for comparison
    
    # Connected Players Now
    cur.execute("""
        SELECT player_names FROM online_players
        WHERE timestamp = (SELECT MAX(timestamp) FROM online_players)
    """)
    latest_players = cur.fetchall()
    connected_players_now = ', '.join([name for row in latest_players for name in row if name])
    
    # Number Of Players Online Now
    cur.execute("""
        SELECT SUM(players_online) FROM online_players
        WHERE timestamp = (SELECT MAX(timestamp) FROM online_players)
    """)
    number_of_players_online_now = cur.fetchone()[0] or 0
    
################################################################################

    # Connected Players Now
    cur.execute("""
        SELECT DISTINCT player_names FROM online_players
        WHERE timestamp = (SELECT MAX(timestamp) FROM online_players) AND player_names != ''
    """)
    latest_players = cur.fetchall()
    connected_players_now = ', '.join([name[0] for name in latest_players])

    # Unique Player Names for Today
    cur.execute("""
        SELECT DISTINCT player_names 
        FROM online_players 
        WHERE date(timestamp, 'localtime', '+6 hours') = date('now', 'localtime', 'start of day', '+6 hours')
        AND player_names != '';
    """)
    raw_names_today = [row[0].replace("'s", "").split(", ") for row in cur.fetchall()]
    unique_players_today = {name for sublist in raw_names_today for name in sublist}

    # Unique Player Names for the Last Hour
    cur.execute("""
        SELECT player_names 
        FROM online_players
        WHERE timestamp >= datetime('now', '-1 hour', 'localtime') AND player_names != ''
    """)
    raw_names_last_hour = [row[0].replace("'s", "").split(", ") for row in cur.fetchall()]
    unique_players_last_hour = set(name for sublist in raw_names_last_hour for name in sublist if name)

    # Number Of Unique Players Today
    unique_players_daily_number = len(unique_players_today)

    # Number Of Unique Players Last Hour
    num_unique_players_last_hour = len(unique_players_last_hour)


    ##########################################

    # Get the current date and hour
    current_date = datetime.now().strftime('%Y-%m-%d')
    current_hour = datetime.now().hour

    # Fetch unique logged-in user counts per hour for the current date
    cur.execute("""
        WITH HourlyMaxPerServer AS (
            SELECT
                strftime('%Y-%m-%d %H:00', timestamp) AS hour,
                game_name,
                MAX(players_online) AS max_players_online
            FROM online_players
            WHERE timestamp >= strftime('%Y-%m-%d 00:00:00', 'now', 'localtime') -- Adjust for localtime
            GROUP BY hour, game_name
        )
        SELECT 
            hour,
            SUM(max_players_online) AS total_max_players_online
        FROM HourlyMaxPerServer
        GROUP BY hour
        ORDER BY hour;
    """)
    data = cur.fetchall()

    # Leaderboards
    cur.execute("""
        WITH RECURSIVE split(id, player_name, rest, timestamp, game_name, status) AS (
            SELECT
            ROWID AS id,
            '',
            player_names || ',' AS rest,
            timestamp,
            game_name,
            status
            FROM online_players
            UNION ALL
            SELECT
            id,
            SUBSTR(rest, 0, INSTR(rest, ',')),
            SUBSTR(rest, INSTR(rest, ',') + 1),
            timestamp,
            game_name,
            status
            FROM split
            WHERE rest != ''
        ),
        players AS (
            SELECT
            TRIM(player_name) AS player_name,
            MAX(timestamp) AS last_seen,
            COUNT(*) * 5 AS total_minutes_online,  -- Multiply the count of appearances by 5 to get total minutes
            MAX(status) AS current_status  -- Assumes 'Online' sorts after 'Offline'
            FROM split
            WHERE player_name != ''
            GROUP BY TRIM(player_name)
        ),
        latest_timestamp AS (
            SELECT MAX(timestamp) AS max_timestamp FROM online_players
        )
        SELECT
            p.player_name,
            p.total_minutes_online,  -- Updated to reflect total minutes online
            p.last_seen,
            CASE 
            WHEN p.last_seen = (SELECT max_timestamp FROM latest_timestamp) THEN 'Online'
            ELSE 'Offline'
            END AS status
        FROM players p
        ORDER BY p.total_minutes_online DESC
        LIMIT 10;        
    """)
    leaderboard_data = cur.fetchall()

    # Create the leaderboard with rank numbers
    leaderboard = [(index + 1, entry[0], entry[1], entry[2], entry[3]) for index, entry in enumerate(leaderboard_data)]


    hours = [datetime.strptime(row[0], '%Y-%m-%d %H:%M').strftime('%H:00') for row in data]
    unique_users_per_hour = [row[1] for row in data]

    # Assuming current_hour is correctly determined
    hours_labels = [f"{hour:02d}:00" for hour in range(current_hour + 1)]
    unique_users_data = [unique_users_per_hour[hours.index(label)] if label in hours else 0 for label in hours_labels]

    ############ Weekly User Graph Count None Unique ######################
    # New Query Execution
    cur.execute("""
        SELECT 
            CASE strftime('%w', day)
                WHEN '0' THEN 'Sunday'
                WHEN '1' THEN 'Monday'
                WHEN '2' THEN 'Tuesday'
                WHEN '3' THEN 'Wednesday'
                WHEN '4' THEN 'Thursday'
                WHEN '5' THEN 'Friday'
                WHEN '6' THEN 'Saturday'
            END AS day_of_week,
            SUM(max_daily_players_online) AS total_max_connected_on_day
        FROM (
            SELECT 
                game_name, 
                DATE(timestamp) AS day,
                MAX(players_online) AS max_daily_players_online
            FROM online_players
            WHERE DATE(timestamp) >= date('now', '-7 day')
            GROUP BY game_name, DATE(timestamp)
        ) AS daily_max_per_game
        GROUP BY strftime('%w', day)
        ORDER BY MIN(strftime('%w', day));
    """)
    week_data = cur.fetchall()

    # Prepare data for graphing (example for Chart.js)
    labels = [row[0] for row in week_data]
    values = [row[1] for row in week_data]

    # Adjusted Percentage Calculation From The Last Hour
    cur.execute("SELECT MAX(timestamp) FROM online_players")
    most_recent_timestamp_str = cur.fetchone()[0]
    if most_recent_timestamp_str:
        most_recent_timestamp = datetime.strptime(most_recent_timestamp_str, '%Y-%m-%d %H:%M:%S')
        start_of_most_recent_hour = most_recent_timestamp.replace(minute=0, second=0, microsecond=0)
        start_of_previous_hour = start_of_most_recent_hour - timedelta(hours=1)

        # Calculate the max players_online for the most recent hour
        cur.execute("""
            SELECT MAX(players_online) FROM online_players
            WHERE timestamp >= ? AND timestamp < ?
        """, (start_of_most_recent_hour.strftime('%Y-%m-%d %H:%M:%S'), most_recent_timestamp_str))
        max_current_hour = cur.fetchone()[0] or 0

        # Calculate the max players_online for the previous hour
        cur.execute("""
            SELECT MAX(players_online) FROM online_players
            WHERE timestamp >= ? AND timestamp < ?
        """, (start_of_previous_hour.strftime('%Y-%m-%d %H:%M:%S'), start_of_most_recent_hour.strftime('%Y-%m-%d %H:%M:%S')))
        max_last_hour = cur.fetchone()[0] or 0

        if max_last_hour > 0:
            percentage_change_last_hour = ((max_current_hour - max_last_hour) / max_last_hour) * 100
        else:
            percentage_change_last_hour = float('inf')  # Represents an infinite increase if last hour had 0 players
    else:
        percentage_change_last_hour = "N/A"  # No recent timestamp found

    conn.close()
    
    dynamic_content = {
        'Servers_Watched': servers_watched,
        'Hour_Online_Total_24': total_connected_today,
        'Percentange_Calculated_From_Last_48_Hours': f"{percentage_change:.2f}%",
        'Connected_Players_Now': connected_players_now,
        'Number_Of_Players_Online_Now': number_of_players_online_now,
        'Unique_Player_Names_Today': ", ".join(unique_players_today),
        'Unique_Player_Names_Last_Hour': ", ".join(unique_players_last_hour),
        'unique_players_daily_number': unique_players_daily_number,
        'server_data': server_data,
        'leaderboard': leaderboard,
        'ms_data': ms_data,
        'latest_news_items': latest_news_items,
        'hours_labels': hours_labels,
        'unique_users_data': unique_users_data,
        'Percentage_Calculated_From_Last_Hour': f"{percentage_change_last_hour:.2f}%" if percentage_change_last_hour != "N/A" else "N/A"
    }
    return render_template('index.html', **dynamic_content, labels=labels, values=values)

# Route to display and add news items
@app.route('/latest-news', methods=['GET', 'POST'])
@require_discord_oauth_admin
def latest_news():
    if request.method == 'POST':
        # Add a new news item
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Current time
        text_message = request.form.get('text_message')
        notification_level = request.form.get('notification_level')

        conn = sqlite3.connect('bot_storage.db')
        cur = conn.cursor()
        cur.execute('INSERT INTO latest_news (timestamp, text_message, notification_level) VALUES (?, ?, ?)',
                    (timestamp, text_message, notification_level))
        conn.commit()
        conn.close()

        return redirect(url_for('latest_news'))

    # Display existing news items
    conn = sqlite3.connect('bot_storage.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM latest_news ORDER BY timestamp DESC')
    news_items = cur.fetchall()
    conn.close()

    return render_template('latest_news.html', news_items=news_items)

# Route to edit a news item
@app.route('/edit-news/<int:id>', methods=['POST'])
@require_discord_oauth_admin
def edit_news(id):
    text_message = request.form.get('text_message')
    notification_level = request.form.get('notification_level')

    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()
    cur.execute('UPDATE latest_news SET text_message = ?, notification_level = ? WHERE id = ?',
                (text_message, notification_level, id))
    conn.commit()
    conn.close()

    return redirect(url_for('latest_news'))

# Route to delete a news item
@app.route('/delete-news/<int:id>', methods=['POST'])
@require_discord_oauth_admin
def delete_news(id):
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM latest_news WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('latest_news'))

@app.route('/servers')
@require_discord_oauth_admin
def servers():
    # Connect to the SQLite database
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()

    # Perform a JOIN query to fetch combined server data
    # Now explicitly including the 'id' field from the 'servers' table
    cur.execute('''
    SELECT s.id, s.server_name, s.server_ip, s.server_port, s.server_image, 
    s.server_emoji, s.server_quick_join_url, s.users_title, 
    s.status_embed, s.server_status_channel_id, s.user_online_count_channel_id, 
    r.Server_Status, r.Server_MS, r.Timestamp, r.Game_Type, r.Players_Count
    FROM servers s
    JOIN real_time_status r ON s.server_name = r.Game_Name
    ''')
    server_data = cur.fetchall()

    # Close the database connection
    conn.close()

    # Convert server data into a list of dictionaries for easier handling in the template
    servers = [
        {
            'id': row[0],  # Now including 'id' in the dictionary
            'Server_Name': row[1], 
            'Server_IP': row[2], 
            'Server_Port': row[3], 
            'Server_Image': row[4], 
            'Server_Emoji': row[5], 
            'Server_Quick_Join_URL': row[6], 
            'Users_Title': row[7], 
            'Status_Embed': row[8], 
            'Server_Status_Channel_ID': row[9], 
            'User_Online_Count_Channel_ID': row[10], 
            'Server_Status': row[11], 
            'Server_Last_MS': row[12], 
            'Date_Added': row[13], 
            'Game_Type': row[14], 
            'Players_Count': row[15]
        }
        for row in server_data
    ]

    return render_template('servers.html', servers=servers)


@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(assets_dir, filename)


@app.route('/update-server', methods=['POST'])
@require_discord_oauth_admin
def update_server():
    server_id = request.form.get('server_id')
    server_name = request.form.get('server_name')
    server_ip = request.form.get('server_ip')
    server_port = request.form.get('server_port')
    server_image = request.form.get('server_image')
    server_emoji = request.form.get('server_emoji')
    server_quick_join_url = request.form.get('server_quick_join_url')
    users_title = request.form.get('users_title')
    status_embed = request.form.get('status_embed') == 'true'
    server_status_channel_id = request.form.get('server_status_channel_id')
    user_online_count_channel_id = request.form.get('user_online_count_channel_id')

    # Convert to boolean
    # status_embed = status_embed.lower() in ['true', '1', 't', 'y', 'yes']

    # Ensure numerical fields are correctly converted to integers or handled appropriately if null/None
    try:
        server_port = int(server_port) if server_port else None
        server_status_channel_id = int(server_status_channel_id) if server_status_channel_id else None
        user_online_count_channel_id = int(user_online_count_channel_id) if user_online_count_channel_id else None
    except ValueError:
        # Handle the error or set to None/default values
        pass

    # Connect to your database and update server data
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()

    cur.execute('''
        UPDATE servers
        SET server_name = ?, server_ip = ?, server_port = ?, server_image = ?, 
            server_emoji = ?, server_quick_join_url = ?, users_title = ?, 
            status_embed = ?, server_status_channel_id = ?, user_online_count_channel_id = ?
        WHERE id = ?
    ''', (server_name, server_ip, server_port, server_image, server_emoji, 
         server_quick_join_url, users_title, status_embed, server_status_channel_id, 
         user_online_count_channel_id, server_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/add-server', methods=['POST'])
@require_discord_oauth_admin
def add_server():
    # Extract server details from the form submission
    server_name = request.form.get('server_name')
    server_ip = request.form.get('server_ip')
    server_port = request.form.get('server_port')
    server_image = request.form.get('server_image')
    server_emoji = request.form.get('server_emoji')
    server_quick_join_url = request.form.get('server_quick_join_url')
    users_title = request.form.get('users_title')
    status_embed = request.form.get('status_embed') == 'true'
    server_status_channel_id = request.form.get('server_status_channel_id')
    user_online_count_channel_id = request.form.get('user_online_count_channel_id')

    # Connect to the SQLite database
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()

    # Insert new server details into the database
    cur.execute('''
        INSERT INTO servers (server_name, server_ip, server_port, server_image, 
        server_emoji, server_quick_join_url, users_title, status_embed, 
        server_status_channel_id, user_online_count_channel_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (server_name, server_ip, server_port, server_image, server_emoji, 
         server_quick_join_url, users_title, status_embed, 
         server_status_channel_id, user_online_count_channel_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/delete-server/<int:server_id>', methods=['POST'])
@require_discord_oauth_admin
def delete_server(server_id):
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM servers WHERE id = ?', (server_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/database')
@require_discord_oauth_admin
def database():
    # Connect to the SQLite database
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()

    # Fetch data from the online_players table along with the server image from the servers table
    cur.execute("""
        SELECT 
            op.game_name,
            COUNT(op.game_name) AS num_records,
            MAX(op.players_online) AS highest_player_online_count,
            MIN(op.timestamp) AS first_timestamp,
            MAX(op.timestamp) AS last_timestamp,
            COALESCE(s.server_image, 'https://cdn-icons-png.flaticon.com/512/954/954991.png') AS server_image,
            s.server_name IS NULL AS is_abandoned
        FROM online_players op
        LEFT JOIN servers s ON op.game_name = s.server_name
        GROUP BY op.game_name;
    """)
    database_data = cur.fetchall()

    # Close the database connection
    conn.close()

    # Prepare the data for rendering
    formatted_data = []
    for row in database_data:
        formatted_entry = {
            'Server_Image': row[5],  # Server image from the join result or default image
            'Server_Name': row[0],
            'Num_Records': row[1],
            'Highest_Player_Online_Count': row[2],
            'First_Timestamp': row[3],
            'Last_Timestamp': row[4],
            'Is_Abandoned': row[6]  # Flag indicating whether the server is abandoned
        }
        formatted_data.append(formatted_entry)

    return render_template('database.html', database_data=formatted_data)

@app.route('/remove-data/<string:server_name>/<string:days>', methods=['POST'])
@require_discord_oauth_admin
def remove_data(server_name, days):
    # Connect to the SQLite database
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()

    if days == '-1':
        # Execute the DELETE query to remove all data for the specified server name
        cur.execute("""
            DELETE FROM online_players
            WHERE game_name = ?
        """, (server_name,))
    else:
        try:
            days_int = int(days)
            if days_int < 0:
                raise ValueError("Days parameter must be a non-negative integer or '-1'")
            # Calculate the date threshold for removal based on the specified days
            threshold_date = datetime.now() - timedelta(days=days_int)

            # Execute the DELETE query to remove data from online_players table
            cur.execute("""
                DELETE FROM online_players
                WHERE game_name = ? AND timestamp >= ?
            """, (server_name, threshold_date))
        except ValueError:
            return jsonify({'error': 'Invalid days parameter'}), 400

    # Commit the transaction and close the database connection
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# Define the route to fetch user count data for the last 7 days
@app.route('/user-count-data/<int:server_id>')
@require_discord_oauth_admin
def user_count_data(server_id):
    try:
        # Connect to the database
        conn = sqlite3.connect('bot_storage.db')
        cursor = conn.cursor()
        
        # Calculate the date 7 days ago from today
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Fetch user count data for the specified server ID and last 7 days
        cursor.execute("""
            SELECT op.timestamp, op.players_online 
            FROM online_players op
            JOIN servers s ON op.game_name = s.server_name
            WHERE s.id = ? AND op.timestamp >= ?
            """, (server_id, start_date))
        rows = cursor.fetchall()
        
        # Extract timestamps and player counts from the database rows
        timestamps = [row[0] for row in rows]
        player_counts = [row[1] for row in rows]
        
        # Close the database connection
        conn.close()
        
        # Return the user count data as JSON
        return jsonify({'timestamps': timestamps, 'playerCounts': player_counts})
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/logs')
@require_discord_oauth_admin
def get_logs():
    log_file_path = "./logging.txt"
    processed_logs = []
    with open(log_file_path, "r", encoding='utf-8') as file:
        logs = file.readlines()[-300:]
    for line in logs:
        # Split the line into parts based on your log structure
        parts = line.split(' - ', 2)  # Split into at most three parts
        if len(parts) >= 3:
            timestamp, level, text = parts
            if "WARNING" in level:
                level = "<span class='log-level-warning'>WARNING</span>"
            elif "INFO" in level:
                level = "<span class='log-level-info'>INFO</span>"
            else:
                level = "<span class='log-text-error'>ERROR</span>"
            processed_line = f"<span class='timestamp'>{timestamp}</span> - {level} - <span class='log-text'>{text}</span>"
            processed_logs.append(processed_line)
        else:
            # If the line doesn't have the expected structure, display it as is
            processed_logs.append(f"<span class='log-text'>{line}</span>")
    return render_template('logs.html', logs=processed_logs)


@app.route('/settings', methods=['GET', 'POST'])
@require_discord_oauth_admin
def settings():
    config = configparser.ConfigParser()
    config.read('settings.ini')

    if request.method == 'POST':
        # Clear the current configuration to handle deletions
        config.clear()

        # Extract sections from the form. Each section is expected to have a unique name.
        sections = request.form.getlist('section_name')
        for section in sections:
            if not config.has_section(section):
                config.add_section(section)
            
            # For each section, find its keys and values
            for key in request.form.getlist(f'{section}_key[]'):
                value_index = request.form.getlist(f'{section}_key[]').index(key)
                value = request.form.getlist(f'{section}_value[]')[value_index]
                if key:  # Make sure the key is not empty
                    config.set(section, key, value)

        save_config(config)
        return redirect(url_for('settings'))

    return render_template('settings.html', config=config)

@app.route('/errors')
@require_discord_oauth_admin
def display_errors():
    logs = []

    # Read the log file with UTF-8 encoding and extract warnings and errors
    with open('logging.txt', 'r', encoding='utf-8') as file:
        for line in file:
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - (WARNING|ERROR) - (.+)', line)
            if match:
                timestamp, flag, text = match.groups()
                logs.append({'timestamp': timestamp, 'flag': flag, 'text': text})

    return render_template('errors.html', logs=logs)


def run():
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)

if __name__ == "__main__":
    run()
