from core.checks import has_permissions, listener, user_has_any_permissions, module, user_has_permissions
from core.checks_api import authenticated, has_any_permissions, dashboard_access
from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from humanfriendly import parse_timespan, format_timespan
from quart import Quart, jsonify, request
from datetime import datetime, timedelta
from guilded.ext import commands, tasks
from core.images import IMAGE_BOT_LOGO
from core.emotes import EMOTE_TADA
from core.cors import apply_cors

import database as db
import guilded
import config

class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.group()
    @has_permissions(manage_giveaways=True)
    @module("giveaways")
    async def giveaway(self, ctx: commands.Context):
        pass
    
    @giveaway.command()
    @has_permissions(manage_giveaways=True)
    @module("giveaways")
    async def host(self, ctx: commands.Context, timespan: str, winners: int, *_prize):
        try:
            guild = await db.servers.fetch_or_create_server(ctx.guild)
        except:
            raise commands.CommandError("Something went wrong while fetching server information.")
        else:
            prize = " ".join(_prize)
            if timespan is not None:
                try:
                    timespan = parse_timespan(timespan)
                except:
                    raise commands.ArgumentParsingError("Invalid timespan.")
            else:
                raise commands.MissingRequiredArgument("timespan")
            
            try:
                int(winners)
            except:
                raise commands.ArgumentParsingError("Winners must be a valid integer.")
            
            channel_id = guild.settings.get("giveaway_channel", ctx.channel.id)
            
            try:
                channel = await self.bot.getch_channel(channel_id)
                message: guilded.ChatMessage = await channel.send(
                    embed=EMBED_STANDARD(
                        title=f"Giveaway hosted by {ctx.author.mention}"
                    ).add_field(
                        name="Prize",
                        value=prize,
                        inline=False
                    ).add_field(
                        name="Winners",
                        value=winners,
                        inline=True
                    ).add_field(
                        name="Ends In",
                        value=format_timespan(timespan),
                        inline=True
                    )
                )
                await message.add_reaction(guilded.Object(EMOTE_TADA))
                giveaway = await db.giveaways.host(
                    ctx.guild.id,
                    ctx.author.id,
                    message.id,
                    channel_id,
                    prize,
                    timespan,
                    winners
                )
            except Exception as e:
                print(f"Giveaway host error: {type(e).__name__} - {e}")
                raise commands.CommandError("Something went wrong while hosting the giveaway.")
            else:
                await ctx.reply(
                    embed=EMBED_SUCCESS(
                        title="Giveaway Hosted",
                        description=f"The giveaway has been hosted in {channel.mention}."
                    )
                )
    
    @giveaway.command()
    @has_permissions(manage_giveaways=True)
    @module("giveaways")
    async def list(self, ctx: commands.Context, page: int=0):
        from base import BOT_VERSION
        try:
            guild = await db.servers.fetch_or_create_server(ctx.guild)
        except:
            raise commands.CommandError("Something went wrong while fetching server information.")
        else:
            try:
                giveaways, total_pages = await db.giveaways.list_giveaways(ctx.guild.id, page)
            except:
                raise commands.CommandError("Something went wrong while fetching giveaway information.")
            else:
                if len(giveaways) == 0:
                    await ctx.reply(
                        embed=EMBED_STANDARD(
                            title="No Giveaways"
                        )
                    )
                else:
                    await ctx.reply(
                        embed=EMBED_STANDARD(
                            title="Giveaways",
                            description="\n".join([
                                f"**[{giveaway.id}]** {giveaway.prize} - {giveaway['entrants']} entries, {giveaway.state == db.giveaways.GiveawayState.ACTIVE and f'ends in {format_timespan(giveaway.ends_at - datetime.now()) or giveaway.state.value.title()}'}"
                                for giveaway in giveaways
                            ])
                        ).set_footer(
                            text=f"v{BOT_VERSION} {str.capitalize(config.DATABASE_DB)} • Page {page}/{total_pages}",
                            icon_url=IMAGE_BOT_LOGO,
                        )
                    )
    
    @giveaway.command()
    @has_permissions(manage_giveaways=True)
    @module("giveaways")
    async def end(self, ctx: commands.Context, giveaway_id: int):
        try:
            guild = await db.servers.fetch_or_create_server(ctx.guild)
        except:
            raise commands.CommandError("Something went wrong while fetching server information.")
        else:
            try:
                giveaway = await db.giveaways.fetch_giveaway(giveaway_id)
            except db.NotFound:
                raise commands.CommandError("Giveaway not found.")
            else:
                if giveaway.guild_id != ctx.guild.id:
                    raise commands.CommandError("Giveaway not found.")
                else:
                    try:
                        await giveaway.end(self.bot, guild, ctx.author.id)
                    except:
                        raise commands.CommandError("Something went wrong while ending the giveaway.")
                    else:
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Giveaway Ended",
                                description="The giveaway has been ended."
                            )
                        )
    
    @giveaway.command(aliases=["delete"])
    @has_permissions(manage_giveaways=True)
    @module("giveaways")
    async def cancel(self, ctx: commands.Context, giveaway_id: int):
        try:
            guild = await db.servers.fetch_or_create_server(ctx.guild)
        except:
            raise commands.CommandError("Something went wrong while fetching server information.")
        else:
            try:
                giveaway = await db.giveaways.fetch_giveaway(giveaway_id)
            except db.NotFound:
                raise commands.CommandError("Giveaway not found.")
            else:
                if giveaway.guild_id != ctx.guild.id:
                    raise commands.CommandError("Giveaway not found.")
                else:
                    try:
                        await giveaway.cancel(self.bot, guild, ctx.author.id)
                    except:
                        raise commands.CommandError("Something went wrong while cancelling the giveaway.")
                    else:
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Giveaway Cancelled",
                                description="The giveaway has been cancelled."
                            )
                        )
    
    @giveaway.command()
    @has_permissions(manage_giveaways=True)
    @module("giveaways")
    async def reroll(self, ctx: commands.Context, giveaway_id: int):
        try:
            guild = await db.servers.fetch_or_create_server(ctx.guild)
        except:
            raise commands.CommandError("Something went wrong while fetching server information.")
        else:
            try:
                giveaway = await db.giveaways.fetch_giveaway(giveaway_id)
            except db.NotFound:
                raise commands.CommandError("Giveaway not found.")
            else:
                if giveaway.guild_id != ctx.guild.id:
                    raise commands.CommandError("Giveaway not found.")
                else:
                    try:
                        await giveaway.reroll(self.bot, guild, ctx.author.id)
                    except:
                        raise commands.CommandError("Something went wrong while rerolling the giveaway.")
                    else:
                        await ctx.reply(
                            embed=EMBED_SUCCESS(
                                title="Giveaway Rerolled",
                                description="The giveaway has been rerolled."
                            )
                        )
    
    @listener("giveaways")
    @commands.Cog.listener()
    async def on_message_reaction_add(self, event: guilded.MessageReactionAddEvent):
        if event.member.bot: return
        if event.message.author.id != self.bot.user.id: return
        if event.emote.id == EMOTE_TADA:
            try:
                giveaway = await db.giveaways.fetch_giveaway(
                    guild_id=event.server_id,
                    message_id=event.message.id
                )
            except:
                pass
            else:
                try:
                    await giveaway.add_entry(event.member.id)
                except Exception as e:
                    print(f"Failed to add entry to giveaway {giveaway.id} for user {event.member.id}: {type(e).__name__} - {e}")
    
    @listener("giveaways")
    @commands.Cog.listener()
    async def on_message_reaction_remove(self, event: guilded.MessageReactionRemoveEvent):
        if event.member.bot: return
        if event.message.author.id != self.bot.user.id: return
        if event.emote.id == EMOTE_TADA:
            try:
                giveaway = await db.giveaways.fetch_giveaway(
                    guild_id=event.server_id,
                    message_id=event.message.id
                )
            except:
                pass
            else:
                try:
                    await giveaway.remove_entry(event.member.id)
                except Exception as e:
                    print(f"Failed to remove entry to giveaway {giveaway.id} for user {event.member.id}: {type(e).__name__} - {e}")
    
    def register_routes(self, app: Quart):
        @app.route("/servers/<string:server_id>/giveaways/list/<int:page>")
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        @has_any_permissions(host_giveaways=True, manage_giveaways=True)
        async def ListGiveaways(server_id: str, page: int):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except Exception:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    giveaways, total_pages = await db.giveaways.list_giveaways(server_id, page)
                except Exception as e:
                    import traceback
                    print(f"Failed to list giveaways for server {server_id}: {type(e).__name__} - {e}")
                    print(traceback.format_exc())
                    return jsonify({"status": "error", "error": "Something went wrong while fetching giveaway information."}), 500
                else:
                    return jsonify({
                        "status": "success",
                        "giveaways": [{
                            "id": giveaway.id,
                            "prize": giveaway.prize,
                            "ends_at": giveaway.ends_at.timestamp(),
                            "channel_id": giveaway.channel_id,
                            "message_id": giveaway.message_id,
                            "host_id": giveaway.host,
                            "state": giveaway.state.value,
                            "winners": giveaway.winners,
                            "entrants": giveaway.total_entries
                        } for giveaway in giveaways],
                        "total_pages": total_pages
                    })
        
        @app.route("/servers/<string:server_id>/giveaways", methods=["POST"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE], allow_methods=["POST"])
        @authenticated
        @dashboard_access
        @has_any_permissions(host_giveaways=True, manage_giveaways=True)
        async def CreateGiveaway(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    data = await request.get_json()
                except:
                    return jsonify({"status": "error", "error": "Please provide a JSON body."}), 400
                else:
                    try:
                        channel_id = guild.settings.get("giveaway_channel", data.get("channel_id"))
                        channel = await self.bot.getch_channel(channel_id)
                        message: guilded.ChatMessage = await channel.send(
                            embed=EMBED_STANDARD(
                                title=f"Giveaway hosted by <@{request.authenticated_user}>"
                            ).add_field(
                                name="Prize",
                                value=data["prize"],
                                inline=False
                            ).add_field(
                                name="Winners",
                                value=data["winners"],
                                inline=True
                            ).add_field(
                                name="Ends In",
                                value=format_timespan((datetime.fromtimestamp(data["ends_at"]) - datetime.now()).total_seconds()),
                                inline=True
                            )
                        )
                        await message.add_reaction(guilded.Object(EMOTE_TADA))
                        giveaway = await db.giveaways.host(
                            guild_id=server_id,
                            prize=data['prize'],
                            winners=data['winners'],
                            duration=data["ends_at"],
                            message_id=message.id,
                            channel_id=channel_id,
                            hosted_by=request.authenticated_user
                        )
                    except Exception as e:
                        print(f"Failed to create giveaway for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                        return jsonify({"status": "error", "error": "Something went wrong while creating giveaway."}), 500
                    else:
                        return jsonify({"status": "success", "giveaway": {
                            "id": giveaway.id,
                            "prize": giveaway.prize,
                            "ends_at": giveaway.ends_at.timestamp(),
                            "channel_id": giveaway.channel_id,
                            "message_id": giveaway.message_id,
                            "host_id": giveaway.host,
                            "state": giveaway.state.value,
                            "winners": giveaway.winners,
                            "entrants": giveaway.total_entries
                        }})
        
        @app.route("/servers/<string:server_id>/giveaways/<int:giveaway_id>", methods=["PATCH"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE], allow_methods=["PATCH"])
        @authenticated
        @dashboard_access
        @has_any_permissions(host_giveaways=True, manage_giveaways=True)
        async def UpdateGiveaway(server_id: str, giveaway_id: int):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    data = await request.get_json()
                except:
                    return jsonify({"status": "error", "error": "Please provide a JSON body."}), 400
                else:
                    try:
                        giveaway = await db.giveaways.fetch_giveaway(guild_id=server_id, id=giveaway_id)
                    except db.NotFound:
                        return jsonify({"status": "error", "error": "Giveaway not found."}), 404
                    except Exception as e:
                        print(f"Failed to fetch giveaway for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                        return jsonify({"status": "error", "error": "Something went wrong while fetching giveaway information."}), 500
                    else:
                        filtered_data = {}
                        for key, value in data.items():
                            if key in ["prize", "ends_at", "winner_amount"]:
                                if key == "prize":
                                    if not isinstance(value, str):
                                        return jsonify({"status": "error", "error": "Prize must be a string."}), 400
                                elif key == "ends_at":
                                    if not isinstance(value, int):
                                        return jsonify({"status": "error", "error": "Ends at must be an integer."}), 400
                                    elif giveaway.ended:
                                        return jsonify({"status": "error", "error": "Giveaway has already ended."}), 400
                                elif key == "winner_amount":
                                    if not isinstance(value, int):
                                        return jsonify({"status": "error", "error": "Winner amount must be an integer."}), 400
                                    elif value < 1:
                                        return jsonify({"status": "error", "error": "Winner amount must be greater than 0."}), 400
                                    elif value > 20:
                                        return jsonify({"status": "error", "error": "Winner amount must be less than 20."}), 400
                                filtered_data[key] = value
                        try:
                            await giveaway.update(**filtered_data)
                            if filtered_data.get("winner_amount") is not None and giveaway.state == db.giveaways.GiveawayState.ENDED:
                                await giveaway.reroll(self.bot, guild, request.authenticated_user)
                            channel = await self.bot.getch_channel(giveaway.channel_id)
                            message = await channel.fetch_message(giveaway.message_id)
                            await message.edit(embed=EMBED_STANDARD(
                                title=f"Giveaway hosted by <@{giveaway.host}>"
                            ).add_field(
                                name="Prize",
                                value=giveaway.prize,
                                inline=False
                            ).add_field(
                                name="Winners",
                                value=giveaway.winners,
                                inline=True
                            ).add_field(
                                name="Ends In",
                                value=format_timespan((datetime.fromtimestamp(giveaway.ends_at) - datetime.now()).total_seconds()),
                                inline=True
                            ))
                        except Exception as e:
                            print(f"Failed to update giveaway {giveaway.id} for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                            return jsonify({"status": "error", "error": "Something went wrong while updating giveaway."}), 500
                        else:
                            return jsonify({"status": "success", "giveaway": {
                                "id": giveaway.id,
                                "prize": giveaway.prize,
                                "ends_at": giveaway.ends_at.timestamp(),
                                "channel_id": giveaway.channel_id,
                                "message_id": giveaway.message_id,
                                "host_id": giveaway.host,
                                "state": giveaway.state.value,
                                "winners": giveaway.winners,
                                "entrants": giveaway.total_entries
                            }})
        
        @app.route("/servers/<string:server_id>/giveaways/<int:giveaway_id>/end", methods=["POST"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE], allow_methods=["POST"])
        @authenticated
        @dashboard_access
        @has_any_permissions(host_giveaways=True, manage_giveaways=True)
        async def EndGiveaway(server_id: str, giveaway_id: int):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    giveaway = await db.giveaways.fetch_giveaway(guild_id=server_id, id=giveaway_id)
                except db.NotFound:
                    return jsonify({"status": "error", "error": "Giveaway not found."}), 404
                except Exception as e:
                    print(f"Failed to fetch giveaway for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                    return jsonify({"status": "error", "error": "Something went wrong while fetching giveaway information."}), 500
                else:
                    try:
                        await giveaway.end(self.bot, guild, request.authenticated_user)
                    except Exception as e:
                        print(f"Failed to end giveaway {giveaway.id} for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                        return jsonify({"status": "error", "error": "Something went wrong while ending giveaway."}), 500
                    else:
                        return jsonify({"status": "success", "giveaway": {
                            "id": giveaway.id,
                            "prize": giveaway.prize,
                            "ends_at": giveaway.ends_at.timestamp(),
                            "channel_id": giveaway.channel_id,
                            "message_id": giveaway.message_id,
                            "host_id": giveaway.host,
                            "state": giveaway.state.value,
                            "winners": giveaway.winners,
                            "entrants": giveaway.total_entries
                        }})
        
        @app.route("/servers/<string:server_id>/giveaways/<int:giveaway_id>/cancel", methods=["POST"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE], allow_methods=["POST"])
        @authenticated
        @dashboard_access
        @has_any_permissions(host_giveaways=True, manage_giveaways=True)
        async def CancelGiveaway(server_id: str, giveaway_id: int):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    giveaway = await db.giveaways.fetch_giveaway(guild_id=server_id, id=giveaway_id)
                except db.NotFound:
                    return jsonify({"status": "error", "error": "Giveaway not found."}), 404
                except Exception as e:
                    print(f"Failed to fetch giveaway for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                    return jsonify({"status": "error", "error": "Something went wrong while fetching giveaway information."}), 500
                else:
                    try:
                        await giveaway.cancel(self.bot, guild, request.authenticated_user)
                    except Exception as e:
                        print(f"Failed to cancel giveaway {giveaway.id} for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                        return jsonify({"status": "error", "error": "Something went wrong while cancelling giveaway."}), 500
                    else:
                        return jsonify({"status": "success", "giveaway": {
                            "id": giveaway.id,
                            "prize": giveaway.prize,
                            "ends_at": giveaway.ends_at.timestamp(),
                            "channel_id": giveaway.channel_id,
                            "message_id": giveaway.message_id,
                            "host_id": giveaway.host,
                            "state": giveaway.state.value,
                            "winners": giveaway.winners,
                            "entrants": giveaway.total_entries
                        }})
        
        @app.route("/servers/<string:server_id>/giveaways/<int:giveaway_id>/reroll", methods=["POST"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE], allow_methods=["POST"])
        @authenticated
        @dashboard_access
        @has_any_permissions(host_giveaways=True, manage_giveaways=True)
        async def RerollGiveaway(server_id: str, giveaway_id: int):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    giveaway = await db.giveaways.fetch_giveaway(guild_id=server_id, id=giveaway_id)
                except db.NotFound:
                    return jsonify({"status": "error", "error": "Giveaway not found."}), 404
                except Exception as e:
                    print(f"Failed to fetch giveaway for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                    return jsonify({"status": "error", "error": "Something went wrong while fetching giveaway information."}), 500
                else:
                    try:
                        await giveaway.reroll(self.bot, guild, request.authenticated_user)
                    except Exception as e:
                        print(f"Failed to reroll giveaway {giveaway.id} for server {guild.name} ({guild.id}): {type(e).__name__} - {e}")
                        return jsonify({"status": "error", "error": "Something went wrong while rerolling giveaway."}), 500
                    else:
                        return jsonify({"status": "success", "giveaway": {
                            "id": giveaway.id,
                            "prize": giveaway.prize,
                            "ends_at": giveaway.ends_at.timestamp(),
                            "channel_id": giveaway.channel_id,
                            "message_id": giveaway.message_id,
                            "host_id": giveaway.host,
                            "state": giveaway.state.value,
                            "winners": giveaway.winners,
                            "entrants": giveaway.total_entries
                        }})

def setup(bot: commands.Bot):
    bot.add_cog(Giveaways(bot))