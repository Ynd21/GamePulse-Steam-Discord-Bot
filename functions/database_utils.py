import sqlite3

def create_table(conn, create_table_sql):
    """
    Create a table from the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except sqlite3.Error as e:
        print(e)

def create_database():
    # Database connection
    database = 'bot_storage.db'

    # SQL statements for creating tables
    table_definitions = {
        'servers': '''
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
        ''',
        'embed_ids': '''
            CREATE TABLE IF NOT EXISTS embed_ids (
                embed_name TEXT NOT NULL,
                message_id TEXT NOT NULL
            )
        ''',
        'online_players': '''
            CREATE TABLE IF NOT EXISTS online_players (
                timestamp TEXT,
                game_name TEXT,
                players_online INTEGER,
                player_names TEXT,
                status TEXT
            )
        ''',
        'real_time_status': '''
            CREATE TABLE IF NOT EXISTS real_time_status (
                Game_Name TEXT NOT NULL,
                Server_Status TEXT NOT NULL,
                Server_MS INTEGER,
                Timestamp TEXT NOT NULL,
                Game_Type TEXT,
                Players_Count INTEGER
            )
        ''',
        'latest_news': '''
            CREATE TABLE IF NOT EXISTS latest_news (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                text_message TEXT,
                notification_level TEXT
            )
        '''
    }

    # Adjusted function call in the create_database function
    with sqlite3.connect(database) as conn:
        for table_name, create_table_sql in table_definitions.items():
            create_table(conn, create_table_sql)
            print(f"Ensured table {table_name} exists.")