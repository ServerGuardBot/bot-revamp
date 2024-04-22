from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from database.permissions import UserPermissions
from libs.translator import refresh_languages
from core.images import IMAGE_DEFAULT_AVATAR
from core.converters import LangConverter
from humanfriendly import format_timespan
from guilded.ext import commands, tasks
from modules.dash import Dashboard
from datetime import datetime
from modules.xp import XP

import database as db
import guilded
import config

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.current_status = 0
        self.refresh_langs.start()
        self.update_status.start()
        self.cleanup_tokens.start()
    
    async def after_load(self):
        dash: Dashboard = self.bot.get_cog("Dashboard")
        dash.register_listener("nickname", self.on_bot_nickname_changed)
    
    @commands.command()
    async def ping(self, ctx: commands.Context):
        """
        Get the bot's current latency
        """
        await ctx.reply(embed=EMBED_STANDARD(
            title="Pong!",
            description=f"Current latency is {round(self.bot.latency * 1000)}ms"
        ))
    
    @commands.command()
    async def invite(self, ctx: commands.Context):
        """
        Invite the bot to your server
        """
        await ctx.reply(embed=EMBED_STANDARD(
            title="Invite Me!",
            description=f"Invite me to your server with this link: {config.INVITE_LINK}"
        ))
    
    @commands.command()
    async def support(self, ctx: commands.Context):
        """
        Get an invite link to the support server
        """
        await ctx.reply(embed=EMBED_STANDARD(
            title="Support Server",
            description=f"Join the support server with this link: {config.SUPPORT_SERVER_LINK}"
        ))
    
    @commands.command(aliases=["lang"])
    async def language(self, ctx: commands.Context, lang: LangConverter):
        """
        Set your preferred language
        """
        supported_languages = ["en"] # TODO: Make this pull from localization system once implemented
        if lang not in supported_languages:
            await ctx.reply(embed=EMBED_DENIED(
                title="Invalid Language",
                description=f"The language `{lang}` is not supported. Supported languages are: {', '.join([f'`{s}`' for s in supported_languages])}"
            ))
            return
        try:
            user = await db.users.fetch_or_create_user(ctx.author)
        except:
            raise commands.CommandError("Something went wrong. Please try again later!")
        else:
            try:
                await user.set_language(lang)
            except:
                raise commands.CommandError("Failed to set language")
            else:
                await ctx.reply(embed=EMBED_SUCCESS(
                    title="Success",
                    description=f"The language for **{ctx.author.name}** has been set to `{lang}`"
                ))
    
    @commands.command()
    async def serverinfo(self, ctx:commands.Context):
        """
        Get information about the server
        """
        server = ctx.guild
        embed = EMBED_STANDARD(
            title=f"{server.name} ({server.id})",
            description=server.about,
            url=f"https://guilded.gg/{server.slug}"
        )
        embed.set_thumbnail(url=server.icon and server.icon.url or IMAGE_DEFAULT_AVATAR)
        embed.add_field(name="Owner", value=f"<@{server.owner_id}>", inline=True)
        embed.add_field(name="Members", value=server.member_count, inline=True)
        embed.add_field(name="Verified", value=server.verified and "Yes" or "No", inline=True)
        embed.add_field(name="Timezone", value=server.timezone and server.timezone.key or "None", inline=True)
        embed.add_field(name="Created", value=format_timespan(datetime.now() - server.created_at), inline=True)
        embed.add_field(name="Type", value=server.type and server.type.name.capitalize() or "Unknown", inline=True)
        await ctx.reply(embed=embed, silent=True)
    
    @tasks.loop(minutes=1)
    async def refresh_langs(self):
        refresh_languages()
    
    @tasks.loop(minutes=1)
    async def cleanup_tokens(self):
        try:
            await db.auth.cleanup_tokens()
        except Exception as e:
            print("Failed to cleanup old tokens: {} - {}".format(type(e).__name__, e))
    
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        message = event.message
        if message.author.bot: return
        event.message.author.last_message = message
        if message.content.strip() == f"<@{self.bot.user_id}>":
            try:
                guild = await db.servers.fetch_or_create_server(message.server)
            except:
                await message.reply(embed=EMBED_DENIED(
                    title="Error",
                    description="An error occurred while trying to get this server's prefix!"
                ))
            else:
                prefix = guild.settings.get("prefix", config.DEFAULT_PREFIX)
                await message.reply(embed=EMBED_STANDARD(
                    title="Prefix",
                    description=f"Hey there, <@{message.author_id}>! The current prefix in **{message.server.name}** is `{prefix}`!"
                ))
    
    async def on_bot_nickname_changed(self, server: guilded.Server, new_nickname: str, _old_nickname: str):
        me = await server.getch_member(self.bot.user_id)
        await me.edit(nick=new_nickname)
    
    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
        member = event.member
        if member.bot: return
        try:
            user = await db.users.fetch_or_create_user(member)
            identifier = await user.get_identifier()
        except Exception as e:
            print(f"Failed to fetch user {member.name} ({member.id}) and their identifier from database: {type(e).__name__} - {e}")
        else:
            socials = {}
            for type in guilded.SocialLinkType:
                try:
                    link: guilded.SocialLink = await member.fetch_social_link(type)
                    socials[type.name] = {
                        "handle": link.handle,
                        "serviceId": link.service_id
                    }
                except:
                    pass
            try:
                await identifier.update(
                    connections=socials
                )
            except Exception as e:
                print(f"Failed to update identifier for {member.name} ({member.id}): {type(e).__name__} - {e}")
            else:
                print(f"Updated connections for {member.name} ({member.id})")
            
            try:
                guild = await db.servers.fetch_or_create_server(member.server)
                guild_member = await guild.fetch_or_create_member(member)
            except Exception as e:
                print(f"Failed to fetch guild {member.server.name} ({member.server.id}) and member {member.name} ({member.id}) from database: {type(e).__name__} - {e}")
            else:
                if guild_member.is_banned:
                    try:
                        await guild_member.set_banned(False)
                    except Exception as e:
                        print(f"Failed to sync ban state for user {member.name} ({member.id}) from server {member.server.name} ({member.server.id}): {type(e).__name__} - {e}")
                    else:
                        print(f"Synced ban state for user {member.name} ({member.id}) from server {member.server.name} ({member.server.id})")
    
    @commands.Cog.listener()
    async def on_member_remove(self, event: guilded.MemberRemoveEvent):
        member = event.member
        if member.bot: return
        try:
            guild = await db.servers.fetch_or_create_server(member.server)
            user = await guild.fetch_or_create_member(member)
        except Exception as e:
            print(f"Failed to fetch user {member.name} ({member.id}) and their identifier from database: {type(e).__name__} - {e}")
        else:
            await user.set_perms(UserPermissions.none())
            await user.set_roles([])
    
    @commands.Cog.listener()
    async def on_member_update(self, event: guilded.MemberUpdateEvent):
        member = event.after
        if member.id == self.bot.user_id:
            try:
                guild = await db.servers.fetch_or_create_server(member.server)
            except Exception as e:
                print(f"Failed to fetch server {member.server.name} ({member.server.id}) from database: {type(e).__name__} - {e}")
            else:
                try:
                    await guild.update_settings(
                        nickname=member.nick,
                    )
                except Exception as e:
                    print(f"Failed to update nickname for server {member.server.name} ({member.server.id}): {type(e).__name__} - {e}")
    
    @commands.Cog.listener()
    async def on_ban_create(self, event: guilded.BanCreateEvent):
        ban = event.ban
        try:
            guild = await db.servers.fetch_or_create_server(ban.server)
            user = await guild.fetch_or_create_member(ban.user)
        except Exception as e:
            print(f"Failed to fetch user {ban.user.name} ({ban.user.id}) from database: {type(e).__name__} - {e}")
        else:
            if not user.is_banned:
                try:
                    await user.set_banned(True)
                except Exception as e:
                    print(f"Failed to sync ban state for user {ban.user.name} ({ban.user.id}) from server {ban.server.name} ({ban.server.id}): {type(e).__name__} - {e}")
                else:
                    print(f"Synced ban state for user {ban.user.name} ({ban.user.id}) from server {ban.server.name} ({ban.server.id})")
    
    @commands.Cog.listener()
    async def on_ban_delete(self, event: guilded.BanDeleteEvent):
        ban = event.ban
        try:
            guild = await db.servers.fetch_or_create_server(ban.server)
            user = await guild.fetch_or_create_member(ban.user)
        except Exception as e:
            print(f"Failed to fetch user {ban.user.name} ({ban.user.id}) from database: {type(e).__name__} - {e}")
        else:
            if user.is_banned:
                try:
                    await user.set_banned(False)
                except Exception as e:
                    print(f"Failed to sync ban state for user {ban.user.name} ({ban.user.id}) from server {ban.server.name} ({ban.server.id}): {type(e).__name__} - {e}")
                else:
                    print(f"Synced ban state for user {ban.user.name} ({ban.user.id}) from server {ban.server.name} ({ban.server.id})")
    
    @commands.Cog.listener()
    async def on_bulk_member_xp_add(self, event: guilded.BulkMemberXpAddEvent):
        xp: XP = self.bot.get_cog("XP")
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except Exception as e:
            print(f"Failed to fetch server {event.server.name} ({event.server.id}) from database: {type(e).__name__} - {e}")
        else:
            for member in event.members:
                try:
                    guild_member = await guild.fetch_or_create_member(member)
                except Exception as e:
                    print(f"Failed to fetch user {member.name} ({member.id}) from database: {type(e).__name__} - {e}")
                else:
                    try:
                        await xp.xp_updated(
                            member,
                            guild_member.xp,
                            member.xp
                        )
                    except Exception as e:
                        print(f"Failed to notify XP module for {member.name} ({member.id}) in server {event.server.id}: {type(e).__name__} - {e}")
                    
                    try:
                        await guild_member.set_xp(member.xp)
                    except Exception as e:
                        print(f"Failed to update user XP {member.name} ({member.id}) in server {event.server.id} in database: {type(e).__name__} - {e}")
    
    @commands.Cog.listener()
    async def on_member_social_link_create(self, event: guilded.MemberSocialLinkCreateEvent):
        socialLink = event.social_link
        member = socialLink.user
        try:
            user = await db.users.fetch_or_create_user(member)
            identifier = await user.get_identifier()
        except Exception as e:
            print(f"Failed to fetch user {member.name} ({member.id}) and their identifier from database: {type(e).__name__} - {e}")
        else:
            socials: dict = identifier.connections
            socials[socialLink.type.name] = {
                "handle": socialLink.handle,
                "serviceId": socialLink.service_id
            }
            try:
                await identifier.update(
                    connections=socials
                )
            except Exception as e:
                print(f"Failed to update identifier for {member.name} ({member.id}) in database: {type(e).__name__} - {e}")
            else:
                print(f"Added connection {socialLink.type.name} for {member.name} ({member.id})")
    
    @commands.Cog.listener()
    async def on_member_social_link_delete(self, event: guilded.MemberSocialLinkDeleteEvent):
        socialLink = event.social_link
        member = socialLink.user
        try:
            user = await db.users.fetch_or_create_user(member)
            identifier = await user.get_identifier()
        except Exception as e:
            print(f"Failed to fetch user {member.name} ({member.id}) and their identifier from database: {type(e).__name__} - {e}")
        else:
            socials: dict = identifier.connections
            socials.pop(socialLink.type.name, None)
            try:
                await identifier.update(
                    connections=socials
                )
            except Exception as e:
                print(f"Failed to update identifier for {member.name} ({member.id}) in database: {type(e).__name__} - {e}")
            else:
                print(f"Deleted connection {socialLink.type.name} for {member.name} ({member.id})")
    
    @commands.Cog.listener()
    async def on_member_social_link_update(self, event: guilded.MemberSocialLinkUpdateEvent):
        socialLink = event.social_link
        member = socialLink.user
        try:
            user = await db.users.fetch_or_create_user(member)
            identifier = await user.get_identifier()
        except Exception as e:
            print(f"Failed to fetch user {member.name} ({member.id}) and their identifier from database: {type(e).__name__} - {e}")
        else:
            socials: dict = identifier.connections
            socials[socialLink.type.name] = {
                "handle": socialLink.handle,
                "serviceId": socialLink.service_id
            }
            try:
                await identifier.update(
                    connections=socials
                )
            except Exception as e:
                print(f"Failed to update identifier for {member.name} ({member.id}) in database: {type(e).__name__} - {e}")
            else:
                print(f"Updated connection {socialLink.type.name} for {member.name} ({member.id})")
    
    @tasks.loop(minutes=1)
    async def update_status(self):
        self.current_status += 1
        if self.current_status > 2:
            self.current_status = 1
        if self.current_status == 1:
            await self.bot.set_status(
                content="/help • serverguard.xyz",
                emote=guilded.Object(2229643)
            )
        elif self.current_status == 2:
            try:
                guilds = await db.servers.count_servers()
            except:
                guilds = 3748

            if guilds > 50000:
                # Don't format with thousand separators if the number is too high
                # instead, shortens it with K, M, etc suffixes
                await self.bot.set_status(
                    content=f"Protecting {human_format(guilds)} Servers",
                    emote=guilded.Object(838290)
                )
            else:
                plural = guilds != 1 and "s" or ""
                await self.bot.set_status(
                    content=f"Protecting {'{:,}'.format(guilds)} Server{plural}",
                    emote=guilded.Object(838290)
                )

def setup(bot: commands.Bot):
    cog = General(bot)
    bot.add_cog(cog)
    bot.help_command.cog = cog

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])