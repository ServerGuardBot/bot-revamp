from database import DBConnection, loadQuery, resultExists
from core.embeds import EMBED_FILTERED, EMBED_STANDARD
from core.checks import listener, is_module_enabled
from humanfriendly import format_timespan
from guilded.ext import commands, tasks
from bs4 import BeautifulSoup
from datetime import datetime
from zipfile import ZipFile

import requests
import guilded
import asyncio
import config
import csv
import io

def get_cooldown_key(message: guilded.ChatMessage):
    return (message.author.id, message.channel.id)

class Automod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.spam_cooldowns = {}
        self.malicious_urls = []
        self.guilded_paths = []
    
    async def was_message_automoderated(self, message: guilded.ChatMessage):
        while getattr(message, "automoderated", None) is None:
            await asyncio.sleep(0.1)
        return message.automoderated
    
    async def notify_filter(self, message, reason: str):
        if isinstance(message, guilded.ChatMessage):
            await message.reply(embed=EMBED_FILTERED(
                message.author,
                reason
            ), private=True)
        message.automoderated = True
    
    async def send_log(self, channel: guilded.ChatChannel, message: guilded.ChatMessage, filter: str, extraData: dict = {}):
        if not channel: return
        user = message.author
        em = EMBED_STANDARD(
            title=f"{filter} Filter Triggered",
            description=message.content,
            url=message.share_url,
        )
        em.set_thumbnail(user.display_avatar.url)
        em.add_field(name="Author", value=user.mention, inline=True)
        if extraData.get("certainty"):
            from base import BOT_VERSION
            em.set_footer(text=f"v{BOT_VERSION} {str.capitalize(config.DATABASE_DB)} • Certainty: {extraData['certainty']}%")
        if extraData.get("filtered"):
            em.add_field(name="Filtered Message", value=extraData["filtered"], inline=False)
        if extraData.get("threat"):
            em.add_field(name="Threat Category", value=extraData["threat"])
        await channel.send(embed=em, silent=True)
    
    async def filter_message(self, message):
        if not getattr(message, "server"): return
        if not getattr(message, "channel"): return
        if not getattr(message, "author"): return
        if message.author.bot: return
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": message.server.id})
            except:
                return
            else:
                if resultExists(response):
                    data = response[0]["result"][0]
                    log_channel_id = data.get("logs_automod")
                    log_channel = None
                    if log_channel_id:
                        try:
                            log_channel = await self.bot.getch_channel(log_channel_id)
                        except:
                            pass
                    spam_amt = data.get("spam_filter")
                    if spam_amt and spam_amt > 0:
                        guild_spam_cooldown = self.spam_cooldowns.get(message.server.id)
                        if not guild_spam_cooldown:
                            guild_spam_cooldown = commands.CooldownMapping.from_cooldown(spam_amt, 60, get_cooldown_key)
                            self.spam_cooldowns[message.server.id] = guild_spam_cooldown
                        if guild_spam_cooldown.update_rate_limit(message):
                            # TODO: Keep track of recent messages in the channel by a user
                            # TODO: and purge them when filter is hit
                            await message.delete()
                            await self.notify_filter(message, "Talking too fast!")
                            await self.send_log(log_channel, message, "Spam")
                            return
                    if data.get("malicious_urls", False):
                        for url in self.malicious_urls.keys():
                            if url in message.content:
                                await message.delete()
                                await self.notify_filter(message, "Malicious URL!")
                                await self.send_log(log_channel, message, "Malicious URL", {"threat": self.malicious_urls[url]})
                                return
    
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        event.message.automoderated = False

        if is_module_enabled(self, event):
            await self.filter_message(event.message)
    
    @commands.Cog.listener()
    async def on_bot_remove(self, event: guilded.BotRemoveEvent):
        if self.spam_cooldowns.get(event.server.id):
            del self.spam_cooldowns[event.server.id]
    
    @tasks.loop(minutes=30)
    async def refresh_cache(self):
        # Malicious URLs
        try:
            response = await requests.get('https://urlhaus.abuse.ch/downloads/csv/')
            zip = ZipFile(io.BytesIO(response.content))
            item = zip.open("csv.txt")
            reader = csv.reader(io.TextIOWrapper(item, "utf-8"))
        except Exception as e:
            print(f"Failed to refresh malicious URLs: {'{}: {}'.format(type(e).__name__, e)}")
        else:
            self.malicious_urls.clear()
            for row in reader:
                if len(row) < 2 or ("id" in row[0]): continue
                url = row[2]
                threat = row[5]
                self.malicious_urls[url] = threat
            print("Refreshed malicious URLs")
        # Guilded Paths
        try:
            response = await requests.get("https://www.guilded.gg/sitemap_landing.xml")
            soup = BeautifulSoup(response.text, "xml")
        except Exception as e:
            print(f"Failed to refresh Guilded Paths: {'{}: {}'.format(type(e).__name__, e)}")
        else:
            self.guilded_paths.clear()
            for tag in soup.find_all("url"):
                loc = tag.loc
                if loc:
                    self.guilded_paths.append(loc.string[23:].lower())
            print("Refreshed Guilded Paths")

def setup(bot: commands.Bot):
    bot.add_cog(Automod(bot))