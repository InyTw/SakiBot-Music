import discord
from discord.ext import commands
import datetime
import os
import re

class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # --- 動態抓取根目錄路徑 ---
        # 這樣寫可以確保無論在哪啟動，log 都會準確出現在 SakiBot-Music/log 裡
        current_dir = os.path.dirname(os.path.abspath(__file__)) # cogs 資料夾
        base_dir = os.path.dirname(current_dir) # 專案根目錄
        
        self.log_dir = os.path.join(base_dir, "log")
        self.log_file = os.path.join(self.log_dir, "add_log.txt")
        
        # 啟動時確保 log 資料夾存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            print(f"📁 已自動建立日誌資料夾: {self.log_dir}")

    def write_log(self, content):
        """將內容寫入 log/add_log.txt"""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content + "\n" + "-"*30 + "\n")

    def get_logged_ids(self):
        """從 log/add_log.txt 讀取已經記錄過的伺服器 ID"""
        if not os.path.exists(self.log_file):
            return set()
        
        logged_ids = set()
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                # 使用正則表達式精準抓取 ID: 之後的數字
                found = re.findall(r"ID:\s*(\d+)", line)
                for id_str in found:
                    logged_ids.add(int(id_str))
        return logged_ids

    @commands.Cog.listener()
    async def on_ready(self):
        """啟動時檢查並補登"""
        # 等待機器人內部緩存準備好，確保 guilds 列表是完整的
        await self.bot.wait_until_ready()
        
        print(f"🔍 正在掃描 {len(self.bot.guilds)} 個伺服器清單...")
        
        logged_ids = self.get_logged_ids()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_records = 0

        for guild in self.bot.guilds:
            if guild.id not in logged_ids:
                log_content = (
                    f"[{current_time}] 補登：啟動時偵測到已存在的伺服器\n"
                    f"server: {guild.name} (ID: {guild.id})\n"
                    f"user: 系統自動補登\n"
                    f"成員數: {guild.member_count}"
                )
                self.write_log(log_content)
                new_records += 1
        
        if new_records > 0:
            print(f"✅ 補登完成，共記錄了 {new_records} 個伺服器到 {self.log_file}")
        else:
            print(f"✨ 所有伺服器皆已記錄在案。")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """即時記錄新加入"""
        inviter = "未知 (無權限或直接安裝)"
        try:
            # 檢查機器人是否有權限查看審核日誌
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
                    if entry.target.id == self.bot.user.id:
                        inviter = f"{entry.user} (ID: {entry.user.id})"
                        break
        except Exception as e:
            print(f"嘗試抓取邀請人時出錯: {e}")

        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = (
            f"[{time_str}] 機器人加入新伺服器\n"
            f"server: {guild.name} (ID: {guild.id})\n"
            f"user: {inviter}\n"
            f"成員數: {guild.member_count}"
        )
        self.write_log(log_content)
        print(f"📥 已將新伺服器 {guild.name} 寫入日誌檔。")

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))