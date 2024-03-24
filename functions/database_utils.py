import sqlite3

def create_database():
    # Connect to the SQLite database. This will create the database file if it doesn't exist.
    conn = sqlite3.connect('bot_storage.db')
    
    # Create a cursor object
    cur = conn.cursor()
    
    # Create the 'servers' table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS servers (
        id INTEGER PRIMARY KEY,
        server_name TEXT NOT NULL,
        server_ip TEXT NOT NULL,
        server_port INTEGER NOT NULL,
        server_emoji TEXT,
        server_quick_join_url TEXT,
        users_title TEXT,
        status_embed BOOLEAN NOT NULL,
        server_status_channel_id INTEGER,
        user_online_count_channel_id INTEGER,
        server_image TEXT
    )
    ''')
    
    # Create the 'embed_ids' table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS embed_ids (
        embed_name TEXT NOT NULL,
        message_id TEXT NOT NULL
    )
    ''')

    # Create the 'online_players' table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS online_players (
	    timestamp TEXT,
	    game_name TEXT,
	    players_online INTEGER,
	    player_names TEXT,
	    status TEXT
    )
    ''')

    # Create the 'real_time_stats' table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS "real_time_status" (
        "Game_Name" TEXT NOT NULL,
        "Server_Status" TEXT NOT NULL,
        "Server_MS" INTEGER,
        "Timestamp" TEXT NOT NULL,
        "Game_Type" TEXT,
        "Players_Count" INTEGER
    );
    ''')

    # Create the 'latest_news' table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS "latest_news" (
	    id INTEGER PRIMARY KEY,
        timestamp TEXT,
	    text_message TEXT,
	    notification_level TEXT
    );
    ''')        
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()