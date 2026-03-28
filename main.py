import discord
import os
import asyncio # 新增這個
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True # 建議開啟，這樣掃描成員數會更準確

bot = commands.Bot(command_prefix='!', intents=intents)

# --- 新增啟動載入函數 ---
async def load_extensions():
    extensions = [
        'commands.start',
        'commands.update_ann',
        'commands.update_ann_dev',
        'commands.ticket',
        'commands.help',
        'cogs.logging_cog' # 放在這裡載入
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ 成功載入: {ext}")
        except Exception as e:
            print(f"❌ 載入失敗 {ext}: {e}")

@bot.event
async def on_ready():
    print(f'✅ {bot.user} 已上線')
    
    # 同步斜線指令
    await bot.tree.sync()
    print("🌐 斜線指令已同步完成")

    activity = discord.CustomActivity(name="🔥我InyTw老師更新了！")
    await bot.change_presence(status=discord.Status.online, activity=activity)

# --- 修改啟動方式 ---
async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())