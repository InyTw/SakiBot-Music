import discord
import asyncio
import yt_dlp
import time
import re
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from discord.ext import commands, tasks
from discord import app_commands
from collections import deque
from dotenv import load_dotenv

load_dotenv()

# --- Spotify API 初始化 ---
auth_manager = SpotifyClientCredentials(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')
)
sp = spotipy.Spotify(auth_manager=auth_manager)

# --- 工具設定 ---
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extract_flat': True, 
    'noplaylist': False,  
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
}
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# --- Spotify 連結解析器 ---
class SpotifyHandler:
    @staticmethod
    def is_spotify(url):
        return "open.spotify.com" in url

    @staticmethod
    async def get_tracks(url):
        """解析 Spotify 連結並回傳 '歌名 - 歌手' 列表"""
        tracks = []
        try:
            if "track" in url:
                res = sp.track(url)
                tracks.append(f"{res['name']} {res['artists'][0]['name']}")
            elif "playlist" in url:
                res = sp.playlist_tracks(url)
                for item in res['items']:
                    if item['track']:
                        tracks.append(f"{item['track']['name']} {item['track']['artists'][0]['name']}")
            elif "album" in url:
                res = sp.album_tracks(url)
                for item in res['items']:
                    tracks.append(f"{item['name']} {res['artists'][0]['name']}")
        except Exception as e:
            print(f"Spotify 解析錯誤: {e}")
        return tracks

