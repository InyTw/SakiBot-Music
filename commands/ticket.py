import discord
from discord.ext import commands
from discord import app_commands
import datetime

# --- 設定區 ---
TICKET_CATEGORY_ID = 1487097289041379488

# --- 申請表單 (Modal 不需要持久化，因為它是被 View 觸發的) ---
class StaffApplyModal(discord.ui.Modal, title='OHW 客服單 - 工作人員申請'):
    duration = discord.ui.TextInput(label="接觸過多久？", placeholder="請填寫數字 (例如: 12個月)", min_length=1, required=True)
    position = discord.ui.TextInput(label="想申請的職位？", placeholder="管理員 / 建築師 / 一般工作人員", required=True)
    experience = discord.ui.TextInput(label="是否從事過相關領域？", placeholder="是 / 否 (若有請簡述)", required=True)
    portfolio = discord.ui.TextInput(label="作品集", placeholder="請貼上連結...", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📋 申請資訊：工作人員", color=discord.Color.blue())
        embed.add_field(name="相關經驗", value=self.experience.value, inline=True)
        embed.add_field(name="接觸時長", value=self.duration.value, inline=True)
        embed.add_field(name="申請職位", value=self.position.value, inline=True)
        embed.add_field(name="作品/附件", value=self.portfolio.value or "無", inline=False)
        embed.set_footer(text=f"申請人: {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message("✅ 申請表單已送出。", embed=embed)

class YoutubeApplyModal(discord.ui.Modal, title='OHW 客服單 - YouTube Rank 申請'):
    years = discord.ui.TextInput(label="是否已當 YouTube 超過 2 年？", placeholder="是 / 否", required=True)
    channel_url = discord.ui.TextInput(label="YouTube 頻道連結", placeholder="https://youtube.com/...", required=True)
    promo_url = discord.ui.TextInput(label="伺服器宣傳片連結", placeholder="...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📋 申請資訊：YouTube Rank", color=discord.Color.red())
        embed.add_field(name="資歷超過2年", value=self.years.value, inline=True)
        embed.add_field(name="頻道連結", value=self.channel_url.value, inline=False)
        embed.add_field(name="宣傳影片", value=self.promo_url.value, inline=False)
        embed.set_footer(text=f"申請人: {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message("✅ YouTube Rank 申請已送出。", embed=embed)

# --- 申請類型的下拉選單 (也需要設定持久化) ---
class ApplyTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 持久化關鍵 1

    @discord.ui.select(
        placeholder="請選擇你想申請的分類...", 
        options=[
            discord.SelectOption(label="工作人員", description="申請管理員、建築師等職位", emoji="🛠️"),
            discord.SelectOption(label="YouTube Rank", description="申請創作者身分", emoji="🎥"),
        ],
        custom_id="persistent:apply_select" # 持久化關鍵 2
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "工作人員":
            await interaction.response.send_modal(StaffApplyModal())
        else:
            await interaction.response.send_modal(YoutubeApplyModal())

# --- 主選單按鈕 (持久化核心) ---
class TicketLauncher(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 持久化關鍵 1

    async def create_ticket(self, interaction: discord.Interaction, category: str):
        guild = interaction.guild
        user = interaction.user
        target_category = guild.get_channel(TICKET_CATEGORY_ID)
        channel_name = f"單-{category}-{user.name}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        try:
            ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=target_category)
            embed = discord.Embed(
                title=f"🎫 OHW 客服單 - {category}",
                description=f"你好 {user.mention}，歡迎來到客服中心。\n輸入 `/close` 以關閉此單。",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            await interaction.response.send_message(f"✅ 客服單已建立: {ticket_channel.mention}", ephemeral=True)
            
            if category == "申請":
                await ticket_channel.send(embed=embed, view=ApplyTypeView())
            else:
                await ticket_channel.send(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ 錯誤: {e}", ephemeral=True)

    # 每個按鈕都必須有唯一的 custom_id
    @discord.ui.button(label="檢舉", style=discord.ButtonStyle.danger, custom_id="persistent:report")
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "檢舉")

    @discord.ui.button(label="申請", style=discord.ButtonStyle.primary, custom_id="persistent:apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "申請")

    @discord.ui.button(label="建議", style=discord.ButtonStyle.secondary, custom_id="persistent:suggest")
    async def suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "建議")

    @discord.ui.button(label="贊助", style=discord.ButtonStyle.success, custom_id="persistent:donate")
    async def donate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "贊助")

# --- Cog 主體 ---
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 關鍵：機器人啟動時重新掛載 View
    @commands.Cog.listener()
    async def on_ready(self):
        # 註冊主面板的 View
        self.bot.add_view(TicketLauncher())
        # 註冊申請單內下拉選單的 View
        self.bot.add_view(ApplyTypeView())
        print("✅ 客服單持久化 View 已掛載完成")

    @app_commands.command(name="setup_ticket", description="[管理員] 設定客服單開單面板")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_ticket(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 OHW 客服系統",
            description="如果您遇到遊戲問題、儲值問題或檢舉玩家，請點擊下方按鈕開啟客服單\n\nYouTube Rank 申請資格:\n1. 需要有1000訂閱\n2. 至少1部影片(不包含shorts)擁有1000觀看\n3. 需要拍一部宣傳片，且觀看需擁有500觀看(Shorts不算)\n\n如果您有任何問題，請隨時聯繫我們的客服團隊！",
            color=discord.Color.gold()
        )
        await interaction.response.send_message("✅ 面板已送出", ephemeral=True)
        await interaction.channel.send(embed=embed, view=TicketLauncher())

    @app_commands.command(name="close", description="關閉當前客服單")
    async def close(self, interaction: discord.Interaction):
        if "單-" not in interaction.channel.name:
            return await interaction.response.send_message("❌ 請在客服單內使用", ephemeral=True)
        
        # 關閉確認按鈕不需要持久化，因為它是即時生成的
        view = discord.ui.View()
        btn = discord.ui.Button(label="確認關閉", style=discord.ButtonStyle.red)
        async def confirm_callback(intx):
            await intx.channel.delete()
        btn.callback = confirm_callback
        view.add_item(btn)

        await interaction.response.send_message("確定要關閉嗎？", view=view)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))