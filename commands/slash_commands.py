from discord import Option
from discord.ext import commands
import sqlite3
import configparser

# Load settings from settings.ini
config = configparser.ConfigParser()
config.read('settings.ini')
TOKEN = config['DISCORD']['TOKEN']
CHANNEL_ID = int(config['DISCORD']['CHANNEL_ID'])
GUILD_ID = int(config['DISCORD']['GUILD_ID'])
ALLOWED_USER_IDS = [int(user_id.strip()) for user_id in config['DISCORD']['Allowed_User_IDs'].split(',')]

# Assuming ALLOWED_USER_IDS is globally accessible or passed somehow, adjust accordingly
# If not, you'll need to re-import or access these IDs in an appropriate manner

async def setup(bot):
    bot.add_application_command(AddServerCommand(bot))
    bot.add_application_command(RemoveServerCommand(bot))
    bot.add_application_command(ManualUpdateCommand(bot))

class AddServerCommand(commands.Command):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            name="add",
            callback=self.command_callback,
            description="Adds a new server"
        )

    async def command_callback(self, ctx,
                               server_name: str,
                               server_ip: str,
                               server_port: int,
                               server_emoji: Option(str, "Emoji for the server", required=False) = "",
                               server_quick_join_url: Option(str, "Quick join URL for the server", required=False) = "",
                               users_title: Option(str, "Title for users", required=False) = "",
                               status_embed: Option(str, "Use status embed?", choices=["Yes", "No"], required=False) = "No",
                               server_status_channel_id: Option(int, "Channel ID for server status", required=False) = 0,
                               user_online_count_channel_id: Option(int, "Channel ID for online user count", required=False) = 0):
        if ctx.author.id in ALLOWED_USER_IDS:
            status_embed_bool = True if status_embed.lower() == "yes" else False
            conn = sqlite3.connect('bot_storage.db')
            cur = conn.cursor()
            try:
                cur.execute('''
                    INSERT INTO servers (
                        server_name, server_ip, server_port, server_emoji, server_quick_join_url,
                        users_title, status_embed, server_status_channel_id, user_online_count_channel_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                  server_name, server_ip, server_port, server_emoji, server_quick_join_url,
                 users_title, status_embed_bool, server_status_channel_id, user_online_count_channel_id
                ))
                conn.commit()
                await ctx.respond(f"Server '{server_name}' added successfully.")
            except sqlite3.Error as e:
                await ctx.respond(f"Failed to add server '{server_name}': {e}")
            finally:
                conn.close()
        else:
            await ctx.respond("You don't have permission to use this command.")

class RemoveServerCommand(commands.Command):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            name="remove",
            callback=self.command_callback,
            description="Removes an existing server"
        )

    async def command_callback(self, ctx, server_name: str):
        if ctx.author.id in ALLOWED_USER_IDS:
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

class ManualUpdateCommand(commands.Command):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            name="test",
            callback=self.command_callback,
            description="Manually triggers an update"
        )

    async def command_callback(self, ctx):
        from functions.discord_utils import log_message
        from functions.server_queries import query_servers
        from functions.discord_utils import update_discord_message
        
        log_message("Manual update triggered.")
        query_results = await query_servers()
        await update_discord_message(self.bot, CHANNEL_ID, query_results)
        await ctx.respond("Manual update triggered and processed.")
