from datetime import datetime
import discord
import sqlite3
import colorama
from colorama import Fore, Style
import configparser
import aiosqlite
import logging
from logging.handlers import RotatingFileHandler

# Initialize the ConfigParser
config = configparser.ConfigParser()

# Read the settings.ini file
config.read('settings.ini')

# Extract the STATUS_IMAGE URL
status_image_url = config['DISCORD']['STATUS_IMAGE']
community_name = config['DISCORD']['community_name']
bot_version = config['DISCORD']['bot_version']

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a rotating file handler
file_handler = RotatingFileHandler('logging.txt', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add the file handler to the logger
logger.addHandler(file_handler)

# Function to log messages with timestamps
def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {Fore.WHITE}{message}{Style.RESET_ALL}"
    
    # Log to console
    logger.info(message)
    
    # Log to file
    print(formatted_message)

# Function to retrieve user title from the database
async def get_user_title(server_name):
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()
    cur.execute("SELECT users_title FROM servers WHERE server_name = ?", (server_name,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "Players"  # Return "Players" if no user_title is found

# Function to retrieve server details from the database
async def get_server_details(server_name):
    conn = sqlite3.connect('bot_storage.db')
    cur = conn.cursor()
    cur.execute("SELECT server_ip, server_port, server_quick_join_url, server_emoji, status_embed FROM servers WHERE server_name = ?", (server_name,))
    row = cur.fetchone()
    conn.close()
    if row and row[-1] == 1:  # Check if status_embed is 1 (1 True, 0 False)
        return row[:-1]  # Return details without the status_embed field
    else:
        return None  # Return None to indicate the server should not be included

# Function to update Discord message with server status
async def update_discord_message(bot, channel_id, query_results):
    # Establish connection to database
    async with aiosqlite.connect('bot_storage.db') as conn:
        async with conn.cursor() as cur:
            # Check if the embed_ids table exists and retrieve the message_id if available
            await cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='embed_ids'")
            if await cur.fetchone():
                await cur.execute("SELECT message_id FROM embed_ids WHERE embed_name = ?", ("server_status",))
                row = await cur.fetchone()
                message_id = row[0] if row else None
            else:
                message_id = None

    channel = bot.get_channel(channel_id)
    message = None
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            # Message does not exist, reset message_id to None to send a new message
            message_id = None

    embed = discord.Embed(title=f"{community_name} Server Status", color=discord.Color.green() if all(result['Status'] == 'Online' for result in query_results) else discord.Color.red())
    embed.set_footer(text=f"📊 Total Users {sum(result.get('Players', 0) for result in query_results if result['Status'] == 'Online')} - 🤖 GamePulse V{bot_version} - 🕒 Updated:")
    embed.timestamp = discord.utils.utcnow()
    embed.set_image(url=status_image_url)  # Assuming status_image_url is predefined

    field_count = 0
    for result in query_results:
        # Fetch server details
        server_details = await get_server_details(result['GameName'])  # This function needs to be async
        if server_details:
            # Assuming server_details returns a tuple/list with the expected values
            server_ip, server_port, quick_connect_url, server_emoji = server_details
            user_title = await get_user_title(result['GameName'])  # This function needs to be async
            
            # Add the server information field
            embed.add_field(name=f"{server_emoji} {result['GameName']}",
                            value=f"⚡ *Status:* {'🟢' if result['Status'] == 'Online' else '☠'}\n"
                                  f"👥 *{user_title}:* **{result.get('Players', 'N/A')}**\n"
                                  f"----------------------\n"
                                  f"💻 IP: {server_ip}\n"
                                  f"🔒 Port: {server_port}\n"
                                  f"🚀 Connect: [Launch]({quick_connect_url})",
                            inline=True)
            field_count += 1
            # After every third field, add an invisible field to create a visual break
            if field_count % 3 == 0 and field_count < len(query_results):
                embed.add_field(name="\u200b", value="\u200b", inline=False)

    # Editing or sending the message
    if message_id and message:
        await message.edit(embed=embed)
        log_message("Discord Message edited in Status Channel.")
    else:
        sent_message = await channel.send(embed=embed)
        # Update or insert the new message_id into the database
        await cur.execute("DELETE FROM embed_ids WHERE embed_name = ?", ("server_status",))
        await cur.execute("INSERT INTO embed_ids (embed_name, message_id) VALUES (?, ?)", ("server_status", sent_message.id))
        await conn.commit()
        log_message("New message sent into Status Channel.")

# Function to update bot's presence with total online users
async def update_bot_presence(bot, query_results):
    # Calculate total online players
    total_players = sum(result.get('Players', 0) for result in query_results if result['Status'] == 'Online')
    
    # Convert total players into emoji representation
    emoji_numbers = {
        '0': '0️⃣',
        '1': '1️⃣',
        '2': '2️⃣',
        '3': '3️⃣',
        '4': '4️⃣',
        '5': '5️⃣',
        '6': '6️⃣',
        '7': '7️⃣',
        '8': '8️⃣',
        '9': '9️⃣',
    }
    emoji_total_players = ''.join(emoji_numbers.get(char, char) for char in str(total_players))
    
    # Update bot's presence
    activity_text = f"{emoji_total_players} Users! 🚀"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=activity_text))
    log_message(f"Updated Status Text To {total_players} Users! 🚀")
