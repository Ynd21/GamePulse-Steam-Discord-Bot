from datetime import datetime
import a2s
import asyncio
from .discord_utils import log_message
import sqlite3

async def query_server(server, max_retries=3):
    address = (server['ServerIP'], server['ServerPort'])
    for attempt in range(max_retries + 1):
        try:
            info = await a2s.ainfo(address)
            players = await a2s.aplayers(address)
            player_names = [player.name for player in players if player.name.strip()]  # Extract player names
            log_message(f"Successfully queried {server['GameName']}. Status: Online, Ping: {info.ping}, Players: {len(players)} - Player Names: {player_names}")
            return {
                'GameName': server['GameName'],
                'Status': 'Online', 
                'Players': len(players), 
                'PlayerNames': player_names,
                'ServerMS': info.ping, # Extract Ping 
                'GameType': info.game  # Assuming 'map' represents the game type or similar attribute
                }
        except Exception as e:
            log_message(f"Error querying {server['GameName']}: {e}")
            if attempt < max_retries:
                log_message(f"Retrying query for {server['GameName']} in 2 seconds (Attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(2)
            else:
                log_message(f"Maximum retry attempts reached for {server['GameName']}")
                return {'GameName': server['GameName'], 'Status': 'Offline', 'Error': f"Max retries reached: {e}"}

async def query_servers():
    # Connect to the SQLite database
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()
    
    # Query server details from the servers table
    cur.execute("SELECT server_ip, server_port, server_name FROM servers")
    rows = cur.fetchall()
    
    # Close the database connection
    conn.close()
    
    # Perform asynchronous queries for each server with retries
    tasks = [query_server({'ServerIP': row[0], 'ServerPort': row[1], 'GameName': row[2]}) for row in rows]
    return await asyncio.gather(*tasks)
