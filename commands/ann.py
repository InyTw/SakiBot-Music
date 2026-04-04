import discord
from discord.ext import commands

class Ann(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ann", description="發布小祥音樂公告")
    async def update_info(self, ctx):
        embed = discord.Embed(
            title="📢 小祥音樂 公告 | Update Notice",
            color=0x3498db
        )
        
        embed.add_field(
            name="機器人無法播放音樂問題...",
            value=(
                "目前的狀況是機器人無法使用任何指令\n"
                "原因可能是後台面板的某些功能出現了問題，導致機器人無法正常運行\n"
                "我們正在積極調查並修復這個問題，請耐心等待\n"
                "如果您有任何相關的資訊或建議，歡迎隨時聯繫我們！\n"
            ),
            inline=False
        )

        embed.add_field(
            name="<a:sakiko_music:1485303402564026408> 小祥音樂 ➤ https://www.ohw.cloud-ip.cc/saki_docs.html",
            value=(
                "進入小祥音樂的更新頁面，查看最新的更新內容和公告！\n"
            ),
            inline=False
        )

        embed.set_footer(text="祝您盡早變神人！")
        await ctx.send(content="@everyone", embed=embed)

async def setup(bot):
    await bot.add_cog(Ann(bot)) 