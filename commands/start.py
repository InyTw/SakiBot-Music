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

# --- 初始化與設定 ---
load_dotenv()

auth_manager = SpotifyClientCredentials(
    client_id=os.getenv('SPOTIPY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')
)
sp = spotipy.Spotify(auth_manager=auth_manager)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'extract_flat': True, 
    'noplaylist': False,  
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'youtube_include_dash_manifest': False,
    'no_warnings': True
}
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# --- 輔助類別 ---
class SpotifyHandler:
    @staticmethod
    def is_spotify(url):
        return "spotify.com" in url or "spotify.link" in url

    @staticmethod
    async def get_tracks(url):
        return await asyncio.to_thread(SpotifyHandler._fetch_spotify_data, url)

    @staticmethod
    def _fetch_spotify_data(url):
        tracks = []
        try:
            if "track" in url:
                res = sp.track(url)
                tracks.append(f"{res['name']} {res['artists'][0]['name']}")
            elif "playlist" in url:
                res = sp.playlist_tracks(url)
                for item in res.get('items', []):
                    t = item.get('track')
                    if t: tracks.append(f"{t['name']} {t['artists'][0]['name']}")
            elif "album" in url:
                res = sp.album(url)
                for item in res['tracks']['items']:
                    tracks.append(f"{item['name']} {res['artists'][0]['name']}")
        except Exception as e:
            print(f"Spotify API Error: {e}")
        return tracks

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
            if self.guild_id in self.cog.queues:
                self.cog.queues[self.guild_id].clear()
            await voice.disconnect()
            if self.guild_id in self.cog.control_messages:
                msg = self.cog.control_messages[self.guild_id]
                try: await msg.edit(view=None)
                except: pass
                del self.cog.control_messages[self.guild_id]
            await interaction.response.send_message("⏹️ 播放已停止", ephemeral=True)

