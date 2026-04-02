import discord
import os
import asyncio
import psutil  # 記得 pip install psutil
import datetime
import json
import base64
import requests # 記得 pip install requests
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# 新增：請在 .env 加入 GITHUB_TOKEN
GH_TOKEN = os.getenv('GITHUB_TOKEN') 

# --- GitHub 設定區 ---
REPO_OWNER = "InyTw"
REPO_NAME = "SakiBot-Music"
FILE_PATH = "stats.json" 

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 紀錄啟動時間來計算 Uptime
start_time = datetime.datetime.now()

# --- 新增：GitHub 同步任務 ---
@tasks.loop(minutes=5)
async def update_github_stats():
    if not GH_TOKEN:
        print("⚠️ 未偵測到 GITHUB_TOKEN，跳過同步")
        return

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GH_TOKEN}"}

    # 計算 Uptime (格式: 1d 2h 3m)
    now = datetime.datetime.now()
    diff = now - start_time
    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{days}d {hours}h {minutes}m"

    # 封裝數據
    stats = {
    "uptime": uptime_str,
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # 新增這行
    "guilds": len(bot.guilds),
    "players": 84,
    "cpu": psutil.cpu_percent(),
    "ram_used": int(psutil.virtual_memory().used / 1024 / 1024),
    "ram_total": int(psutil.virtual_memory().total / 1024 / 1024)
}

    try:
        # 獲取 SHA
        resp = requests.get(url, headers=headers)
        sha = resp.json().get('sha') if resp.status_code == 200 else None

        # 推送更新
        content_b64 = base64.b64encode(json.dumps(stats, indent=2).encode('utf-8')).decode('utf-8')
        payload = {
            "message": "sys: update saki-music load stats",
            "content": content_b64,
            "sha": sha
        }
        
        requests.put(url, headers=headers, json=payload)
        print(f"✅ 數據已同步至 GitHub ({datetime.datetime.now().strftime('%H:%M:%S')})")
    except Exception as e:
        print(f"❌ GitHub 同步失敗: {e}")

async def load_extensions():
    extensions = [
        'commands.start',
        'commands.update_ann',
        'commands.update_ann_dev',
        'commands.ticket',
        'commands.help',
        'cogs.logging_cog'
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
    await bot.tree.sync()
    print("🌐 斜線指令已同步完成")

    activity = discord.CustomActivity(name="🔥我InyTw老師更新了！")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
    # --- 啟動定時任務 ---
    if not update_github_stats.is_running():
        update_github_stats.start()

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())