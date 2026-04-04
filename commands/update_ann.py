import discord
from discord.ext import commands

class UpdateAnn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="update", description="發布小祥音樂更新公告")
    async def update_info(self, ctx):
        embed = discord.Embed(
            title="📢 小祥音樂更新公告 | Update Notice",
            description="v.1.0.1 版本更新公告",
            color=0x3498db
        )

        embed.add_field(
            name="<a:sakiko_music:1485303402564026408> [**[小祥音樂 最新更新內容]**](https://www.ohw.cloud-ip.cc/saki_music.html)",
            value=(
                "進入小祥音樂的更新頁面，查看最新的更新內容和公告！\n"
            ),
            inline=False
        )

        embed.set_footer(text="祝您盡早變神人！")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UpdateAnn(bot)) 