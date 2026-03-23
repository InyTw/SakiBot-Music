import discord
import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} 已上線')
    
    try:
        await bot.load_extension('commands.start')
        print("📁 已載入音樂模組")
    except Exception as e:
        print(f"❌ 載入失敗: {e}")

    activity = discord.CustomActivity(name="🔥現在正是複習的時刻")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
    await bot.tree.sync()

bot.run(TOKEN)