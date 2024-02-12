from core.checks import has_permissions, user_has_any_permissions, module, user_has_permissions
from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from database import DBConnection, loadQuery, resultExists
from core.converters import UserConverter, MemberConverter
from humanfriendly import parse_timespan, format_timespan
from guilded.ext import commands, tasks
from datetime import datetime

import guilded

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.check_statuses.start()
    
    @commands.command()
    @has_permissions(commands_ban=True)
    @module("moderation")
    async def ban(self, ctx: commands.Context, member: UserConverter, timespan: str = None, *reason: str):
        """
        Ban a member from the server
        """
        reason: str = " ".join(reason)
        if member:
            if ctx.server.get_member(member.id):
                member: guilded.Member = ctx.server.get_member(member.id)
            if isinstance(member, guilded.Member) and member.bot:
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot ban a bot!"
                ))
                return
            if isinstance(member, guilded.Member) and await user_has_any_permissions(
                member,
                commands_ban=True,
                commands_kick=True,
                manage_moderation=True
            ):
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot ban another admin!"
                ))
                return
            if timespan is not None:
                try:
                    # We're only doing this to verify that it
                    # would be something the database can
                    # automatically convert to a duration
                    parse_timespan(timespan)
                except:
                    reason = f"{timespan} {reason}"
                    timespan = None
            
            if reason.rstrip() == "":
                reason = "No reason provided."
            
            if timespan:
                async with DBConnection() as db:
                    try:
                        await ctx.server.ban(member, reason=f"(Issuer: {ctx.author.id}) {reason}")
                        response = await db.query(loadQuery("tempBanUser"), {
                            "guild_id": ctx.server.id,
                            "user_id": member.id,
                            "reason": reason,
                            "ends": timespan,
                        })
                    except:
                        response = None
                    if response and resultExists(response):
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Success",
                                description=f"Successfully banned {member.mention}!"
                            )
                            .add_field(name="Reason", value=reason)
                            .add_field(name="Duration", value=format_timespan(parse_timespan(timespan)))
                        )
            else:
                try:
                    await ctx.server.ban(member, reason=f"(Issuer: {ctx.author.id}) {reason}")
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while banning {member.mention}!"
                        )
                    )
                else:
                    await ctx.reply(
                        embed=EMBED_SUCCESS(
                            title="Success",
                            description=f"Successfully banned {member.mention}!"
                        )
                        .add_field(name="Reason", value=reason)
                    )
    
    @commands.command()
    @has_permissions(commands_ban=True)
    @module("moderation")
    async def unban(self, ctx: commands.Context, member: UserConverter):
        """
        Unban a member from the server
        """
        if member:
            member: guilded.User
            if ctx.server.get_member(member.id):
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"This user is not banned!"
                ))
                return
            try:
                ban = await ctx.server.fetch_ban(member)
            except:
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"This user is not banned!"
                ))
                return
            else:
                if not ban:
                    await ctx.reply(embed=EMBED_DENIED(
                        title="Invalid Member",
                        description=f"This user is not banned!"
                    ))
                    return
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("unbanUser"), {"guild_id": ctx.server.id, "user_id": member.id})
                except:
                    pass
            try:
                await ctx.server.unban(member)
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while unbanning {member.mention}!"
                    )
                )
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully unbanned {member.mention}!"
                    )
                )
    
    @commands.command()
    @has_permissions(commands_kick=True)
    @module("moderation")
    async def kick(self, ctx: commands.Context, member: MemberConverter, *reason: str):
        """
        Kick a member from the server
        """
        reason: str = " ".join(reason)
        if member:
            if not isinstance(member, guilded.Member):
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot kick a non-member!"
                ))
                return
            if member.bot:
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot kick a bot!"
                ))
                return
            if await user_has_any_permissions(
                member,
                commands_ban=True,
                commands_kick=True,
                manage_moderation=True
            ):
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot kick another admin!"
                ))
                return
            if reason.rstrip() == "":
                reason = "No reason provided."
            try:
                await ctx.server.kick(member)
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while kicking {member.mention}!"
                    )
                )
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully kicked {member.mention}!"
                    )
                    .add_field(name="Reason", value=reason)
                )
    
    @commands.command()
    @has_permissions(commands_purge=True)
    @module("moderation")
    async def purge(self, ctx: commands.Context, amount: int, target: UserConverter=None):
        """
        Purge a certain amount of messages from the channel
        """
        if amount > 100:
            await ctx.reply(embed=EMBED_DENIED(
                title="Invalid Amount",
                description=f"You cannot purge more than 100 messages!"
            ))
            return
        if amount < 1:
            await ctx.reply(embed=EMBED_DENIED(
                title="Invalid Amount",
                description=f"You cannot purge less than 1 message!"
            ))
            return
        deleted_count = 0
        for message in await ctx.channel.history(limit=amount, include_private=False):
            if target and message.author.id != target.id:
                continue
            await message.delete()
            deleted_count += 1
        
        if deleted_count > 0:
            await ctx.reply(embed=EMBED_SUCCESS(
                title="Success",
                description=f"Successfully deleted **{deleted_count}** messages!"
            ))
        else:
            await ctx.reply(embed=EMBED_DENIED(
                title="Failure",
                description=f"No messages were deleted!"
            ))
    
    @commands.command()
    @has_permissions(commands_warn=True)
    @module("moderation")
    async def warn(self, ctx: commands.Context, member: MemberConverter, timespan: str = None, *reason: str):
        """
        Warn a member
        """
        reason: str = " ".join(reason)
        if member:
            member: guilded.Member = member
            if member.bot:
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot warn a bot!"
                ))
                return
            if timespan:
                try:
                    parse_timespan(timespan)
                except:
                    reason = f"{timespan} {reason}"
                    timespan = None
            if reason.rstrip() == "":
                reason = "No reason provided."
            async with DBConnection() as db:
                try:
                    if timespan:
                        response = await db.query(loadQuery("tempWarnUser"), {
                            "guild_id": ctx.server.id,
                            "user_id": member.id,
                            "reason": reason,
                            "ends": timespan,
                            "issuer": ctx.author.id
                        })
                    else:
                        response = await db.query(loadQuery("warnUser"), {
                            "guild_id": ctx.server.id,
                            "user_id": member.id,
                            "reason": reason,
                            "issuer": ctx.author.id
                        })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while warning {member.mention}!"
                        )
                    )
                else:
                    em = EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully warned {member.mention}!"
                    )
                    em.add_field(name="Reason", value=reason)
                    em.add_field(name="Issuer", value=ctx.author.mention)
                    if timespan:
                        em.add_field(name="Duration", value=format_timespan(parse_timespan(timespan)))
                    await ctx.reply(embed=em)
    
    @commands.command()
    @has_permissions(commands_warn=True)
    @module("moderation")
    async def delwarn(self, ctx: commands.Context, member: MemberConverter, warn_id: int):
        """
        Delete a warning from a member
        """
        if member:
            member: guilded.Member = member
            async with DBConnection() as db:
                try:
                    response1 = await db.query(loadQuery("getStatus"), {
                        "id": warn_id,
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"Warning {warn_id} does not exist!"
                        )
                    )
                    return
                else:
                    if resultExists(response1):
                        data = response1[0]["result"]
                        if data["type"] != "warn" or data["user_id"] != member.id or data["guild_id"] != ctx.server.id:
                            await ctx.reply(
                                embed=EMBED_DENIED(
                                    title="Failure",
                                    description=f"Warning {warn_id} does not exist!"
                                )
                            )
                            return
                try:
                    response = await db.query(loadQuery("expireStatuses"), {
                        "ids": [warn_id],
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while deleting the warning!"
                        )
                    )
                else:
                    if resultExists(response):
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Success",
                                description=f"Successfully deleted the warning!"
                            )
                        )
                    else:
                        await ctx.reply(
                            embed=EMBED_DENIED(
                                title="Failure",
                                description=f"No warning was deleted!"
                            )
                        )
    
    @commands.command(aliases=["warns", "warnlist"])
    @has_permissions(commands_warn=True)
    @module("moderation")
    async def warnings(self, ctx: commands.Context, member: MemberConverter):
        """
        Get a list of warnings for a member
        """
        if member:
            member: guilded.Member = member
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("getStatuses"), {
                        "user_id": member.id,
                        "guild_id": ctx.server.id,
                        "types": ["warn"]
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while fetching the warnings!"
                        )
                    )
                else:
                    if resultExists(response):
                        warnings = response[0]["result"]
                        desc = ""
                        for warning in warnings:
                            if warning["ends"]:
                                ends = datetime.fromisoformat(warning["ends"])
                                remaining = ends - datetime.now()
                                desc += f"**{warning['id']}** • <@{warning['issuer']}> • {warning['reason']} • {format_timespan(remaining)}\n"
                            else:
                                desc += f"**{warning['id']}** • <@{warning['issuer']}> • {warning['reason']}\n"
                        await ctx.reply(embed=EMBED_SUCCESS(
                            title=f"Warnings for {member.mention} ({len(warnings)})",
                            description=desc
                        ))
                    else:
                        await ctx.reply(
                            embed=EMBED_DENIED(
                                title="Failure",
                                description=f"No warnings were found!"
                            )
                        )
    
    @commands.command(aliases=["clearwarns", "clearwarn"])
    @has_permissions(commands_warn=True)
    @module("moderation")
    async def clearwarnings(self, ctx: commands.Context, member: MemberConverter):
        """
        Clear all warnings for a member
        """
        if member:
            member: guilded.Member = member
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("clearStatuses"), {
                        "user_id": member.id,
                        "guild_id": ctx.server.id,
                        "type": ["warn"]
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while clearing the warnings!"
                        )
                    )
                else:
                    if resultExists(response):
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Success",
                                description=f"Successfully cleared the warnings!"
                            )
                        )
                    else:
                        await ctx.reply(
                            embed=EMBED_DENIED(
                                title="Failure",
                                description=f"No warnings were cleared!"
                            )
                        )
    
    @commands.command()
    @has_permissions(commands_note=True)
    @module("moderation")
    async def note(self, ctx: commands.Context, member: MemberConverter, *note: str):
        """
        Add a note to a member
        """
        note: str = " ".join(note)
        if member:
            member: guilded.Member = member
            if note.rstrip() == "":
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"No note was added!"
                    )
                )
                return
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("setUserNote"), {
                        "guild_id": ctx.server.id,
                        "user_id": member.id,
                        "note": note
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while adding the note!"
                        )
                    )
                else:
                    if resultExists(response):
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Success",
                                description=f"Successfully added the note!"
                            )
                        )
                    else:
                        await ctx.reply(
                            embed=EMBED_DENIED(
                                title="Failure",
                                description=f"An error occurred while adding the note!"
                            )
                        )
    
    @commands.command(aliases=["delnote"])
    @has_permissions(commands_note=True)
    @module("moderation")
    async def clearnote(self, ctx: commands.Context, member: MemberConverter):
        """
        Clear a member's note
        """
        if member:
            member: guilded.Member = member
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("setUserNote"), {
                        "guild_id": ctx.server.id,
                        "user_id": member.id,
                        "note": ""
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while clearing the note!"
                        )
                    )
                else:
                    if resultExists(response):
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Success",
                                description=f"Successfully cleared the note!"
                            )
                        )
                    else:
                        await ctx.reply(
                            embed=EMBED_DENIED(
                                title="Failure",
                                description=f"An error occurred while clearing the note!"
                            )
                        )
    
    @commands.command()
    @has_permissions(commands_userinfo=True)
    @module("moderation")
    async def userinfo(self, ctx: commands.Context, member: MemberConverter):
        """
        Get information about a member
        """
        if member:
            member: guilded.Member = member
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("getGuildUser"), {
                        "guild": ctx.server.id,
                        "id": member.id,
                    })
                except:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while fetching the user's information!"
                        )
                    )
                else:
                    if resultExists(response):
                        try:
                            data = response[0]["result"][0]
                            em = EMBED_STANDARD(
                                title=f"User Information for {member.mention} ({member.id})",
                                description="",
                                url=member.profile_url
                            )
                            joinedTimespan = datetime.now() - member.joined_at
                            createdTimespan = datetime.now() - member.created_at
                            em.add_field(name="Joined", value=format_timespan(joinedTimespan))
                            em.add_field(name="Created", value=format_timespan(createdTimespan) + (createdTimespan.total_seconds() <= 60 * 60 * 24 * 3 and "\n:warning: Recent Account" or ""))
                            em.add_field(name="Roles", value=", ".join([f"<@{role}>" for role in await member.fetch_role_ids()]), inline=False)
                            em.set_thumbnail(url=member.display_avatar.url)
                            if await user_has_permissions(ctx.author, commands_note=True) and data.get("note", None):
                                em.add_field(name="Note", value=data.get("note", "None"), inline=False)
                            await ctx.reply(embed=em)
                        except Exception as e:
                            print("{}: {}".format(type(e).__name__, e))
                            await ctx.reply(
                                embed=EMBED_DENIED(
                                    title="Failure",
                                    description=f"An error occurred while fetching the user's information!"
                                )
                            )
                    else:
                        await ctx.reply(
                            embed=EMBED_DENIED(
                                title="Failure",
                                description=f"No information was found!"
                            )
                        )
    
    @commands.command()
    @commands.has_server_permissions(manage_server_xp=True)
    @module("moderation")
    async def reset_xp(self, ctx: commands.Context):
        """
        Reset the XP of all mentioned users
        """
        if len(ctx.message.user_mentions) == 0:
            await ctx.reply(
                embed=EMBED_DENIED(
                    title="Failure",
                    description=f"No users were mentioned!"
                )
            )
            return
        elif len(ctx.message.user_mentions) > 50:
            await ctx.reply(
                embed=EMBED_DENIED(
                    title="Failure",
                    description=f"Too many users were mentioned!"
                )
            )
            return
        else:
            reset = []
            for user in ctx.message.user_mentions:
                try:
                    await user.set_xp(0)
                except:
                    pass
                else:
                    reset.append(user)
            
            if len(reset) > 0:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully reset the XP of the following users:\n{' '.join([u.mention for u in reset])}"
                    ),
                    silent=True
                )
    
    @tasks.loop(seconds=5)
    async def check_statuses(self):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getExpiredStatuses"), {
                    "type": ["tempban", "mute", "warn"]
                })
            except:
                pass
            else:
                if resultExists(response):
                    to_expire = []
                    for status in response[0]["result"]:
                        if status["type"] == "ban":
                            try:
                                server = await self.bot.getch_server(status["guild_id"])
                                await server.unban(status["user_id"])
                            except:
                                pass
                            else:
                                # TODO: Notify the user when possible
                                pass
                        elif status["type"] == "warn":
                            # TODO: Notify the user when possible
                            pass
                        elif status["type"] == "mute":
                            try:
                                guildResponse = await db.query(loadQuery("getGuild"), {"id": status["guild_id"]})
                            except:
                                pass
                            else:
                                if resultExists(guildResponse):
                                    muteRoleId = guildResponse[0]["result"][0].get("mute_role", None)
                                    if muteRoleId:
                                        try:
                                            server = await self.bot.getch_server(status["guild_id"])
                                            member = await server.getch_member(status["user_id"])
                                            await member.remove_role(guilded.Object(muteRoleId))
                                        except:
                                            pass
                                        else:
                                            # TODO: Notify the user when possible
                                            pass
                        to_expire.append(status["id"].split(":")[1])

def setup(bot: commands.Bot):
    bot.add_cog(Moderation(bot))