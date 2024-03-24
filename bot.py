import discord
import configparser
import aiosqlite
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from functions.server_queries import query_servers
from functions.discord_utils import update_discord_message, update_bot_presence
from functions.database_utils import create_database
from functions.update_voice_channels import update_voice_channels 
import logging
import sqlite3
from functions.discord_utils import log_message
import threading
from functions.webserver import run as run_webserver
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO


#### Logging
logging.basicConfig(level=logging.ERROR)


# Load settings from settings.ini
config = configparser.ConfigParser()
config.read('settings.ini')
TOKEN = config['DISCORD']['TOKEN']
CHANNEL_ID = int(config['DISCORD']['CHANNEL_ID'])
GUILD_ID = int(config['DISCORD']['GUILD_ID'])
bot_version = config['DISCORD']['bot_version']
ALLOWED_USER_IDS = [int(user_id.strip()) for user_id in config['DISCORD']['Allowed_User_IDs'].split(',')]


###### Create That DB baby!
create_database()

#################
bot = discord.Bot()

class AddServerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@bot.command(name="add")
async def add(ctx, 
              server_name: str,
              server_ip: str,
              server_port: int,
              server_image: str = "",  # Provide a default value and move before parameters with default values
              server_emoji: str = "",
              server_quick_join_url: str = "",
              users_title: str = "",
              status_embed: str = "No",
              server_status_channel_id: int = "",
              user_online_count_channel_id: int = ""):
    await ctx.defer(ephemeral=True)
    if ctx.author.id in ALLOWED_USER_IDS:
        # Convert status_embed from Yes/No to boolean
        status_embed_bool = True if status_embed.lower() == "yes" else False

        # Insert the new server into the database
        conn = sqlite3.connect('bot_storage.db')
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO servers (
                    server_name, server_ip, server_port, server_emoji, server_quick_join_url,
                    users_title, status_embed, server_status_channel_id, user_online_count_channel_id, server_image
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
              server_name, server_ip, server_port, server_emoji, server_quick_join_url,
             users_title, status_embed_bool, server_status_channel_id, user_online_count_channel_id, server_image
            ))
            conn.commit()
            await ctx.respond(f"Server '{server_name}' added successfully.")
        except sqlite3.Error as e:
            await ctx.respond(f"Failed to add server '{server_name}': {e}")
        finally:
            conn.close()
    else:
        await ctx.respond("You don't have permission to use this command.")



@bot.command(name="remove")
async def remove(ctx, server_name: str):
    await ctx.defer(ephemeral=True)
    # Check if the user is a server admin or has an allowed user ID
    if ctx.author.id in ALLOWED_USER_IDS:
        # Delete the server from the database
        conn = sqlite3.connect('bot_storage.db')
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM servers WHERE server_name = ?", (server_name,))
            conn.commit()
            await ctx.respond(f"Server '{server_name}' removed successfully.")
        except sqlite3.Error as e:
            await ctx.respond(f"Failed to remove server '{server_name}': {e}")
        finally:
            conn.close()
    else:
        await ctx.respond("You don't have permission to use this command.")

@bot.command(name='trigger')
async def manual_update(ctx):
    await ctx.defer(ephemeral=True)
    if ctx.author.id in ALLOWED_USER_IDS:
        query_results = await query_servers()
        await update_discord_message(bot, CHANNEL_ID, query_results)
        await update_bot_presence(bot, query_results)
        await update_voice_channels(bot, query_results)
        await ctx.respond(f"Manual Updates Ran!")
        log_message("Manual update triggered.")
    else:
        await ctx.respond("You don't have permission to use this command.")    

@bot.event
async def on_ready():
    query_and_update.start()
    # Await the setup coroutine from add_server.py
    bot.add_cog(AddServerCog(bot))
    threading.Thread(target=run_webserver, daemon=True).start()
    # Set bot's Avatar
    with open(config['DISCORD']['avatar'], 'rb') as f:
        avatar = f.read()
    await bot.user.edit(avatar=avatar)
    
    # Set bot's username
    bot_username = config['DISCORD'].get('bot_username')
    if bot_username:
        await bot.user.edit(username=bot_username)    
    log_message(f'{bot.user} has connected to Discord!')

