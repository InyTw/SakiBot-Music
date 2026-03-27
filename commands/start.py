import discord
import asyncio
import yt_dlp
import time
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from discord.ext import commands, tasks
from discord import app_commands
from collections import deque
from dotenv import load_dotenv

load_dotenv()

# --- Spotify API ---
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

class SpotifyHandler:
    @staticmethod
    def is_spotify(url):
        return "spotify.com" in url or "spotify.link" in url

    @staticmethod
    async def get_tracks(url):
        tracks = []
        try:
            # 1. 處理單曲
            if "track" in url:
                res = sp.track(url)
                artist_name = res['artists'][0]['name'] if res.get('artists') else "未知歌手"
                tracks.append(f"{res['name']} {artist_name}")

            # 2. 處理歌單
            elif "playlist" in url:
                res = sp.playlist_tracks(url)
                for item in res.get('items', []):
                    track = item.get('track')
                    if track:
                        artist_name = track['artists'][0]['name'] if track.get('artists') else "未知歌手"
                        tracks.append(f"{track['name']} {artist_name}")

            # 3. 處理專輯
            elif "album" in url:
                res = sp.album(url) # 改用 sp.album 才能拿到專輯整體的歌手
                album_artist = res['artists'][0]['name'] if res.get('artists') else "未知歌手"
                for item in res['tracks']['items']:
                    # 優先找歌曲本身的歌手，沒有就用專輯歌手
                    track_artist = item['artists'][0]['name'] if item.get('artists') else album_artist
                    tracks.append(f"{item['name']} {track_artist}")

        except Exception as e:
            print(f"Spotify 解析錯誤: {e}")
            import traceback; traceback.print_exc() 
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
                msg = self.cog.control_messages[self.guild_id]
                try:
                    await msg.edit(view=None) # 移除按鈕
                except: pass
                del self.cog.control_messages[self.guild_id]
            
            await interaction.response.send_message("⏹️ 播放已停止，按鈕已移除", ephemeral=True)

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
                data = self.current_songs.get(gid, {}).get('raw_data', {})
                total_dur = data.get('duration', 0)
                if elapsed > total_dur: elapsed = total_dur
                current_str = f"{elapsed//60}分 {elapsed%60}秒"
                total_str = f"{total_dur//60}分 {total_dur%60}秒"
                try:
                    new_embed = msg.embeds[0]
                    new_embed.set_field_at(0, name="<:time:1485620493758365808> | 歌曲時長", value=f"`{current_str} / {total_str}`", inline=True)
                    await msg.edit(embed=new_embed)
                except: pass

    # --- 自動補全搜尋邏輯 ---
    async def song_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current: return []
        search_options = {'format': 'bestaudio/best', 'quiet': True, 'default_search': 'ytsearch10', 'extract_flat': True}
        try:
            with yt_dlp.YoutubeDL(search_options) as ydl:
                info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch10:{current}", download=False))
            results = []
            for entry in info.get('entries', []):
                title = entry.get('title', '未知標題')
                if len(title) > 90: title = title[:87] + "..."
                results.append(app_commands.Choice(name=title, value=entry.get('url') or title))
            return results
        except: return []

    async def play_next(self, interaction, guild):
        gid = guild.id
        voice = guild.voice_client
        if not voice or not voice.is_connected(): return

        mode = self.loop_modes.get(gid, 0)
        
        if mode == 1 and gid in self.current_songs:
            song_info = self.current_songs[gid]
        elif not self.queues.get(gid):
            if gid in self.control_messages:
                try:
                    msg = self.control_messages[gid]
                    new_embed = msg.embeds[0]
                    new_embed.title = "✅ | 播放已結束"
                    new_embed.color = discord.Color.greyple()
                    await msg.edit(content="🎵 所有歌曲已播放完畢。", embed=new_embed, view=None) # 播完移除按鈕
                except: pass
                if gid in self.start_times: del self.start_times[gid]
                del self.control_messages[gid]
            return
        else:
            song_info = self.queues[gid].popleft()
            if mode == 2: self.queues[gid].append(song_info)

        query = song_info['query']
        requester = song_info['requester']
        source_type = song_info['source']

        try:
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
            if 'entries' in data: data = data['entries'][0]
        except Exception as e:
            return await self.play_next(interaction, guild)

        self.current_songs[gid] = {'raw_data': data, 'requester': requester, 'source': source_type}
        self.start_times[gid] = time.time()
        
        voice.play(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), 
                   after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction, guild), self.bot.loop))

        color = 0x1DB954 if source_type == "Spotify" else 0x00ffff
        embed = discord.Embed(title="<a:sakiko_music:1485303402564026408> | 正在播放", color=color)
        embed.description = f"**[{data.get('title')}]({data.get('webpage_url')})**"
        
        dur = data.get('duration', 0)
        embed.add_field(name="<:time:1485620493758365808> | 歌曲時長", value=f"`0分 0秒 / {dur//60}分 {dur%60}秒`", inline=True)
        embed.add_field(name="<:yes:1485303410256379934> | 歌曲作者", value=f"{data.get('uploader', '未知')}", inline=True)
        embed.add_field(name="<:kuru64:1485622482701647992> | 歌曲來源", value=f"{source_type}", inline=True)
        embed.add_field(name="<:user_discord:1485621449636184084> | 點播者", value=requester, inline=True)
        embed.add_field(name="<:list:1485621651868614777> | 待播清單", value=f"{len(self.queues[gid])} 首", inline=True)
        
        if data.get('thumbnail'): embed.set_thumbnail(url=data['thumbnail'])
        
        view = MusicControls(self, gid)
        view.children[2].label = view.get_loop_label()
        view.children[2].style = view.get_loop_style()

        if gid in self.control_messages:
            try: await self.control_messages[gid].edit(embed=embed, view=view)
            except: self.control_messages[gid] = await interaction.channel.send(embed=embed, view=view)
        else:
            self.control_messages[gid] = await interaction.channel.send(embed=embed, view=view)

    @app_commands.command(name="play", description="播放音樂 (支援 YouTube 搜尋/Spotify)")
    @app_commands.autocomplete(search=song_autocomplete)
    async def play(self, interaction: discord.Interaction, search: str):
        await interaction.response.defer(ephemeral=False)
        
        gid = interaction.guild.id
        if not interaction.user.voice: return await interaction.followup.send("❌ 請先加入語音頻道")
        
        voice = interaction.guild.voice_client
        if not voice: voice = await interaction.user.voice.channel.connect()

        if gid not in self.queues: self.queues[gid] = deque()

        try:
            is_spotify = SpotifyHandler.is_spotify(search)
            
            if is_spotify:
                # 1. 先嘗試用 Spotify API 拿歌曲名稱
                try:
                    tracks = await SpotifyHandler.get_tracks(search)
                except:
                    tracks = [] # 403 噴錯就設為空列表

                if tracks:
                    # 如果 API 拿得到歌曲清單 (例如單曲名 歌手名)
                    for t in tracks:
                        self.queues[gid].append({'query': t, 'requester': interaction.user.mention, 'source': 'Spotify'})
                    display_title = f"Spotify 內容 ({len(tracks)} 首)"
                    display_author = "Spotify"
                    display_duration = "視搜尋結果而定"
                    thumbnail = None
                    color = 0x1DB954
                else:
                    # 2. 如果 API 失敗，我們「不」直接解析網址，而是搜尋網址本身 (這會觸發 YouTube 搜尋)
                    # 我們強迫 yt-dlp 用關鍵字搜尋而不是直接下載
                    search_query = f"ytsearch1:{search}" 
                    data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
                    
                    if not data or 'entries' not in data or not data['entries']:
                        return await interaction.followup.send("<a:sakiko_err:1485303400194248725> 啊不是叫你先別用了嗎?")
                    
                    first_song = data['entries'][0]
                    self.queues[gid].append({
                        'query': first_song.get('webpage_url'),
                        'requester': interaction.user.mention,
                        'source': 'YouTube (Spotify 轉發)'
                    })
                    display_title = first_song.get('title')
                    display_author = first_song.get('uploader')
                    dur = first_song.get('duration', 0)
                    display_duration = f"{dur//60}分 {dur%60}秒"
                    thumbnail = first_song.get('thumbnail')
                    color = 0x00ff00
            else:
                # --- 一般 YouTube 或關鍵字搜尋 ---
                data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
                
                # 防呆：確保 data 不是 None
                if not data:
                    return await interaction.followup.send("❌ 找不到歌曲資訊")
                
                songs = data.get('entries', [data])
                for s in songs:
                    if s:
                        self.queues[gid].append({
                            'query': s.get('webpage_url') or s.get('url'),
                            'requester': interaction.user.mention,
                            'source': 'YouTube'
                        })
                
                first_song = songs[0] if songs[0] else data
                display_title = first_song.get('title', '未知標題')
                display_author = first_song.get('uploader', '未知作者')
                dur = first_song.get('duration', 0)
                display_duration = f"{dur//60}分 {dur%60}秒"
                thumbnail = first_song.get('thumbnail')
                color = 0x00ff00

            fb_embed = discord.Embed(color=color)
            fb_embed.set_author(name="小祥音樂 | 新增歌曲", icon_url=self.bot.user.display_avatar.url)
            fb_embed.description = f"<a:check1:1485303384436244541> **已新增 [{display_title}]({search if 'http' in search else 'https://www.youtube.com'}) 至待播清單**"
            fb_embed.add_field(name="<:time:1485620493758365808> | 歌曲時長", value=f"`{display_duration}`", inline=True)
            fb_embed.add_field(name="<:yes:1485303410256379934> | 歌曲作者", value=f"`{display_author}`", inline=True)
            if thumbnail: fb_embed.set_thumbnail(url=thumbnail)

            await interaction.followup.send(embed=fb_embed, ephemeral=False)

            if not voice.is_playing():
                await self.play_next(interaction, interaction.guild)
                
        except Exception as e:
            await interaction.followup.send(f"❌ 處理歌曲時發生錯誤: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
