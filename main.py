import discord
import os
import asyncio
import psutil
import datetime
import json
import base64
import aiohttp
from discord.ext import commands, tasks
from dotenv import load_dotenv
from mcstatus import JavaServer

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GH_TOKEN = os.getenv('GITHUB_TOKEN') 

REPO_OWNER = "InyTw"
REPO_NAME = "SakiBot-Music"
FILE_PATH = "stats.json" 

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
start_time = datetime.datetime.now()

@tasks.loop(minutes=5)
async def update_github_stats():
    if not bot.is_ready():
        return

    if not GH_TOKEN:
        print("⚠️ 未偵測到 GITHUB_TOKEN，跳過同步任務")
        return

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    now = datetime.datetime.now()
    diff = now - start_time
    uptime_str = f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds // 60) % 60}m"

    process = psutil.Process(os.getpid())

    ram_used_mb = int(process.memory_info().rss / 1024 / 1024)
    total_listeners = 0
    for guild in bot.guilds:
        if guild.voice_client and guild.voice_client.is_playing():
            total_listeners += len(guild.voice_client.channel.members) - 1
            
    try:
        server = JavaServer.lookup("ohw.cloud-ip.cc") 
        status = await server.async_status()
        mc_data = {
            "online": True,
            "current": status.players.online,
            "max": status.players.max,
            "ping": round(status.latency, 1)
        }
    except Exception as e:
        print(f"⚠️ 無法獲取 Minecraft 數據: {e}")
        mc_data = {"online": False, "current": 0, "max": 1000, "ping": 0}
    stats = {
        "uptime": uptime_str,
        "guilds": len(bot.guilds),
        "players": total_listeners,
        "cpu": psutil.cpu_percent(),
        "ram_used": ram_used_mb,
        "ram_total": 2048,
        "minecraft": mc_data
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                sha = data.get('sha') if resp.status == 200 else None

            content_json = json.dumps(stats, indent=2, ensure_ascii=False)
            content_b64 = base64.b64encode(content_json.encode('utf-8')).decode('utf-8')
            
            payload = {
                "message": "sys: auto-sync bot metrics [skip ci]",
                "content": content_b64,
                "sha": sha
            }
            
            async with session.put(url, headers=headers, json=payload) as put_resp:
                if put_resp.status in [200, 201]:
                    print(f"✅ 數據已成功同步至 GitHub ({now.strftime('%H:%M:%S')})")
                else:
                    err_details = await put_resp.text()
                    print(f"❌ 同步失敗 (HTTP {put_resp.status}): {err_details}")
                    
    except Exception as e:
        print(f"❌ GitHub 同步過程發生非預期錯誤: {e}")

async def load_extensions():
    extensions = [
        'commands.start',
        'commands.update_ann',
        'commands.update_ann_dev',
        'commands.ticket',
        'commands.help',
        'commands.ann',
        'cogs.logging_cog'
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ 成功載入模組: {ext}")
        except Exception as e:
            print(f"❌ 載入模組失敗 {ext}: {e}")

@bot.event
async def on_ready():
    print(f'✅ {bot.user} 已成功上線並接管服務')

    await bot.tree.sync()
    print("🌐 Discord 斜線指令已完成全域同步")

    activity = discord.CustomActivity(name="🔥 Saki 音樂系統監控中")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    await asyncio.sleep(10)
    if not update_github_stats.is_running():
        update_github_stats.start()
        print("📊 監控數據同步任務已就緒")

async def main():
    try:
        async with bot:
            await load_extensions()
            if not TOKEN:
                print("❌ 錯誤: 找不到 DISCORD_TOKEN，請檢查 .env 檔案")
                return
            await bot.start(TOKEN)
    except Exception as e:
        print(f"🔥 機器人啟動時發生嚴重錯誤: {e}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 接收到關閉指令，機器人正在離線...")
    except Exception as e:
        print(f"🚨 系統層級崩潰: {e}")