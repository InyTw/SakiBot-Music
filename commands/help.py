import discord
from discord.ext import commands
from discord import app_commands

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="音樂功能", description="查看音樂播放相關指令", emoji="🎵"),
            discord.SelectOption(label="客服系統", description="查看如何開啟客服單", emoji="🎫"),
            discord.SelectOption(label="一般/更新", description="查看公告與一般指令", emoji="📢"),
        ]
        # 設定 custom_id 以便重啟後依然有效
        super().__init__(placeholder="請選擇你想查看的指令分類...", options=options, custom_id="persistent:help_select")

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(color=0x3498db)
        
        if self.values[0] == "音樂功能":
            embed.title = "🎵 音樂功能指令"
            embed.description = (
                "👉 `/play [連結/歌名]` - 播放音樂"
            )
            
        elif self.values[0] == "客服系統":
            embed.title = "🎫 客服系統指令"
            embed.description = (
                "👉 `/setup_ticket` - [管理員] 設定開單面板\n"
                "👉 `/close` - 關閉目前的客服單頻道"
            )
            
        elif self.values[0] == "一般/更新":
            embed.title = "📢 一般與更新指令"
            embed.description = (
                "👉 `!update` - 發送最新的機器人更新公告\n"
                "👉 `/help` - 顯示此幫助選單"
            )

        embed.set_footer(text="提示：點擊下方選單可以切換分類")
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 機器人啟動時自動掛載選單監聽
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(HelpView())

    @app_commands.command(name="help", description="顯示機器人的幫助選單與功能介紹")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏮 小祥音樂 | 客服中心(指令列表)",
            description="我是豐川集團大小姐 aka [Ave Mujica](https://zh.wikipedia.org/zh-tw/Ave_Mujica) 的神人！，請從下方下拉選單中選擇你想了解的功能分類。",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="✨ 快速連結", value="[建議回報](https://discord.com/channels/1466688887102505107/1487086827029397595/1487131749610819607) | [官方網站](https://www.ohw.cloud-ip.cc)", inline=False)
        
        await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))