from core.checks import has_permissions, user_has_any_permissions, module, user_has_permissions
from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from core.converters import UserConverter, MemberConverter
from humanfriendly import parse_timespan, format_timespan
from guilded.ext import commands, tasks
from modules.autoroles import Autoroles
from datetime import datetime

import database as db
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
                try:
                    await ctx.server.ban(member, reason=f"(Issuer: {ctx.author.id}) {reason}")
                    guild = await db.servers.fetch_or_create_server(ctx.server)
                    user = await guild.fetch_member(member.id)
                    await user.temp_ban(ctx.author.id, reason, timespan)
                except:
                    pass
                else:
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
                await user.unban()
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
    @has_permissions(commands_mute=True)
    @module("moderation")
    async def mute(self, ctx: commands.Context, member: MemberConverter, timespan: str = None, *reason: str):
        """
        Mute a member from the server
        """
        reason: str = " ".join(reason)
        if member:
            if not isinstance(member, guilded.Member):
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot mute a non-member!"
                ))
                return
            if member.bot:
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot mute a bot!"
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
                    description=f"You cannot mute another admin!"
                ))
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
            except:
                raise commands.CommandError("An unknown error occurred")
            else:
                if guild.settings.get("mute_role", "") == "":
                    await ctx.reply(embed=EMBED_DENIED(
                        title="Failure",
                        description=f"This server does not have a mute role set!"
                    ))
                    return
                try:
                    await member.add_role(guilded.Object(guild.settings["mute_role"]))
                except:
                    await ctx.reply(embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while muting {member.mention}!"
                    ))
                else:
                    if timespan is not None:
                        try:
                            user = await guild.fetch_or_create_member(member)
                            await user.mute(timespan, reason)
                        except:
                            await ctx.reply(embed=EMBED_DENIED(
                                title="Failure",
                                description=f"An error occurred while muting {member.mention}!"
                            ))
                        else:
                            await ctx.reply(embed=EMBED_SUCCESS(
                                title="Success",
                                description=f"Successfully muted {member.mention}!"
                            ))
                    else:
                        await ctx.reply(embed=EMBED_SUCCESS(
                            title="Success",
                            description=f"Successfully muted {member.mention}!"
                        ))
    
    async def unmute(self, ctx: commands.Context, member: MemberConverter):
        """
        Unmute a member from the server
        """
        if member:
            if not isinstance(member, guilded.Member):
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot unmute a non-member!"
                ))
                return
            if member.bot:
                await ctx.reply(embed=EMBED_DENIED(
                    title="Invalid Member",
                    description=f"You cannot unmute a bot!"
                ))
                return
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
            except:
                raise commands.CommandError("An unknown error occurred")
            else:
                if guild.settings.get("mute_role", "") == "":
                    await ctx.reply(embed=EMBED_DENIED(
                        title="Failure",
                        description=f"This server does not have a mute role set!"
                    ))
                    return
                try:
                    await member.remove_role(guilded.Object(guild.settings["mute_role"]))
                except:
                    await ctx.reply(embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while unmuting {member.mention}!"
                    ))
                else:
                    try:
                        user = await guild.fetch_or_create_member(member)
                        await user.unmute()
                    except:
                        await ctx.reply(embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while unmuting {member.mention}!"
                        ))
                    else:
                        await ctx.reply(embed=EMBED_SUCCESS(
                            title="Success",
                            description=f"Successfully unmuted {member.mention}!"
                        ))
    
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
                await user.warn(ctx.author.id, reason, timespan)
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
            try:
                status = await db.statuses.get_status(warn_id)
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"Warning {warn_id} does not exist!"
                    )
                )
                return
            else:
                if status.type != "warn" or status.user_id != member.id or status.guild_id != ctx.server.id:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"Warning {warn_id} does not exist!"
                        )
                    )
                    return
            try:
                await status.delete()
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while deleting the warning!"
                    )
                )
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully deleted the warning!"
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
                warnings = await user.warnings()
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while fetching the warnings!"
                    )
                )
            else:
                desc = ""
                if len(warnings) == 0:
                    desc = "No warnings!"
                else:
                    for warning in warnings:
                        if warning.ends_at:
                            ends = warning.ends_at
                            remaining = ends - datetime.now()
                            desc += f"**{warning.id}** • <@{warning.issuer}> • {warning.reason} • {format_timespan(remaining)}\n"
                        else:
                            desc += f"**{warning.id}** • <@{warning.issuer}> • {warning.reason}\n"
                await ctx.reply(embed=EMBED_SUCCESS(
                    title=f"Warnings for {member.mention} ({len(warnings)})",
                    description=desc
                ))
    
    @commands.command(aliases=["clearwarns", "clearwarn"])
    @has_permissions(commands_warn=True)
    @module("moderation")
    async def clearwarnings(self, ctx: commands.Context, member: MemberConverter):
        """
        Clear all warnings for a member
        """
        if member:
            member: guilded.Member = member
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
                await user.clear_statuses(["warn"])
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while clearing the warnings!"
                    )
                )
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully cleared the warnings!"
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
                await user.set_note(note)
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while adding the note!"
                    )
                )
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully added the note!"
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
                await user.set_note("")
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while clearing the note!"
                    )
                )
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"Successfully cleared the note!"
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
            try:
                guild = await db.servers.fetch_or_create_server(ctx.server)
                user = await guild.fetch_member(member.id)
            except:
                await ctx.reply(
                    embed=EMBED_DENIED(
                        title="Failure",
                        description=f"An error occurred while fetching the user's information!"
                    )
                )
            else:
                try:
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
                    if await user_has_permissions(ctx.author, commands_note=True) and user.note:
                        em.add_field(name="Note", value=len(user.note) > 0 and user.note or "None", inline=False)
                    await ctx.reply(embed=em)
                except db.NotFound:
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"No information found!"
                        )
                    )
                except Exception as e:
                    print("{}: {}".format(type(e).__name__, e))
                    await ctx.reply(
                        embed=EMBED_DENIED(
                            title="Failure",
                            description=f"An error occurred while fetching the user's information!"
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
        try:
            statuses = await db.statuses.get_expired_statuses(["tempban", "mute", "warn", "autorole"])
        except:
            pass
        else:
            to_expire = []
            for status in statuses:
                if status.type == "ban":
                    try:
                        server = await self.bot.getch_server(status.guild_id)
                        await server.unban(status["user_id"])
                    except:
                        pass
                    else:
                        # TODO: Notify the user when possible
                        pass
                elif status.type == "warn":
                    # TODO: Notify the user when possible
                    pass
                elif status.type == "mute":
                    try:
                        guild = await db.servers.fetch_or_create_server(status.guild_id)
                    except:
                        pass
                    else:
                        muteRoleId = guild.settings.get("mute_role", None)
                        if muteRoleId:
                            try:
                                server = await self.bot.getch_server(status.guild_id)
                                member = await server.getch_member(status.guild_id)
                                await member.remove_role(guilded.Object(muteRoleId))
                            except:
                                pass
                            else:
                                # TODO: Notify the user when possible
                                pass
                elif status.type == "autorole":
                    autoroles: Autoroles = self.bot.get_cog("Autoroles")
                    try:
                        autorole = await db.autoroles.get_autorole(status.autorole)
                    except:
                        pass
                    else:
                        try:
                            server = await self.bot.getch_server(status.guild_id)
                            member = await server.getch_member(status.user_id)
                        except:
                            pass
                        else:
                            try:
                                await autoroles.update_autoroles(member, [autorole])
                            except:
                                pass
                to_expire.append(status.id)
            try:
                await db.statuses.expire_statuses(to_expire)
            except:
                pass

def setup(bot: commands.Bot):
    bot.add_cog(Moderation(bot))