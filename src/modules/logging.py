from humanfriendly import format_timespan
from core.embeds import EMBED_STANDARD
from modules.automod import Automod
from core.checks import listener
from guilded.ext import commands
from datetime import datetime

import database as db
import guilded


class Logging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @listener("logging")
    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
        automod: Automod = self.bot.get_cog("Automod")
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_traffic"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_traffic"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"{event.member.mention} Joined",
                        url=event.member.profile_url,
                    )
                    em.set_thumbnail(url=event.member.display_avatar.url)
                    em.add_field(name="User ID", value=event.member.id)
                    em.add_field(name="Account Age", value=format_timespan(
                        datetime.now() - event.member.created_at))

                    if automod.filters_ready and (guild.settings.get("filter_toxicity", 0) > 0 or guild.settings.get("filter_hatespeech", 0)):
                        for field in ["display_name", "bio"]:
                            content = getattr(event.member, field, None)
                            if content:
                                toxicity, hatespeech = automod.apply_filters(
                                    content)
                                if field == "display_name":
                                    name = "Name %s"
                                else:
                                    name = field.title() + " %s"
                                if guild.settings.get("filter_toxicity", 0) > 0:
                                    em.add_field(name=name.format(
                                        "(Toxicity)"), value=f"{round(toxicity * 100)}%")
                                if guild.settings.get("filter_hatespeech", 0) > 0:
                                    em.add_field(name=name.format(
                                        "(Hate Speech)"), value=f"{round(hatespeech * 100)}%")

                    if guild.settings.get("premium", "0")[0] == "1" and guild.settings.get("filter_nsfw", 0) > 0:
                        user = await self.bot.getch_user(event.member.id)
                        urls = {
                            "banner": user.banner and user.banner.url or None,
                            "avatar": user.display_avatar.url
                        }
                        for field, url in urls.items():
                            if url:
                                nudity = round(
                                    automod.scan_nsfw(url=url) * 100)
                                if nudity >= guild.settings["filter_nsfw"] or nudity >= 50:
                                    try:
                                        nsfw_log_channel = await self.bot.getch_channel(guild.settings.get("logs_nsfw"))
                                    except:
                                        pass
                                    else:
                                        em2 = EMBED_STANDARD(
                                            title=f"NSFW {field.title()}",
                                            colour=guilded.Colour.red() if (
                                                nudity >= guild.settings["filter_nsfw"] or nudity >= 50) else guilded.Colour.orange(),
                                            url=user.profile_url
                                        )
                                        em2.set_thumbnail(
                                            url=user.display_avatar.url)
                                        em2.set_image(url=url)
                                        await nsfw_log_channel.send(embed=em2)

                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_member_remove(self, event: guilded.MemberRemoveEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_traffic"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_traffic"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"{event.member.mention} Left",
                        url=event.member.profile_url,
                        colour=(event.kicked or event.banned) and guilded.Colour.red(
                        ) or guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.member.display_avatar.url)
                    em.add_field(name="User ID", value=event.member.id)
                    if event.member.created_at:
                        em.add_field(name="Account Age", value=format_timespan(
                            datetime.now() - event.member.created_at))
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_member_update(self, event: guilded.MemberUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:

            if guild.settings.get("logs_user"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_user"])
                except:
                    pass
                else:
                    if event.before.nick != event.after.nick:
                        em: guilded.Embed = EMBED_STANDARD(
                            title=f"{event.after.mention} Nickname Changed",
                            url=event.after.profile_url,
                            colour=guilded.Colour.gilded()
                        )
                        em.set_thumbnail(url=event.after.display_avatar.url)
                        em.add_field(name="User ID", value=event.after.id)
                        em.add_field(
                            name="Before", value=event.before.nick or "None")
                        em.add_field(
                            name="Now", value=event.after.nick or "None")
                        await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_bulk_member_roles_update(self, event: guilded.BulkMemberRolesUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:

            if guild.settings.get("logs_user") and guild.settings.get("log_roles"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_user"])
                except:
                    pass
                else:
                    for member in event.after:
                        em: guilded.Embed = EMBED_STANDARD(
                            title=f"{member.mention} Roles Changed",
                            url=member.profile_url,
                            colour=guilded.Colour.gilded()
                        )
                        em.set_thumbnail(url=member.display_avatar.url)
                        em.add_field(name="User ID", value=member.id)
                        for other in event.before:
                            if other.id == member.id:
                                em.add_field(name="Roles Before", value=", ".join(
                                    [role.mention for role in other.roles]), inline=False)
                                break
                        em.add_field(name="Roles Now", value=", ".join(
                            [role.mention for role in member.roles]), inline=False)
                        await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_ban_create(self, event: guilded.BanCreateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:

            if guild.settings.get("logs_traffic"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_traffic"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"{event.member.mention} Banned",
                        url=event.member.profile_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.member.display_avatar.url)
                    em.add_field(name="User ID", value=event.member.id)
                    em.add_field(name="Banned by",
                                 value=event.ban.author.mention)
                    em.add_field(
                        name="Reason", value=event.ban.reason, inline=False)
                    if event.member.created_at:
                        em.add_field(name="Account created", value=format_timespan(
                            datetime.now() - event.member.created_at))
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_ban_delete(self, event: guilded.BanDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:

            if guild.settings.get("logs_traffic"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_traffic"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"{event.member.mention} Unbanned",
                        url=event.member.profile_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.member.display_avatar.url)
                    em.add_field(name="User ID", value=event.member.id)
                    em.add_field(name="Banned by",
                                 value=event.ban.author.mention)
                    em.add_field(
                        name="Reason", value=event.ban.reason, inline=False)
                    if event.member.created_at:
                        em.add_field(name="Account created", value=format_timespan(
                            datetime.now() - event.member.created_at))
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_message_delete(self, event: guilded.MessageDeleteEvent):
        from modules.automod import Automod
        automod_cog: Automod = self.bot.get_cog("Automod")
        if await automod_cog.was_message_automoderated(event.message):
            return
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Message Deleted",
                        url=event.message.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(
                        url=event.message.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.message.author.id)
                    em.add_field(name="Message ID", value=event.message.id)
                    em.add_field(name="Contents",
                                 value=event.message.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_message_update(self, event: guilded.MessageUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Message Edited",
                        url=event.after.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.after.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.after.author.id)
                    em.add_field(name="Message ID", value=event.after.id)
                    em.add_field(name="Pinned", value=event.after.pinned)
                    if event.before:
                        em.add_field(
                            name="Before", value=event.before.content, inline=False)
                    em.add_field(
                        name="After", value=event.after.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_update(self, event: guilded.ForumTopicUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Updated",
                        url=event.topic.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.topic.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.topic.author.id)
                    em.add_field(name="Topic ID", value=event.topic.id)
                    em.add_field(
                        name="Title", value=event.topic.title, inline=False)
                    em.add_field(name="Contents",
                                 value=event.topic.content, inline=False)
                    em.add_field(name="Pinned", value=event.topic.pinned)
                    em.add_field(name="Locked", value=event.topic.locked)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_delete(self, event: guilded.ForumTopicDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Deleted",
                        url=event.topic.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.topic.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.topic.author.id)
                    em.add_field(name="Topic ID", value=event.topic.id)
                    em.add_field(
                        name="Title", value=event.topic.title, inline=False)
                    em.add_field(name="Contents",
                                 value=event.topic.content, inline=False)
                    em.add_field(name="Pinned", value=event.topic.pinned)
                    em.add_field(name="Locked", value=event.topic.locked)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_pin(self, event: guilded.ForumTopicPinEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Pinned",
                        url=event.topic.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.topic.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.topic.author.id)
                    em.add_field(name="Topic ID", value=event.topic.id)
                    em.add_field(
                        name="Title", value=event.topic.title, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_unpin(self, event: guilded.ForumTopicUnpinEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Unpinned",
                        url=event.topic.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.topic.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.topic.author.id)
                    em.add_field(name="Topic ID", value=event.topic.id)
                    em.add_field(
                        name="Title", value=event.topic.title, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_lock(self, event: guilded.ForumTopicLockEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Locked",
                        url=event.topic.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.topic.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.topic.author.id)
                    em.add_field(name="Topic ID", value=event.topic.id)
                    em.add_field(
                        name="Title", value=event.topic.title, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_unlock(self, event: guilded.ForumTopicUnlockEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Unlocked",
                        url=event.topic.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.topic.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.topic.author.id)
                    em.add_field(name="Topic ID", value=event.topic.id)
                    em.add_field(
                        name="Title", value=event.topic.title, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_reply_update(self, event: guilded.ForumTopicReplyUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Reply Updated",
                        url=event.reply.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Topic ID", value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_forum_topic_reply_delete(self, event: guilded.ForumTopicReplyDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Forum Topic Reply Deleted",
                        url=event.reply.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Topic ID", value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_doc_update(self, event: guilded.DocUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Doc Updated",
                        url=event.doc.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.doc.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.doc.author.id)
                    em.add_field(name="Doc ID", value=event.doc.id)
                    em.add_field(
                        name="Title", value=event.doc.title, inline=False)
                    em.add_field(name="Contents", value=(event.doc.content[:97] + "...") if len(
                        event.doc.content) > 97 else event.doc.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_doc_delete(self, event: guilded.DocDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Doc Deleted",
                        url=event.doc.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.doc.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.doc.author.id)
                    em.add_field(name="Doc ID", value=event.doc.id)
                    em.add_field(
                        name="Title", value=event.doc.title, inline=False)
                    em.add_field(name="Contents", value=(event.doc.content[:97] + "...") if len(
                        event.doc.content) > 97 else event.doc.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_doc_reply_update(self, event: guilded.DocReplyUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Doc Reply Updated",
                        url=event.reply.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Doc ID", value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_doc_reply_delete(self, event: guilded.DocReplyDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Doc Reply Deleted",
                        url=event.reply.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Doc ID", value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_announcement_update(self, event: guilded.AnnouncementUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Announcement Updated",
                        url=event.announcement.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(
                        url=event.announcement.author.display_avatar.url)
                    em.add_field(name="User ID",
                                 value=event.announcement.author.id)
                    em.add_field(name="Announcement ID",
                                 value=event.announcement.id)
                    em.add_field(
                        name="Title", value=event.announcement.title, inline=False)
                    em.add_field(name="Contents", value=(event.announcement.content[:97] + "...") if len(
                        event.announcement.content) > 97 else event.announcement.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_announcement_delete(self, event: guilded.AnnouncementDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Announcement Deleted",
                        url=event.announcement.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(
                        url=event.announcement.author.display_avatar.url)
                    em.add_field(name="User ID",
                                 value=event.announcement.author.id)
                    em.add_field(name="Announcement ID",
                                 value=event.announcement.id)
                    em.add_field(
                        name="Title", value=event.announcement.title, inline=False)
                    em.add_field(name="Contents", value=(event.announcement.content[:97] + "...") if len(
                        event.announcement.content) > 97 else event.announcement.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_announcement_reply_update(self, event: guilded.AnnouncementReplyUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Announcement Reply Updated",
                        url=event.reply.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Announcement ID",
                                 value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_announcement_reply_delete(self, event: guilded.AnnouncementReplyDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Announcement Reply Deleted",
                        url=event.reply.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Announcement ID",
                                 value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_calendar_event_update(self, event: guilded.CalendarEventUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Calendar Event Updated",
                        url=event.calendar_event.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(
                        url=event.calendar_event.author.display_avatar.url)
                    em.add_field(name="User ID",
                                 value=event.calendar_event.author.id)
                    em.add_field(name="Calendar Event ID",
                                 value=event.calendar_event.id)
                    em.add_field(
                        name="Name", value=event.calendar_event.name, inline=False)
                    em.add_field(
                        name="Description", value=event.calendar_event.description, inline=False)
                    em.add_field(name="Location",
                                 value=event.calendar_event.location or "None")
                    em.add_field(
                        name="URL", value=event.calendar_event.url or "None")
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_calendar_event_delete(self, event: guilded.CalendarEventDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Calendar Event Deleted",
                        url=event.calendar_event.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(
                        url=event.calendar_event.author.display_avatar.url)
                    em.add_field(name="User ID",
                                 value=event.calendar_event.author.id)
                    em.add_field(name="Calendar Event ID",
                                 value=event.calendar_event.id)
                    em.add_field(
                        name="Name", value=event.calendar_event.name, inline=False)
                    em.add_field(
                        name="Description", value=event.calendar_event.description, inline=False)
                    em.add_field(name="Location",
                                 value=event.calendar_event.location or "None")
                    em.add_field(
                        name="URL", value=event.calendar_event.url or "None")
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_calendar_event_reply_update(self, event: guilded.CalendarEventReplyUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Calendar Event Reply Updated",
                        url=event.reply.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Calendar Event ID",
                                 value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_calendar_event_reply_delete(self, event: guilded.CalendarEventReplyDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Calendar Event Reply Deleted",
                        url=event.reply.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.reply.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.reply.author.id)
                    em.add_field(name="Calendar Event ID",
                                 value=event.reply.parent_id)
                    em.add_field(name="Contents",
                                 value=event.reply.content, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_list_item_update(self, event: guilded.ListItemUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"List Item Updated",
                        url=event.item.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(url=event.item.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.item.author.id)
                    em.add_field(name="Message",
                                 value=event.item.message, inline=False)
                    em.add_field(
                        name="Note", value=event.item.note, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_list_item_delete(self, event: guilded.ListItemDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"List Item Deleted",
                        url=event.item.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.item.author.display_avatar.url)
                    em.add_field(name="User ID", value=event.item.author.id)
                    em.add_field(name="Message",
                                 value=event.item.message, inline=False)
                    em.add_field(
                        name="Note", value=event.item.note, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_list_item_complete(self, event: guilded.ListItemCompleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"List Item Completed",
                        url=event.item.share_url,
                        colour=guilded.Colour.green()
                    )
                    em.set_thumbnail(url=event.item.author.display_avatar.url)
                    em.add_field(name="Author ID", value=event.item.author.id)
                    em.add_field(name="Message",
                                 value=event.item.message, inline=False)
                    em.add_field(
                        name="Note", value=event.item.note, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_list_item_uncomplete(self, event: guilded.ListItemUncompleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_message"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_message"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"List Item Uncompleted",
                        url=event.item.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(url=event.item.author.display_avatar.url)
                    em.add_field(name="Author ID", value=event.item.author.id)
                    em.add_field(name="Message",
                                 value=event.item.message, inline=False)
                    em.add_field(
                        name="Note", value=event.item.note, inline=False)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_server_channel_create(self, event: guilded.ServerChannelCreateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_management"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_management"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Channel \"{event.channel.name}\" Created",
                        description=f"In category \"{event.channel.category.name if event.channel.category else 'None'}\"",
                        url=event.channel.share_url,
                        colour=guilded.Colour.green()
                    )
                    em.set_thumbnail(
                        url=event.channel.group.display_avatar.url if event.channel.group else event.channel.server.display_avatar.url)
                    em.add_field(name="Channel ID", value=event.channel.id)
                    em.add_field(name="Channel Type",
                                 value=event.channel.type.name.capitalize())
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_server_channel_delete(self, event: guilded.ServerChannelDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_management"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_management"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Channel \"{event.channel.name}\" Deleted",
                        description=f"In category \"{event.channel.category.name if event.channel.category else 'None'}\"",
                        url=event.channel.share_url,
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(
                        url=event.channel.group.display_avatar.url if event.channel.group else event.channel.server.display_avatar.url)
                    em.add_field(name="Channel ID", value=event.channel.id)
                    em.add_field(name="Channel Type",
                                 value=event.channel.type.name.capitalize())

    @listener("logging")
    @commands.Cog.listener()
    async def on_server_channel_update(self, event: guilded.ServerChannelUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_management"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_management"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Channel \"{event.channel.name}\" Updated",
                        description=f"In category \"{event.channel.category.name if event.channel.category else 'None'}\"",
                        url=event.channel.share_url,
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(
                        url=event.channel.group.display_avatar.url if event.channel.group else event.channel.server.display_avatar.url)
                    em.add_field(name="Channel ID", value=event.channel.id)
                    if event.before:
                        if event.before.name != event.after.name:
                            em.add_field(name="Previous Name",
                                         value=event.before.name)
                            em.add_field(name="New Name",
                                         value=event.after.name)
                        if event.before.category != event.after.category:
                            em.add_field(
                                name="Previous Category", value=event.before.category.name if event.before.category else "None")
                            em.add_field(
                                name="New Category", value=event.after.category.name if event.after.category else "None")
                        if event.before.topic != event.after.topic:
                            em.add_field(name="Previous Topic",
                                         value=event.before.topic)
                            em.add_field(name="New Topic",
                                         value=event.after.topic)
                        if event.before.group_id != event.after.group_id:
                            em.add_field(
                                name="Previous Group", value=event.before.group.name if event.before.group else "None")
                            em.add_field(
                                name="New Group", value=event.after.group.name if event.after.group else "None")

                        if event.before.archived_by_id is None and event.after.archived_by_id is not None:
                            em2: guilded.Embed = EMBED_STANDARD(
                                title=f"Channel \"{event.channel.name}\" Archived",
                                description=f"By <@{event.after.archived_by_id}>",
                                url=event.channel.share_url,
                                colour=guilded.Colour.red()
                            )
                            em2.set_thumbnail(
                                url=event.channel.group.display_avatar.url if event.channel.group else event.channel.server.display_avatar.url)
                            em2.add_field(name="Channel ID",
                                          value=event.channel.id)
                            await channel.send(embed=em2, silent=True)
                        elif event.before.archived_by_id is not None and event.after.archived_by_id is None:
                            em2: guilded.Embed = EMBED_STANDARD(
                                title=f"Channel \"{event.channel.name}\" Unarchived",
                                description=f"Previously archived by <@{event.before.archived_by_id}>",
                                url=event.channel.share_url,
                                colour=guilded.Colour.green()
                            )
                            em2.set_thumbnail(
                                url=event.channel.group.display_avatar.url if event.channel.group else event.channel.server.display_avatar.url)
                            em2.add_field(name="Channel ID",
                                          value=event.channel.id)
                            await channel.send(embed=em2, silent=True)
                    else:
                        em.add_field(name="Unknown Changes",
                                     value="Could not compare changes.")
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_category_create(self, event: guilded.CategoryCreateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_management"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_management"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Category \"{event.category.name}\" Created",
                        description=f"In group \"{event.category.group.name if event.category.group else 'None'}\"",
                        colour=guilded.Colour.green()
                    )
                    em.set_thumbnail(
                        url=event.category.group.display_avatar.url if event.category.group else event.category.server.display_avatar.url)
                    em.add_field(name="Category ID", value=event.category.id)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_category_delete(self, event: guilded.CategoryDeleteEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_management"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_management"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Category \"{event.category.name}\" Deleted",
                        description=f"In group \"{event.category.group.name if event.category.group else 'None'}\"",
                        colour=guilded.Colour.red()
                    )
                    em.set_thumbnail(
                        url=event.category.group.display_avatar.url if event.category.group else event.category.server.display_avatar.url)
                    em.add_field(name="Category ID", value=event.category.id)
                    await channel.send(embed=em, silent=True)

    @listener("logging")
    @commands.Cog.listener()
    async def on_category_update(self, event: guilded.CategoryUpdateEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            pass
        else:
            if guild.settings.get("logs_management"):
                try:
                    channel = await self.bot.getch_channel(guild.settings["logs_management"])
                except:
                    pass
                else:
                    em: guilded.Embed = EMBED_STANDARD(
                        title=f"Category \"{event.category.name}\" Updated",
                        description=f"In group \"{event.category.group.name if event.category.group else 'None'}\"",
                        colour=guilded.Colour.gilded()
                    )
                    em.set_thumbnail(
                        url=event.category.group.display_avatar.url if event.category.group else event.category.server.display_avatar.url)
                    em.add_field(name="Category ID", value=event.category.id)
                    if event.before:
                        if event.before.name != event.after.name:
                            em.add_field(name="Previous Name",
                                         value=event.before.name)
                            em.add_field(name="New Name",
                                         value=event.after.name)
                        if event.before.group_id != event.after.group_id:
                            em.add_field(
                                name="Previous Group", value=event.before.group.name if event.before.group else "None")
                            em.add_field(
                                name="New Group", value=event.after.group.name if event.after.group else "None")
                    await channel.send(embed=em, silent=True)


def setup(bot: commands.Bot):
    bot.add_cog(Logging(bot))