# --- 按鈕介面 ---
class MusicControls(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    def get_loop_label(self):
        mode = self.cog.loop_modes.get(self.guild_id, 0)
        return ["➡️ 不重複", "🔂 單曲重複", "🔁 列表重複"][mode]

    def get_loop_style(self):
        mode = self.cog.loop_modes.get(self.guild_id, 0)
        return [discord.ButtonStyle.grey, discord.ButtonStyle.green, discord.ButtonStyle.blurple][mode]

    @discord.ui.button(label='暫停', style=discord.ButtonStyle.grey, emoji='⏸️')
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = interaction.guild.voice_client
        if not voice: return
        if voice.is_playing():
            voice.pause()
            button.label = "繼續"; button.emoji = "▶️"
        else:
            voice.resume()
            button.label = "暫停"; button.emoji = "⏸️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='下一首歌', style=discord.ButtonStyle.grey, emoji='⏭️')
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = interaction.guild.voice_client
        if voice:
            voice.stop()
            await interaction.response.defer()

    @discord.ui.button(label='循環模式', style=discord.ButtonStyle.grey)
    async def cycle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        mode = (self.cog.loop_modes.get(self.guild_id, 0) + 1) % 3
        self.cog.loop_modes[self.guild_id] = mode
        button.label = self.get_loop_label()
        button.style = self.get_loop_style()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='停止播放', style=discord.ButtonStyle.red, emoji='⏹️', row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = interaction.guild.voice_client
        if voice:
            self.cog.queues[self.guild_id].clear()
            await voice.disconnect()
            if self.guild_id in self.cog.control_messages:
                try: await self.cog.control_messages[self.guild_id].delete()
                except: pass
                del self.cog.control_messages[self.guild_id]
            await interaction.response.send_message("⏹️ 播放在此結束", ephemeral=True)

# --- 主模組 ---
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.loop_modes = {}
        self.current_songs = {}
        self.control_messages = {}
        self.start_times = {}
        self.update_progress.start()

    def cog_unload(self):
        self.update_progress.cancel()

    @tasks.loop(seconds=5)
    async def update_progress(self):
        for gid, msg in list(self.control_messages.items()):
            voice = msg.guild.voice_client
            if voice and voice.is_playing() and not voice.is_paused() and gid in self.start_times:
                elapsed = int(time.time() - self.start_times[gid])
                data = self.current_songs.get(gid, {})
                total_dur = data.get('duration', 0)
                if elapsed > total_dur: elapsed = total_dur
                
                current_str = f"{elapsed//60}分 {elapsed%60}秒"
                total_str = f"{total_dur//60}分 {total_dur%60}秒"
                
                try:
                    new_embed = msg.embeds[0]
                    new_embed.set_field_at(0, name="⌚ | 歌曲時長", value=f"`{current_str} / {total_str}`", inline=True)
                    await msg.edit(embed=new_embed)
                except: pass

    async def play_next(self, interaction, guild):
        gid = guild.id
        voice = guild.voice_client
        if not voice or not voice.is_connected(): return

        mode = self.loop_modes.get(gid, 0)
        
        # 決定下一首歌的來源
        if mode == 1 and gid in self.current_songs:
            song_data = self.current_songs[gid]
        elif not self.queues.get(gid):
            if gid in self.control_messages:
                try: await self.control_messages[gid].edit(content="🎵 播放清單已結束。", embed=None, view=None)
                except: pass
                if gid in self.start_times: del self.start_times[gid]
            return
        else:
            song_data = self.queues[gid].popleft()
            if mode == 2: self.queues[gid].append(song_data)

        # 解析音源 (處理 Spotify 的關鍵字搜尋或直接 URL)
        query = song_data if isinstance(song_data, str) else (song_data.get('webpage_url') or song_data.get('url'))
        
        data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if 'entries' in data: # 如果是搜尋結果，抓第一個
            data = data['entries'][0]

        self.current_songs[gid] = data
        self.start_times[gid] = time.time()
        
        voice.play(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), 
                   after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction, guild), self.bot.loop))

        # --- 介面製作 ---
        embed = discord.Embed(title="<a:sakiko_music:1485303402564026408> | 正在播放", color=0x2b2d31)
        embed.description = f"**[{data.get('title')}]({data.get('webpage_url')})**"
        dur = data.get('duration', 0)
        embed.add_field(name="⌚ | 歌曲時長", value=f"`0分 0秒 / {dur//60}分 {dur%60}秒`", inline=True)
        embed.add_field(name="👤 | 歌曲作者", value=f"`{data.get('uploader', '未知')}`", inline=True)
        embed.add_field(name="📁 | 歌曲類別", value=f"`音樂/影片`", inline=True)
        embed.add_field(name="🖱️ | 點播者", value=interaction.user.mention, inline=True)
        embed.add_field(name="📂 | 待播清單", value=f"`{len(self.queues[gid])} 首`", inline=True)
        if data.get('thumbnail'): embed.set_thumbnail(url=data['thumbnail'])
        
        view = MusicControls(self, gid)
        view.children[2].label = view.get_loop_label()
        view.children[2].style = view.get_loop_style()

        if gid in self.control_messages:
            try: await self.control_messages[gid].edit(embed=embed, view=view)
            except: self.control_messages[gid] = await interaction.channel.send(embed=embed, view=view)
        else:
            self.control_messages[gid] = await interaction.channel.send(embed=embed, view=view)

    @app_commands.command(name="play", description="播放音樂 (支援 YouTube/Spotify)")
    async def play(self, interaction: discord.Interaction, search: str):
        await interaction.response.defer(ephemeral=True)
        gid = interaction.guild.id
        if not interaction.user.voice: return await interaction.followup.send("❌ 請先加入語音頻道")
        
        voice = interaction.guild.voice_client
        if not voice: voice = await interaction.user.voice.channel.connect()

        if gid not in self.queues: self.queues[gid] = deque()

        try:
            # 判斷是否為 Spotify
            if SpotifyHandler.is_spotify(search):
                tracks = await SpotifyHandler.get_tracks(search)
                if not tracks: return await interaction.followup.send("❌ 無法解析 Spotify 連結")
                for t in tracks: self.queues[gid].append(t)
                msg = f"已從 Spotify 新增 ``{len(tracks)}`` 首歌曲至待播清單"
                color = 0x1DB954 # Spotify 綠
            else:
                data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
                songs = data['entries'] if 'entries' in data else [data]
                for s in songs: 
                    if s: self.queues[gid].append(s)
                msg = f"已從 YouTube 新增 ``{len(songs)}`` 首歌曲至待播清單"
                color = 0x2ecc71

            fb_embed = discord.Embed(color=color)
            fb_embed.set_author(name="小祥音樂 | 阿北母雞卡的機器人 🎵", icon_url=self.bot.user.display_avatar.url)
            fb_embed.description = f"<a:check1:1485303384436244541> {msg}"
            await interaction.followup.send(embed=fb_embed)

            if not voice.is_playing():
                await self.play_next(interaction, interaction.guild)
            elif gid in self.control_messages:
                try:
                    new_embed = self.control_messages[gid].embeds[0]
                    new_embed.set_field_at(4, name="📂 | 待播清單", value=f"`{len(self.queues[gid])} 首`", inline=True)
                    await self.control_messages[gid].edit(embed=new_embed)
                except: pass
        except Exception as e:
            await interaction.followup.send(f"<a:sakiko_err:1485303400194248725> 錯誤: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))