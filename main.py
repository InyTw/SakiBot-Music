import discord
import os
import asyncio
import yt_dlp
import re
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from collections import deque

# 載入環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 設定機器人權限
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True 
bot = commands.Bot(command_prefix='!', intents=intents)

# 儲存伺服器播放清單
queues = {}

# 正規表達式判斷連結
YT_PATTERN = re.compile(r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)[^&\s]+')
SPOTIFY_PATTERN = re.compile(r'(https?://)?(open\.)?spotify\.com/(track|album|playlist)/[a-zA-Z0-9]+')

# yt-dlp 設定
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', '未知標題')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        
        # 這裡的 url 可能是關鍵字，也可能是連結
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            # 如果是搜尋結果，取第一個
            data = data['entries'][0]
                
        # 如果 stream=True，直接用連結；否則準備本地檔案
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        
        # 回傳實例時，記得把 data 傳進去
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# 播放控制按鈕介面
class MusicControls(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label='暫停', style=discord.ButtonStyle.grey, emoji='⏸️')
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice and voice.is_playing():
            voice.pause()
            await interaction.response.send_message("⏸️ 播放已暫停", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 目前沒有音樂在播放", ephemeral=True)

    @discord.ui.button(label='繼續', style=discord.ButtonStyle.green, emoji='▶️')
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice and voice.is_paused():
            voice.resume()
            await interaction.response.send_message("▶️ 音樂繼續播放", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 音樂並未處於暫停狀態", ephemeral=True)

    @discord.ui.button(label='跳過', style=discord.ButtonStyle.blurple, emoji='⏭️')
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()
            await interaction.response.send_message("⏭️ 已跳過當前歌曲", ephemeral=True)

    @discord.ui.button(label='停止', style=discord.ButtonStyle.red, emoji='⏹️')
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice:
            queues[interaction.guild.id].clear()
            await voice.disconnect()
            await interaction.response.send_message("⏹️ 已停止播放並退出頻道", ephemeral=True)

@bot.event
async def on_ready():
    print(f'🎵 {bot.user} 已上線！')
    try:
        synced = await bot.tree.sync()
        print(f"成功同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"同步指令失敗: {e}")

async def play_next(interaction, guild):
    """自動播放下一首歌的邏輯"""
    if guild.id not in queues or not queues[guild.id]:
        return

    voice = discord.utils.get(bot.voice_clients, guild=guild)
    if not voice or not voice.is_connected():
        return

    if voice.is_playing():
        return

    player = queues[guild.id].popleft()
    
    def after_playing(error):
        if error:
            print(f"播放出錯: {error}")
        asyncio.run_coroutine_threadsafe(play_next(interaction, guild), bot.loop)

    voice.play(player, after=after_playing)
    
    embed = discord.Embed(
        title="🎶 正在播放",
        description=f"[{player.title}]({player.data.get('webpage_url')})\n時長: `{player.duration//60}:{player.duration%60:02d}`",
        color=0x0099ff
    )
    if player.thumbnail:
        embed.set_thumbnail(url=player.thumbnail)
    
    await interaction.channel.send(embed=embed, view=MusicControls(bot))

@bot.tree.command(name="play", description="播放來自 YouTube 的音樂")
@app_commands.describe(search="請輸入歌曲名稱或網址")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    
    # 檢查使用者是否在語音頻道
    if not interaction.user.voice:
        return await interaction.followup.send("❌ 你必須先加入一個語音頻道！", ephemeral=True)

    # 語音連接邏輯
    voice_channel = interaction.user.voice.channel
    voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not voice or not voice.is_connected():
        voice = await voice_channel.connect()
    elif voice.channel != voice_channel:
        await voice.move_to(voice_channel)

    if interaction.guild.id not in queues:
        queues[interaction.guild.id] = deque()

    try:
        # 讀取音樂資源
        player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
        queues[interaction.guild.id].append(player)

        if voice.is_playing() or voice.is_paused():
            embed = discord.Embed(
                title="✅ 已加入排隊",
                description=f"**{player.title}**",
                color=0xffcc00
            )
            if player.thumbnail: embed.set_thumbnail(url=player.thumbnail)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("🔎 正在搜尋並準備播放...", ephemeral=True)
            await play_next(interaction, interaction.guild)
            
    except Exception as e:
        await interaction.followup.send(f"❌ 發生錯誤: `{str(e)}`", ephemeral=True)

@bot.tree.command(name="queue", description="查看目前的播放隊列")
async def queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id not in queues or not queues[guild_id]:
        return await interaction.response.send_message("Empty", ephemeral=True)

    queue_list = list(queues[guild_id])
    description = ""
    for i, song in enumerate(queue_list[:10], 1):
        description += f"{i}. {song.title}\n"
    
    if len(queue_list) > 10:
        description += f"\n*還有 {len(queue_list)-10} 首歌曲...*"

    embed = discord.Embed(title="📋 目前播放隊列", description=description, color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leave", description="讓機器人離開語音頻道")
async def leave(interaction: discord.Interaction):
    voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice:
        queues[interaction.guild.id].clear()
        await voice.disconnect()
        await interaction.response.send_message("👋 已退出頻道並清空清單")
    else:
        await interaction.response.send_message("❌ 我不在語音頻道中", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)