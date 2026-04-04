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

# 1. 載入環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GH_TOKEN = os.getenv('GITHUB_TOKEN') 

# --- GitHub 設定區 ---
REPO_OWNER = "InyTw"
REPO_NAME = "SakiBot-Music"
FILE_PATH = "stats.json" 

# 2. 初始化 Bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
start_time = datetime.datetime.now()

# --- 真實數據同步任務 (非同步優化版) ---
@tasks.loop(minutes=5)
async def update_github_stats():
    # 確保機器人完全連線後再開始跑，避免抓不到 bot.latency
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

    # 封裝真實指標數據
    now = datetime.datetime.now()
    diff = now - start_time
    uptime_str = f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds // 60) % 60}m"
    
    # 1. 獲取當前進程對象
    process = psutil.Process(os.getpid())
    
    # 2. 獲取當前機器人實際使用的記憶體 (單位: bytes -> MB)
    # 使用 rss (Resident Set Size) 是最準確的物理記憶體佔用
    ram_used_mb = int(process.memory_info().rss / 1024 / 1024)
    total_listeners = 0
    for guild in bot.guilds:
        if guild.voice_client and guild.voice_client.is_playing():
            # 只統計 Bot 正在播放音樂的那個頻道的人數
            # 減 1 是為了扣除 Bot 自己
            total_listeners += len(guild.voice_client.channel.members) - 1
            
    try:
        # 這裡填入你 OHW 伺服器的 IP。如果是本機跑就填 127.0.0.1
        # 如果有改 port (不是 25565) 記得要加上去，例如 "127.0.0.1:25566"
        server = JavaServer.lookup("ohw.cloud-ip.cc") 
        status = await server.async_status() # 使用非同步版本，才不會卡住 Bot
        mc_data = {
            "online": True,
            "current": status.players.online,
            "max": status.players.max,
            "ping": round(status.latency, 1)
        }
    except Exception as e:
        print(f"⚠️ 無法獲取 Minecraft 數據: {e}")
        mc_data = {"online": False, "current": 0, "max": 1000, "ping": 0}

    # 3. 封裝數據 (修正原本 NameError 的問題)
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
            # A. 獲取檔案目前的 SHA (GitHub 修改檔案必備)
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                sha = data.get('sha') if resp.status == 200 else None

            # B. 將數據轉為 Base64 並推送更新
            content_json = json.dumps(stats, indent=2, ensure_ascii=False)
            content_b64 = base64.b64encode(content_json.encode('utf-8')).decode('utf-8')
            
            payload = {
                "message": "sys: auto-sync bot metrics [skip ci]", # [skip ci] 避免觸發無謂的 Actions
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

# 3. 擴充功能載入
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

# 4. 事件處理
@bot.event
async def on_ready():
    print(f'✅ {bot.user} 已成功上線並接管服務')
    
    # 同步斜線指令
    await bot.tree.sync()
    print("🌐 Discord 斜線指令已完成全域同步")

    # 設定機器人狀態
    activity = discord.CustomActivity(name="🔥 Saki 音樂系統監控中")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
    # 啟動定時同步任務 (延遲 10 秒啟動，確保系統穩定)
    await asyncio.sleep(10)
    if not update_github_stats.is_running():
        update_github_stats.start()
        print("📊 監控數據同步任務已就緒")

# 5. 主啟動程序
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
        # 在 Pterodactyl 中保持程序開啟 10 秒以便閱讀報錯
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 接收到關閉指令，機器人正在離線...")
    except Exception as e:
        print(f"🚨 系統層級崩潰: {e}")