# --- 主程式模組 ---
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.loop_modes = {}
        self.current_songs = {}
        self.control_messages = {}
        self.start_times = {}
        self.is_transitioning = {}
        self.update_progress.start()

    def cog_unload(self):
        self.update_progress.cancel()

    @tasks.loop(seconds=5) # 降低更新頻率防止 API 速率限制
    async def update_progress(self):
        for gid, msg in list(self.control_messages.items()):
            if self.is_transitioning.get(gid): continue
                
            voice = msg.guild.voice_client
            if voice and voice.is_playing() and not voice.is_paused():
                if gid in self.start_times and gid in self.current_songs:
                    elapsed = int(time.time() - self.start_times[gid])
                    song_data = self.current_songs[gid].get('raw_data', {})
                    total_dur = song_data.get('duration', 0)
                    if elapsed > total_dur: elapsed = total_dur
                    
                    current_str = f"{elapsed//60}分 {elapsed%60}秒"
                    total_str = f"{total_dur//60}分 {total_dur%60}秒"
                    
                    try:
                        new_embed = msg.embeds[0]
                        new_embed.set_field_at(0, name="<:time:1485620493758365808> | 歌曲時長", value=f"`{current_str} / {total_str}`", inline=True)
                        await msg.edit(embed=new_embed)
                    except: pass

    async def play_next(self, interaction, guild):
        gid = guild.id
        if self.is_transitioning.get(gid): return
        self.is_transitioning[gid] = True
        
        try:
            voice = guild.voice_client
            if not voice or not voice.is_connected(): return

            # 稍微等待確保數據寫入隊列
            await asyncio.sleep(1)

            mode = self.loop_modes.get(gid, 0)
            
            if mode == 1 and gid in self.current_songs:
                song_info = self.current_songs[gid]
            elif not self.queues.get(gid) or len(self.queues[gid]) == 0:
                if gid in self.control_messages:
                    try:
                        msg = self.control_messages[gid]
                        emb = msg.embeds[0]
                        emb.title = "✅ | 播放已結束"
                        await msg.edit(content="🎵 所有歌曲已播放完畢。", embed=emb, view=None)
                    except: pass
                    if gid in self.start_times: del self.start_times[gid]
                    if gid in self.current_songs: del self.current_songs[gid]
                    del self.control_messages[gid]
                return
            else:
                song_info = self.queues[gid].popleft()
                if mode == 2: self.queues[gid].append(song_info)

            # 解析 YouTube 連結
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(song_info['query'], download=False))
            if 'entries' in data: data = data['entries'][0]

            self.current_songs[gid] = {'raw_data': data, 'requester': song_info['requester'], 'source': song_info['source']}
            self.start_times[gid] = time.time()
            
            if voice.is_playing(): voice.stop()

            def handle_next(error):
                asyncio.run_coroutine_threadsafe(self.play_next(interaction, guild), self.bot.loop)

            voice.play(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), after=handle_next)

            # 更新介面
            clr = 0x1DB954 if song_info['source'] == "Spotify" else 0x00ffff
            embed = discord.Embed(title="<a:sakiko_music:1485303402564026408> | 正在播放", color=clr)
            embed.description = f"**[{data.get('title')}]({data.get('webpage_url')})**"
            dur = data.get('duration', 0)
            embed.add_field(name="<:time:1485620493758365808> | 歌曲時長", value=f"`0分 0秒 / {dur//60}分 {dur%60}秒`", inline=True)
            embed.add_field(name="<:yes:1485303410256379934> | 歌曲作者", value=f"{data.get('uploader', '未知')}", inline=True)
            embed.add_field(name="<:user_discord:1485621449636184084> | 點播者", value=song_info['requester'], inline=True)
            embed.add_field(name="<:list:1485621651868614777> | 待播清單", value=f"{len(self.queues[gid])} 首", inline=True)
            if data.get('thumbnail'): embed.set_thumbnail(url=data['thumbnail'])
            
            view = MusicControls(self, gid)
            if gid in self.control_messages:
                try: await self.control_messages[gid].edit(embed=embed, view=view)
                except: self.control_messages[gid] = await interaction.channel.send(embed=embed, view=view)
            else:
                self.control_messages[gid] = await interaction.channel.send(embed=embed, view=view)

        except Exception as e:
            print(f"Play Next Error: {e}")
        finally:
            self.is_transitioning[gid] = False

    # 幫你補上自動補完函數
    async def song_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current:
            return [app_commands.Choice(name="請輸入歌曲名稱或網址", value="")]
        return [app_commands.Choice(name=f"搜尋: {current}", value=current)]

    @app_commands.command(name="play", description="播放音樂 (支援 YouTube 搜尋/Spotify)")
    async def play(self, interaction: discord.Interaction, search: str):
        # 檢查 autocomplete 是否傳入空值
        if not search: return await interaction.response.send_message("❌ 請輸入有效的內容", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        gid = interaction.guild.id
        
        if not interaction.user.voice: 
            return await interaction.followup.send("❌ 請先加入語音頻道")
        
        voice = interaction.guild.voice_client
        if not voice: 
            voice = await interaction.user.voice.channel.connect()
        
        if gid not in self.queues: self.queues[gid] = deque()

        try:
            if SpotifyHandler.is_spotify(search):
                tracks = await SpotifyHandler.get_tracks(search)
                for t in tracks:
                    self.queues[gid].append({'query': f"ytsearch:{t}", 'requester': interaction.user.mention, 'source': 'Spotify'})
                d_title = f"Spotify 歌單 ({len(tracks)} 首)"
                d_author = "Spotify"
                d_dur = "多首歌曲"
                thumb = None
                clr = 0x1DB954
            else:
                data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search if "http" in search else f"ytsearch:{search}", download=False))
                if 'entries' in data: data = data['entries'][0]
                self.queues[gid].append({'query': data['webpage_url'], 'requester': interaction.user.mention, 'source': 'YouTube'})
                d_title, d_author, dur = data.get('title'), data.get('uploader'), data.get('duration', 0)
                d_dur, thumb, clr = f"{dur//60}分 {dur%60}秒", data.get('thumbnail'), 0x00ff00

            fb = discord.Embed(title="✅ 已加入隊列", description=f"**[{d_title}]({search if 'http' in search else 'https://www.youtube.com'})**", color=clr)
            fb.add_field(name="歌曲作者", value=d_author, inline=True)
            fb.add_field(name="時長", value=d_dur, inline=True)
            if thumb: fb.set_thumbnail(url=thumb)
            await interaction.followup.send(embed=fb)

            if not voice.is_playing() and not self.is_transitioning.get(gid):
                await self.play_next(interaction, interaction.guild)
        except Exception as e:
            await interaction.followup.send(f"❌ 錯誤: {e}")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))