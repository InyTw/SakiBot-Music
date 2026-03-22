import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import re
from collections import deque

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

queues = {}

# YouTube and Spotify URL patterns
YT_PATTERN = re.compile(r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)[^&\s]+')
SPOTIFY_PATTERN = re.compile(r'(https?://)?(open\.)?spotify\.com/(track|album|playlist)/[a-zA-Z0-9]+')

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
    'default_search': 'ytsearch1:',  # Only YouTube search
    'source_address': '0.0.0.0'
}

ffmpeg_options = {'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label='⏸️ Pause', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice and voice.is_playing():
            voice.pause()
            embed = discord.Embed(title="⏸️ Paused", color=0x00ff00)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='▶️ Resume', style=discord.ButtonStyle.green)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice and voice.is_paused():
            voice.resume()
            embed = discord.Embed(title="▶️ Resumed", color=0x00ff00)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='⏭️ Skip', style=discord.ButtonStyle.blurple)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice and voice.is_playing():
            voice.stop()
            embed = discord.Embed(title="⏭️ Skipped", color=0x00ff00)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='⏹️ Stop', style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice:
            await voice.disconnect()
            if interaction.guild.id in queues:
                queues[interaction.guild.id] = deque()
            embed = discord.Embed(title="⏹️ Stopped & Disconnected", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="play", description="Play from YouTube or Spotify link")
@app_commands.describe(link="YouTube or Spotify URL")
async def play(interaction: discord.Interaction, link: str):
    await interaction.response.defer()
    
    # Validate URL - only YouTube/Spotify allowed
    if not (YT_PATTERN.search(link) or SPOTIFY_PATTERN.search(link)):
        embed = discord.Embed(
            title="❌ Invalid Link", 
            description="**Only YouTube and Spotify links are supported!**\n\n✅ `youtube.com/watch?v=...`\n✅ `youtu.be/...`\n✅ `spotify.com/track/...`", 
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    if not interaction.user.voice:
        embed = discord.Embed(title="❌ Error", description="Join a voice channel first!", color=0xff0000)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel
    voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not voice:
        voice = await voice_channel.connect()

    if interaction.guild.id not in queues:
        queues[interaction.guild.id] = deque()

    try:
        # Handle Spotify -> yt-dlp auto-converts to YouTube
        player = await YTDLSource.from_url(link, loop=bot.loop, stream=True)
        
        queues[interaction.guild.id].append(player)

        embed = discord.Embed(
            title="🎵 Added to Queue",
            description=f"**{player.title[:100]}...**\n`{player.duration//60}:{player.duration%60:02d}`",
            color=0x00ff00
        )
        if player.data.get('thumbnail'):
            embed.set_thumbnail(url=player.data['thumbnail'])

        view = MusicControls()
        await interaction.followup.send(embed=embed, view=view)
        
        await play_next(interaction.guild)
        
    except Exception as e:
        embed = discord.Embed(title="❌ Error", description=f"Failed to load: `{str(e)[:50]}...`", color=0xff0000)
        await interaction.followup.send(embed=embed, ephemeral=True)

async def play_next(guild):
    if guild.id not in queues or not queues[guild.id]:
        return

    voice = discord.utils.get(bot.voice_clients, guild=guild)
    if not voice or not voice.is_connected():
        return

    player = queues[guild.id].popleft()
    
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{player.title[:100]}...**\n`{player.duration//60}:{player.duration%60:02d}`",
        color=0x0099ff
    )
    if player.data.get('thumbnail'):
        embed.set_thumbnail(url=player.data['thumbnail'])

    def after_playing(error):
        if error:
            print(f"Player error: {error}")
        if queues[guild.id]:
            asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

    voice.play(player, after=after_playing)
    
    channel = discord.utils.get(guild.text_channels, name="music") or guild.text_channels[-1]
    view = MusicControls()
    asyncio.create_task(channel.send(embed=embed, view=view))

@bot.tree.command(name="queue", description="Show current queue")
async def queue(interaction: discord.Interaction):
    if interaction.guild.id not in queues or not queues[interaction.guild.id]:
        embed = discord.Embed(title="📋 Queue", description="**Queue is empty**", color=0x808080)
    else:
        queue_list = []
        for i, song in enumerate(list(queues[interaction.guild.id])[:10], 1):
            dur = song.duration//60 if song.duration else 0
            queue_list.append(f"{i}. **{song.title[:50]}...** `{dur}m`")
        
        desc = "\n".join(queue_list)
        if len(queues[interaction.guild.id]) > 10:
            desc += f"\n\n...and **{len(queues[interaction.guild.id])-10}** more"
            
        embed = discord.Embed(title="📋 Music Queue", description=desc, color=0x00ff00)
    
    await interaction.response.send_message(embed=embed)

bot.run('MTM4NjAyNDE4ODUxODU5NjYxOA.GKF-Nx.mn2qLRDR7Di5qKhkb_B9Eyx6IzZE55HGPSRG1s')