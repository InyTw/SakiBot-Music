import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# --- 設定區 ---
# 請將這裡替換成你那則「特定公告訊息」的 ID
# 你可以先執行一次 /help，然後右鍵點擊該訊息 -> 複製 ID 填入這裡
TARGET_MESSAGE_ID = 1488928949957300344

class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="音樂功能", description="查看音樂播放相關指令", emoji="🎵"),
            discord.SelectOption(label="客服系統", description="查看如何開啟客服單", emoji="🎫"),
            discord.SelectOption(label="一般/更新", description="查看公告與一般指令", emoji="📢"),
        ]
        super().__init__(
            placeholder="請選擇你想查看的指令分類...", 
            options=options, 
            custom_id="persistent:help_select"
        )

    async def callback(self, interaction: discord.Interaction):
        # 1. 定義分類內容
        embed = discord.Embed(color=0x3498db)
        if self.values[0] == "音樂功能":
            embed.title = "🎵 音樂功能指令"
            embed.description = "👉 `/play [連結/歌名]` - 播放音樂\n"
        elif self.values[0] == "客服系統":
            embed.title = "🎫 客服系統指令"
            embed.description = "👉 <#1487086827029397595>\n👉 `/close` - 關閉目前的客服單頻道"
        elif self.values[0] == "一般/更新":
            embed.title = "📢 一般與更新指令"
            embed.description = "👉 `!update` - 發送最新的機器人更新公告\n👉 `/help` - 顯示此幫助選單"

        # --- 核心判斷：檢查是否為該則特定訊息 ---
        if interaction.message.id == TARGET_MESSAGE_ID:
            embed.set_footer(text="提示：此公告選單將在 1 分鐘後重設")
            await interaction.response.edit_message(embed=embed)

            # 只有特定訊息才執行倒數
            await asyncio.sleep(60)

            # 重新產生首頁 Embed
            home_embed = discord.Embed(
                title="🏮 小祥音樂 | 客服中心(指令列表)",
                description="我是豐川集團大小姐 aka [Ave Mujica](https://zh.wikipedia.org/zh-tw/Ave_Mujica) 的神人！...",
                color=discord.Color.gold()
            )
            home_embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            home_embed.add_field(name="✨ 快速連結", value="[建議回報](https://discord.com/channels/1466688887102505107/1487086827029397595) | [官方網站](https://www.ohw.cloud-ip.cc)", inline=False)

            try:
                # 重設回首頁
                await interaction.edit_original_response(embed=home_embed, view=self.view)
            except:
                pass
        else:
            # 一般使用者隨手打的 /help (或者是 ephemeral 訊息)
            embed.set_footer(text="提示：點擊下方選單可以切換分類")
            await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(HelpSelect(bot))

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(HelpView(self.bot))
        print("✅ 幫助選單持久化 View 已掛載完成")

    @app_commands.command(name="help", description="顯示機器人的幫助選單與功能介紹")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏮 小祥音樂 | 客服中心(指令列表)",
            description="我是豐川集團大小姐 aka [Ave Mujica](https://zh.wikipedia.org/zh-tw/Ave_Mujica) 的神人！...",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        # 這裡建議 ephemeral 設為 True，這樣一般使用者用指令時不會洗掉頻道訊息
        await interaction.response.send_message(embed=embed, view=HelpView(self.bot), ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))