@tasks.loop(minutes=2) # Adjust the timing as needed
async def query_and_update():
    log_message("Query and update loop started! Leeeeeets get'er done!")
    query_results = await query_servers()
    await update_discord_message(bot, CHANNEL_ID, query_results)
    await update_bot_presence(bot, query_results)
    await update_voice_channels(bot, query_results)

    # Round down the current time to the nearest 5 minutes
    current_time = datetime.now()
    rounded_time = current_time - timedelta(minutes=current_time.minute % 5, 
                                            seconds=current_time.second, 
                                            microseconds=current_time.microsecond)

    # Log the player list to the database
    async with aiosqlite.connect('bot_storage.db') as conn:
        async with conn.cursor() as cur:
            for result in query_results:
                if result['Status'] == 'Online':
                    timestamp = rounded_time.strftime("%Y-%m-%d %H:%M:%S")
                    game_name = result['GameName']
                    players_online = result['Players']
                    player_names = ', '.join(result['PlayerNames'])  # Convert list of player names to a string

                    # Check if an entry for the current timestamp already exists
                    await cur.execute('''
                        SELECT * FROM online_players WHERE timestamp = ? AND game_name = ?
                    ''', (timestamp, game_name))
                    entry_exists = await cur.fetchone()

                    # If no entry exists for the current timestamp, insert a new one
                    if not entry_exists:
                        await cur.execute('''
                            INSERT INTO online_players (timestamp, game_name, players_online, player_names, status)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (timestamp, game_name, players_online, player_names, result['Status']))
            # Clear the real_time_status table before inserting new data
            await cur.execute('DELETE FROM real_time_status')

            # Insert new data into real_time_status table
            for result in query_results:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                players_online = result.get('Players', 0)  # Defaults to 0 if 'Players' key is not found
                server_ping_ms = round(result.get('ServerMS', 0) * 1000)
                await cur.execute('''
                    INSERT INTO real_time_status (Game_Name, Server_Status, Server_MS, Timestamp, Game_Type, Players_Count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (result['GameName'], result['Status'], server_ping_ms, timestamp, result.get('GameType', 'Unknown'), result.get('Players', 0)))

            await conn.commit()

@bot.command(name="online")
async def online(ctx, game_name: str):
    await ctx.defer(ephemeral=True)
    # Connect to the database
    async with aiosqlite.connect('bot_storage.db') as conn:
        async with conn.cursor() as cur:
            # Adjusted the query to include timestamp
            await cur.execute('''
                SELECT op.timestamp, op.game_name, op.status, op.players_online, op.player_names, 
                       s.server_quick_join_url, s.users_title, s.server_emoji, s.server_image
                FROM online_players op
                JOIN servers s ON op.game_name = s.server_name  -- Assuming game_name maps to server_name
                WHERE op.game_name = ? 
                ORDER BY op.timestamp DESC 
                LIMIT 1
            ''', (game_name,))
            result = await cur.fetchone()
            
    if result:
        timestamp, game_name, status, players_online, player_names, server_quick_join_url, users_title, server_emoji, server_image = result
        # Split player names into a list only if player_names is not empty
        player_list = player_names.split(', ') if player_names.strip() else []
        
        # Create the embed with server_image and include timestamp in the footer
        embed = discord.Embed(title=f"{server_emoji} Server Status for {game_name}", color=0x00ff00)
        if server_image:  # Check if server_image is not empty or None
            embed.set_image(url=server_image)
        
        embed.add_field(name="Server Status", value=status, inline=True)
        embed.add_field(name=f"{users_title}", value=players_online, inline=True)
        
        # Add player names, each on a new line, if not blank. Only add the field if player_list is not empty.
        if player_list:
            embed.add_field(name=f"{users_title} Online", value="\n".join(player_list), inline=False)

        # Add Server Quick Join URL if available
        if server_quick_join_url:
            embed.add_field(name="Quick Connect", value=f"[here]({server_quick_join_url})", inline=True)
        
        # Add the Last Updated timestamp to the footer
        embed.set_footer(text=f"🤖 GamePulse V{bot_version} - Last Updated: {timestamp}")
        
        await ctx.respond(embed=embed)
    else:
        await ctx.respond("No information available for this game.")

from datetime import datetime

@bot.command(name="history")
async def history(ctx, server_name: str):
    # Acknowledge the command promptly
    await ctx.defer(ephemeral=True)

    # Connect to the database
    async with aiosqlite.connect('bot_storage.db') as conn:
        async with conn.cursor() as cur:
            # Fetch server details for emoji and image
            await cur.execute('''
                SELECT server_emoji, server_image
                FROM servers
                WHERE server_name = ?
                LIMIT 1
            ''', (server_name,))
            server_details = await cur.fetchone()

            if not server_details:
                await ctx.send("Server not found.")
                return

            server_emoji, server_image = server_details

            # Adjusted query to fetch the highest players_online count for each hour
            await cur.execute('''
                SELECT strftime('%Y-%m-%d %H:00', op.timestamp) as hour, 
                       group_concat(op.player_names, ', ') AS all_player_names, 
                       max(op.players_online) as max_players_online
                FROM online_players op
                JOIN servers s ON op.game_name = s.server_name
                WHERE s.server_name = ? AND op.timestamp >= datetime('now', '-24 hours')
                GROUP BY hour
                ORDER BY hour DESC
                LIMIT 24
            ''', (server_name,))
            results = await cur.fetchall()

    # Collect all player names and count unique names
    all_names = []
    for _, all_player_names, _ in results:
        if all_player_names:
            all_names.extend(all_player_names.split(', '))
    unique_names_count = len(set(all_names))

    # Prepare the data for the graph
    hours = []
    player_counts = []

    # Prepare embed
    embed = discord.Embed(title=f"{server_emoji} 24 Hour Player History for {server_name}", color=0x7289DA)
    if server_image:
        embed.set_thumbnail(url=server_image)

    # Add fields for each hour with player count and names
    for hour, all_player_names, max_players_online in results:
        player_names_list = all_player_names.split(', ') if all_player_names else []
        unique_player_names = set(filter(None, player_names_list))

        if unique_player_names:
            total_players = len(unique_player_names)
            player_names_display = ", ".join(unique_player_names)
            if len(player_names_display) > 450:
                player_names_display = player_names_display[:450] + "..."
        else:
            total_players = max_players_online
            player_names_display = "Player names not available" if max_players_online > 0 else "No players online"

        # Convert "hour" from "YYYY-MM-DD HH:MM" to "1 PM" format
        hour_datetime = datetime.strptime(hour, '%Y-%m-%d %H:%M')
        hour_formatted = hour_datetime.strftime('%I %p').lstrip("0")

        embed.add_field(name=f"{hour_formatted}", value=f"**Total Players:** *{total_players}*\n**Players:** *{player_names_display}*", inline=True)
        embed.set_footer(text=f"🤖 GamePulse V{bot_version} - Saw {unique_names_count} Unique Users Connected")

        # Collect data for the graph
        hours.append(hour_datetime)
        player_counts.append(total_players)

    # Create the graph if we have data
    if results:
        # Use a dark theme for the graph
        plt.style.use('dark_background')

        plt.figure(figsize=(10, 5))
        plt.plot(hours, player_counts, marker='o', color='#7289DA')  # Discord's "Blurple"
        plt.title('Player Count Over the Last 24 Hours', color='white')
        plt.xlabel('Time', color='white')
        plt.ylabel('Player Count', color='white')
        plt.grid(True, color='#424549')  # Discord's secondary dark color
        plt.xticks(color='white')
        plt.yticks(color='white')

        # Change spine color
        ax = plt.gca()
        ax.spines['bottom'].set_color('#7289DA')
        ax.spines['top'].set_color('#2C2F33')  # Discord's background color
        ax.spines['right'].set_color('#2C2F33')
        ax.spines['left'].set_color('#7289DA')

        # Formatting for the date ticks
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        # Save it to a BytesIO object in memory with the corrected facecolor
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        plt.close()

        # Attach the graph image to the embed
        file = discord.File(buffer, filename="player_history_graph.png")
        embed.set_image(url="attachment://player_history_graph.png")

        # Send the embed with the file
        await ctx.respond(file=file, embed=embed)
    else:
        await ctx.respond("No history available for this server.")

bot.run(TOKEN)
