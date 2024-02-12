from datetime import datetime
from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from core.images import IMAGE_DEFAULT_AVATAR
from database import DBConnection, loadQuery, resultExists
from database.permissions import UserPermissions
from core.converters import LangConverter
from humanfriendly import format_timespan
from guilded.ext import commands, tasks

import guilded
import config

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.current_status = 0
        self.update_status.start()
    
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
        async with DBConnection() as db:
            userData = await db.query(loadQuery("getUser"), {"id": ctx.author.id})
            if resultExists(userData):
                result = await db.query(loadQuery("setUserLanguage"), {"id": ctx.author.id, "lang": lang})
                if result[0]["status"] == "OK":
                    await ctx.reply(embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"The language for **{ctx.author.name}** has been set to `{lang}`"
                    ))
                else:
                    raise commands.CommandError("Failed to set language")
            else:
                result1 = await db.query(loadQuery("createUser"), {
                    "id": ctx.author.id,
                    "name": ctx.author.name,
                    "avatar": ctx.author.display_avatar.url,
                })
                if result1[0]["status"] == "OK":
                    result2 = await db.query(loadQuery("setUserLanguage"), {"id": ctx.author.id, "lang": lang})
                    if result2[0]["status"] == "OK":
                        await ctx.reply(embed=EMBED_SUCCESS(
                            title="Success",
                            description=f"The language for **{ctx.author.name}** has been set to `{lang}`"
                        ))
                    else:
                        raise commands.CommandError("Failed to set language")
                else:
                    raise commands.CommandError("Failed to create user")
    
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
    
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        message = event.message
        if message.author.bot: return
        if message.content.strip() == f"<@{self.bot.user_id}>":
            async with DBConnection() as db:
                prefix = config.DEFAULT_PREFIX
                guildData = await db.query(loadQuery("getGuild"), {"id": message.server_id})
                if resultExists(guildData):
                    prefix = guildData[0]["result"][0].get("prefix", config.DEFAULT_PREFIX)
                await message.reply(embed=EMBED_STANDARD(
                    title="Prefix",
                    description=f"Hey there, <@{message.author_id}>! The current prefix in **{message.server.name}** is `{prefix}`!"
                ))
    
    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
        member = event.member
        if member.bot: return
        async with DBConnection() as db:
            identifierData = await db.query(loadQuery("getIdentifier"), {"id": member.id})
            if not resultExists(identifierData):
                await db.query(loadQuery("createIdentifier"), {"id": member.id})
                print(f"Created identifier for {member.name} ({member.id})")

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
                await db.query(loadQuery("setUserConnections"), {
                    "id": member.id,
                    "connections": socials,
                })
                print(f"Updated connections for {member.name} ({member.id})")
            userData = await db.query(loadQuery("getUser"), {"id": member.id})
            if not resultExists(userData):
                await db.query(loadQuery("createUser"), {
                    "id": member.id,
                    "name": member.name,
                    "avatar": member.display_avatar.url,
                })
                print(f"Created user {member.name} ({member.id}) in database")
            guildUserData = await db.query(loadQuery("getGuildUser"), {"id": member.id, "guild": member.server_id})
            if not resultExists(guildUserData):
                await db.query(loadQuery("createGuildUser"), {
                    "id": member.id,
                    "guild": member.server_id,
                    "perms": str(UserPermissions.none()),
                    "banned": False,
                    "xp": 0,
                    "access": False,
                })
                print(f"Created user {member.name} ({member.id}) for server {member.server_id} in database")
            else:
                # Update their banned status, in case they
                # were unbanned while the bot was offline
                await db.query(loadQuery("updateGuildUserBan"), {
                    "banned": False,
                    "id": member.id,
                    "guild": member.server_id,
                })
                print(f"Set user {member.name} ({member.id}) for server {member.server_id} in database to not banned")
    
    @commands.Cog.listener()
    async def on_member_remove(self, event: guilded.MemberRemoveEvent):
        member = event.member
        if member.bot: return
        async with DBConnection() as db:
            # Set their perms to none
            result = await db.query(loadQuery("updateGuildUserPerms"), {
                "id": member.id,
                "guild": member.server_id,
                "perms": str(UserPermissions.none()),
                "access": False,
            })
            if result[0]["status"] == "OK":
                print(f"Set user {member.name} ({member.id}) perms for server {member.server_id} in database to none")
    
    @commands.Cog.listener()
    async def on_ban_create(event: guilded.BanCreateEvent):
        ban = event.ban
        async with DBConnection() as db:
            guildUserData = await db.query(loadQuery("getGuildUser"), {"id": ban.user.id, "guild": ban.server.id})
            if resultExists(guildUserData):
                print(f"Will try setting user {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) in database to banned")
                result = await db.query(loadQuery("updateGuildUserBan"), {
                    "banned": True,
                    "id": ban.user.id,
                    "guild": ban.server.id,
                })
                if result[0]["status"] == "OK":
                    print(f"Set user {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) in database to banned")
            else:
                print(f"User {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) not in database, will try creating")
                result = await db.query(loadQuery("createGuildUser"), {
                    "id": ban.user.id,
                    "guild": ban.server.id,
                    "perms": str(UserPermissions.none()),
                    "banned": True,
                    "xp": 0,
                    "access": False,
                })
                if result[0]["status"] == "OK":
                    print(f"Created user {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) in database as banned")
    
    @commands.Cog.listener()
    async def on_ban_delete(event: guilded.BanDeleteEvent):
        ban = event.ban
        async with DBConnection() as db:
            guildUserData = await db.query(loadQuery("getGuildUser"), {"id": ban.user.id, "guild": ban.server.id})
            if resultExists(guildUserData):
                print(f"Will try setting user {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) in database to not banned")
                result = await db.query(loadQuery("updateGuildUserBan"), {
                    "banned": False,
                    "id": ban.user.id,
                    "guild": ban.server.id,
                })
                if result[0]["status"] == "OK":
                    print(f"Set user {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) in database to not banned")
            else:
                print(f"User {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) not in database, will try creating")
                result = await db.query(loadQuery("createGuildUser"), {
                    "id": ban.user.id,
                    "guild": ban.server.id,
                    "perms": str(UserPermissions.none()),
                    "banned": False,
                    "xp": 0,
                    "access": False,
                })
                if result[0]["status"] == "OK":
                    print(f"Created user {ban.user.name} ({ban.user.id}) for server {ban.server.name} ({ban.server.id}) in database as not banned")
    
    @commands.Cog.listener()
    async def on_bulk_member_xp_add(event: guilded.BulkMemberXpAddEvent):
        async with DBConnection() as db:
            for member in event.members:
                guildUserData = await db.query(loadQuery("getGuildUser"), {"id": member.id, "guild": member.server_id})
                if resultExists(guildUserData):
                    print(f"Will try setting user {member.name} ({member.id}) for server {member.server_id} in database to have {member.xp} XP")
                    result = await db.query(loadQuery("updateGuildUserXP"), {
                        "xp": member.xp,
                        "id": member.id,
                        "guild": member.server_id,
                    })
                    if result[0]["status"] == "OK":
                        print(f"Set user {member.name} ({member.id}) for server {member.server_id} in database to have {member.xp} XP")
                else:
                    print(f"User {member.name} ({member.id}) for server {member.server_id} not in database, will try creating")
                    if member.id == event.server.owner_id:
                        perms = UserPermissions.all()
                    elif (await member.fetch_permissions()).manage_server:
                        perms = UserPermissions.manager()
                    else:
                        perms = UserPermissions.none() # TODO: Calculate perms based on roles
                    result = await db.query(loadQuery("createGuildUser"), {
                        "id": member.id,
                        "guild": member.server_id,
                        "perms": str(perms),
                        "banned": False,
                        "xp": member.xp,
                        "access": perms.can_access_dash,
                    })
                    if result[0]["status"] == "OK":
                        print(f"Created user {member.name} ({member.id}) for server {member.server_id} in database to have {member.xp} XP")
    
    @commands.Cog.listener()
    async def on_member_social_link_create(event: guilded.MemberSocialLinkCreateEvent):
        socialLink = event.social_link
        member = socialLink.user
        async with DBConnection() as db:
            identifierData = await db.query(loadQuery("getIdentifier"), {"id": member.id})
            if not resultExists(identifierData):
                await db.query(loadQuery("createIdentifier"), {"id": member.id})
                print(f"Created identifier for {member.name} ({member.id})")

            socials: dict = identifierData[0]["results"][0].get("connections", {})
            socials[socialLink.type.name] = {
                "handle": socialLink.handle,
                "serviceId": socialLink.service_id
            }
            await db.query(loadQuery("setUserConnections"), {
                "id": member.id,
                "connections": socials,
            })
            print(f"Added connection {socialLink.type.name} for {member.name} ({member.id})")
    
    @commands.Cog.listener()
    async def on_member_social_link_delete(event: guilded.MemberSocialLinkDeleteEvent):
        socialLink = event.social_link
        member = socialLink.user
        async with DBConnection() as db:
            identifierData = await db.query(loadQuery("getIdentifier"), {"id": member.id})
            if not resultExists(identifierData):
                await db.query(loadQuery("createIdentifier"), {"id": member.id})
                print(f"Created identifier for {member.name} ({member.id})")

            socials: dict = identifierData[0]["results"][0].get("connections", {})
            socials.pop(socialLink.type.name, None)
            await db.query(loadQuery("setUserConnections"), {
                "id": member.id,
                "connections": socials,
            })
            print(f"Deleted connection {socialLink.type.name} for {member.name} ({member.id})")
    
    @commands.Cog.listener()
    async def on_member_social_link_update(event: guilded.MemberSocialLinkUpdateEvent):
        socialLink = event.social_link
        member = socialLink.user
        async with DBConnection() as db:
            identifierData = await db.query(loadQuery("getIdentifier"), {"id": member.id})
            if not resultExists(identifierData):
                await db.query(loadQuery("createIdentifier"), {"id": member.id})
                print(f"Created identifier for {member.name} ({member.id})")

            socials: dict = identifierData[0]["results"][0].get("connections", {})
            socials[socialLink.type.name] = {
                "handle": socialLink.handle,
                "serviceId": socialLink.service_id
            }
            await db.query(loadQuery("setUserConnections"), {
                "id": member.id,
                "connections": socials,
            })
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
            async with DBConnection() as db:
                guilds = await db.query(loadQuery("countGuilds"))
                if guilds[0]["result"][0] is not None:
                    plural = guilds[0]['result'][0]['count'] != 1 and "s" or ""
                    await self.bot.set_status(
                        content=f"Protecting {'{:,}'.format(guilds[0]['result'][0]['count'])} Server{plural}",
                        emote=guilded.Object(838290)
                    )

def setup(bot: commands.Bot):
    cog = General(bot)
    bot.add_cog(cog)
    bot.help_command.cog = cog