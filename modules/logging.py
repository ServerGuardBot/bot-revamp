from database import DBConnection, loadQuery, resultExists
from humanfriendly import format_timespan
from core.embeds import EMBED_STANDARD
from core.checks import listener
from guilded.ext import commands
from datetime import datetime

import guilded

class Logging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @listener("logging")
    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": event.server.id})
            except:
                pass
            else:
                if resultExists(response):
                    data = response[0]["result"][0]

                    if data.get("logs_traffic"):
                        try:
                            channel = await self.bot.getch_channel(data["logs_traffic"])
                        except:
                            pass
                        else:
                            em: guilded.Embed = EMBED_STANDARD(
                                title=f"{event.member.mention} Joined",
                                url = event.member.profile_url,
                            )
                            em.set_thumbnail(url=event.member.display_avatar.url)
                            em.add_field(name="User ID", value=event.member.id)
                            em.add_field(name="Account created", value=format_timespan(datetime.now() - event.member.created_at))
                            # TODO: Implement toxicity and hatespeech filters and show them here
                            await channel.send(embed=em, silent=True)
    
    @listener("logging")
    @commands.Cog.listener()
    async def on_member_remove(self, event: guilded.MemberRemoveEvent):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": event.server.id})
            except:
                pass
            else:
                if resultExists(response):
                    data = response[0]["result"][0]

                    if data.get("logs_traffic"):
                        try:
                            channel = await self.bot.getch_channel(data["logs_traffic"])
                        except:
                            pass
                        else:
                            em: guilded.Embed = EMBED_STANDARD(
                                title=f"{event.member.mention} Left",
                                url = event.member.profile_url,
                                colour=(event.kicked or event.banned) and guilded.Colour.red() or guilded.Colour.gilded()
                            )
                            em.set_thumbnail(url=event.member.display_avatar.url)
                            em.add_field(name="User ID", value=event.member.id)
                            if event.member.created_at:
                                em.add_field(name="Account created", value=format_timespan(datetime.now() - event.member.created_at))
                            await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_ban_create(self, event: guilded.BanCreateEvent):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": event.server.id})
            except:
                pass
            else:
                if resultExists(response):
                    data = response[0]["result"][0]

                    if data.get("logs_traffic"):
                        try:
                            channel = await self.bot.getch_channel(data["logs_traffic"])
                        except:
                            pass
                        else:
                            em: guilded.Embed = EMBED_STANDARD(
                                title=f"{event.member.mention} Banned",
                                url = event.member.profile_url,
                                colour=guilded.Colour.red()
                            )
                            em.set_thumbnail(url=event.member.display_avatar.url)
                            em.add_field(name="User ID", value=event.member.id)
                            em.add_field(name="Banned by", value=event.ban.author.mention)
                            em.add_field(name="Reason", value=event.ban.reason, inline=False)
                            if event.member.created_at:
                                em.add_field(name="Account created", value=format_timespan(datetime.now() - event.member.created_at))
                            await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_ban_delete(self, event: guilded.BanDeleteEvent):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": event.server.id})
            except:
                pass
            else:
                if resultExists(response):
                    data = response[0]["result"][0]

                    if data.get("logs_traffic"):
                        try:
                            channel = await self.bot.getch_channel(data["logs_traffic"])
                        except:
                            pass
                        else:
                            em: guilded.Embed = EMBED_STANDARD(
                                title=f"{event.member.mention} Unbanned",
                                url = event.member.profile_url,
                                colour=guilded.Colour.gilded()
                            )
                            em.set_thumbnail(url=event.member.display_avatar.url)
                            em.add_field(name="User ID", value=event.member.id)
                            em.add_field(name="Banned by", value=event.ban.author.mention)
                            em.add_field(name="Reason", value=event.ban.reason, inline=False)
                            if event.member.created_at:
                                em.add_field(name="Account created", value=format_timespan(datetime.now() - event.member.created_at))
                            await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_message_delete(self, event: guilded.MessageDeleteEvent):
        from modules.automod import Automod
        automod_cog: Automod = self.bot.get_cog("automod")
        if await automod_cog.was_message_automoderated(event.message): return

        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": event.server.id})
            except:
                pass
            else:
                if resultExists(response):
                    data = response[0]["result"][0]

                    if data.get("logs_message"):
                        try:
                            channel = await self.bot.getch_channel(data["logs_message"])
                        except:
                            pass
                        else:
                            em: guilded.Embed = EMBED_STANDARD(
                                title=f"Message Deleted",
                                url = event.message.share_url,
                                colour=guilded.Colour.red()
                            )
                            em.set_thumbnail(url=event.message.author.display_avatar.url)
                            em.add_field(name="User ID", value=event.message.author.id)
                            em.add_field(name="Message ID", value=event.message.id)
                            em.add_field(name="Contents", value=event.message.content, inline=False)
                            await channel.send(embed=em, silent=True)

def setup(bot: commands.Bot):
    bot.add_cog(Logging(bot))