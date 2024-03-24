import sqlite3
import discord
from .discord_utils import get_user_title, log_message

# Global dictionary to cache server statuses and player counts
server_cache = {}

async def update_voice_channels(bot, query_results):
    global server_cache

    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()

    for result in query_results:
        server_name = result['GameName']
        cur.execute("SELECT server_status_channel_id, user_online_count_channel_id FROM servers WHERE server_name = ?", (server_name,))
        row = cur.fetchone()
        if row:
            online_channel_id, user_count_channel_id = row
            status = result['Status']
            players = result.get('Players', 0)

            # Cache key adjustments for separate tracking
            status_cache_key = f"{server_name}_status"
            players_cache_key = f"{server_name}_players"

            # Determine if an update is needed
            status_update_needed = server_cache.get(status_cache_key) != status
            players_update_needed = server_cache.get(players_cache_key) != players

            # Status channel update logic
            if online_channel_id:
                if status_update_needed:
                    online_text = "Status: 🟢" if status == "Online" else "Status: 🔴"
                    try:
                        online_channel = await bot.fetch_channel(online_channel_id)
                        await online_channel.edit(name=online_text)
                        log_message(f"{server_name} Status Channel Updated to {online_text}. Cache updated.")
                        server_cache[status_cache_key] = status
                    except discord.HTTPException as e:
                        log_message(f"Error updating {server_name} status channel: {e}")
                    except Exception as e:
                        log_message(f"Error updating {server_name} status channel: {e}")
                else:
                    log_message(f"Skipped updating {server_name} status channel. Status unchanged ({status}).")

            # Players channel update logic
            if user_count_channel_id:
                if players_update_needed:
                    game_name = result['GameName']
                    user_title = await get_user_title(game_name)  # Retrieve user_title from the database
                    survivors_text = f"{user_title}: {players}" if status == "Online" else "N/A"
                    try:
                        user_count_channel = await bot.fetch_channel(user_count_channel_id)
                        await user_count_channel.edit(name=survivors_text)
                        log_message(f"{server_name} User Count Channel Updated to {survivors_text}. Cache updated.")
                        server_cache[players_cache_key] = players
                    except discord.HTTPException as e:
                        log_message(f"Error updating {server_name} user count channel: {e}")
                    except Exception as e:
                        log_message(f"Error updating {server_name} user count channel: {e}")
                else:
                    log_message(f"Skipped updating {server_name} user count channel. Player count unchanged ({players}).")

    conn.close()