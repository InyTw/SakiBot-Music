import discord
from discord.ext import commands

class UpdateAnnDev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="update_dev", description="發布小祥音樂更新公告")
    async def update_info(self, ctx):
        embed = discord.Embed(
            title="📢 小祥音樂更新公告 (工作人員版本) | Update Notice (STAFF version)",
            description="為了提供更穩定的播放體驗，我們對機器人進行了以下調整：",
            color=0x3498db
        )

        embed.add_field(
            name="<a:sakiko_music:1485303402564026408> 功能調整",
            value=(
                "**1. 暫時移除 Spotify 連結搜尋**\n"
                "目前 Spotify API 限制尚未解決，未來可能會移除此功能。\n"
                "**玩家不須擔心，其他功能正常使用：**\n"
                "👉 `/play [YT 連結]`\n"
                "👉 `/play [音樂歌名/歌手]`\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎨 介面更新",
            value=(
                "**2. Embed 面板優化**\n"
                "目前的樣式以目前為主。若有神人想要提供修改建議，\n"
                "可以私訊我或到伺服器的 **<#1487086827029397595>** 提出！\n"
            ),
            inline=False
        )

        embed.set_footer(text="最後更新日期：2026/03/27 • 任何問體也請管理員到 ohw 的客服單，以便做處理")
        
        await ctx.send(content="給管理員看的\n也請工作人員公告給玩家使用 !update 來查詢更新內容", embed=embed)

async def setup(bot):
    await bot.add_cog(UpdateAnnDev(bot))