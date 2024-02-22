BOT_VERSION = "1.0.0"

from dotenv import load_dotenv
load_dotenv()

from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from database import DBConnection, loadQuery, resultExists
from database.permissions import UserPermissions
from core.bot import Bot, HelpCommand, prefix
from database.setup import try_db_setup
from quart_cors import cors, route_cors
from hypercorn.asyncio import serve
from hypercorn.config import Config
from guilded.ext import commands
from quart import Quart, jsonify
from core import checks

import logging
import asyncio
import guilded
import inspect
import config
import glob
import sys
import ssl
import os

logger = logging.getLogger("guilded")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="guilded.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

cogs = [os.path.basename(f) for f in glob.glob("modules/*.py")]
startup = [f"modules.{os.path.splitext(f)[0]}" for f in cogs]

client_features = guilded.ClientFeatures(
    experimental_event_style=True,
    official_markdown=True,
)

bot = Bot(
    command_prefix=prefix,
    features=client_features,
    help_command=HelpCommand(), # TODO: Create a custom help command that has i18n support
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    async with DBConnection() as db:
        for server in await bot.fetch_servers():
            print(f"Checking guild {server.name} ({server.id}) for database row")
            if server.member_count == 0:
                await server.fill_members()
            guildData = await db.query(loadQuery("getGuild"), {"id": server.id})
            if not resultExists(guildData):
                print(f"Will try creating guild {server.name} ({server.id}) in database")
                await db.query(
                    loadQuery("createGuild"),
                    {
                        "id": server.id,
                        "name": server.name,
                        "bio": server.about,
                        "members": server.member_count,
                    }
                )
                print(f"Created guild {server.name} ({server.id}) in database")
            for member in server.members:
                if member.bot: continue
                guildUserData = await db.query(loadQuery("getGuildUser"), {"id": member.id, "guild": server.id})
                if not resultExists(guildUserData):
                    print(f"Will try creating guild user {member.name} ({member.id}) for server {server.name} ({server.id}) in database")
                    if member.id == server.owner_id:
                        perms = UserPermissions.all()
                    elif (await member.fetch_permissions()).manage_server:
                        perms = UserPermissions.manager()
                    else:
                        perms = UserPermissions.none() # TODO: Calculate perms based on roles
                    await db.query(loadQuery("createGuildUser"), {
                        "id": member.id,
                        "guild": server.id,
                        "access": perms.can_access_dash,
                        "perms": str(perms),
                        "banned": False,
                        "xp": (await member.award_xp(0)), # Stupid hack because you can't just fetch XP >:(
                    })
                    print(f"Created user {member.name} ({member.id}) for server {server.name} ({server.id}) in database")
                userData = await db.query(loadQuery("getUser"), {"id": member.id})
                if not resultExists(userData):
                    print(f"Will try creating user {member.name} ({member.id}) in database")
                    await db.query(loadQuery("createUser"), {
                        "id": member.id,
                        "name": member.name,
                        "avatar": member.display_avatar.url,
                    })
                    print(f"Created user {member.name} ({member.id}) in database")
            for ban in await server.bans():
                if ban.user.bot: continue
                guildUserData = await db.query(loadQuery("getGuildUser"), {"id": ban.user.id, "guild": server.id})
                if resultExists(guildUserData):
                    print(f"Will try setting user {ban.user.name} ({ban.user.id}) for server {server.name} ({server.id}) in database to banned")
                    await db.query(loadQuery("updateGuildUserBan"), {
                        "banned": True,
                        "id": ban.user.id,
                        "guild": server.id,
                    })
                    print(f"Set user {ban.user.name} ({ban.user.id}) for server {server.name} ({server.id}) in database to banned")
                else:
                    perms = UserPermissions.none()
                    await db.query(loadQuery("createGuildUser"), {
                        "id": ban.user.id,
                        "guild": server.id,
                        "access": perms.can_access_dash,
                        "perms": str(perms),
                        "banned": True,
                        "xp": 0, # Banned users don't have XP lol
                    })
                    print(f"Created user {ban.user.name} ({ban.user.id}) for server {server.name} ({server.id}) as banned in database")
    print("Bot online and ready to go!")

@bot.event
async def on_bot_add(event: guilded.BotAddEvent):
    server = event.server
    try:
        default = await server.fetch_default_channel()
    except:
        pass
    else:
        if isinstance(default, guilded.ChatChannel):
            await default.send(embed=EMBED_STANDARD(
                title="Hello!",
                description=f"Thanks <@{event.member_id}> for inviting me to **{server.name}!**\n\nTo start configuring Server Guard, access your server's dashboard [here](https://serverguard.xyz/account)!"
            ))
    
    async with DBConnection() as db:
        guildData = await db.query(loadQuery("getGuild"), {"id": server.id})
        if not resultExists(guildData):
            print(f"Will try creating guild {server.name} ({server.id}) in database")
            if server.member_count == 0:
                await server.fill_members()
            await db.query(
                loadQuery("createGuild"),
                {
                    "id": server.id,
                    "name": server.name,
                    "bio": server.about,
                    "members": server.member_count,
                }
            )
            print(f"Created guild {server.name} ({server.id}) in database")
        else:
            print(f"Guild {server.name} ({server.id}) already exists in database, setting it to active")
            await db.query(loadQuery("updateGuildActive"), {
                "active": True,
                "id": server.id,
            })
        for ban in await server.bans():
            guildUserData = await db.query(loadQuery("getGuildUser"), {"id": ban.user.id, "guild": server.id})
            if resultExists(guildUserData):
                print(f"Will try setting user {ban.user.name} ({ban.user.id}) for server {server.name} ({server.id}) in database to banned")
                await db.query(loadQuery("updateGuildUserBan"), {
                    "banned": True,
                    "id": ban.user.id,
                    "guild": server.id,
                })
                print(f"Set user {ban.user.name} ({ban.user.id}) for server {server.name} ({server.id}) in database to banned")
            else:
                perms = UserPermissions.none()
                await db.query(loadQuery("createGuildUser"), {
                    "id": ban.user.id,
                    "guild": server.id,
                    "access": perms.can_access_dash,
                    "perms": str(perms),
                    "banned": True,
                    "xp": 0, # Banned users don't have XP lol
                })
                print(f"Created user {ban.user.name} ({ban.user.id}) for server {server.name} ({server.id}) as banned in database")

@bot.event
async def on_bot_remove(event: guilded.BotRemoveEvent):
    server = event.server
    async with DBConnection() as db:
        guildData = await db.query(loadQuery("getGuild"), {"id": server.id})
        if resultExists(guildData):
            print(f"Will try setting guild {server.name} ({server.id}) in database to inactive")
            await db.query(loadQuery("updateGuildActive"), {
                "active": False,
                "id": server.id,
            })
            print(f"Set guild {server.name} ({server.id}) in database to inactive")
        else:
            print(f"Guild {server.name} ({server.id}) does not exist in database, ignoring")

@bot.event
async def on_command_error(ctx: commands.Context, error):
    print('{}: {}'.format(type(error), error))
    if isinstance(error, commands.CommandNotFound):
        await ctx.reply(
            embed=EMBED_DENIED(title="Command Not Found", description=f"Command `{ctx.invoked_with}` not found")
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        param: inspect.Parameter = error.param
        await ctx.reply(
            embed=EMBED_DENIED(title="Missing Argument", description=f"Missing required argument `{param.name}`")
        )
    elif isinstance(error, commands.CommandError):
        await ctx.reply(
            embed=EMBED_DENIED(title="Command Error", description=f"An error occurred while running command `{ctx.invoked_with}`:\n{' '.join(error.args)}")
        )
    else:
        # NOTE: Maybe should log the error in an internal channel as well and offer the user an error id?
        await ctx.reply(
            embed=EMBED_DENIED(title="Command Error", description=f"An unexpected error occurred while running command `{ctx.invoked_with}`")
        )

@bot.event
async def on_command(ctx: commands.Context):
    # Prepare commands to be localized
    # TODO: Once localization has been implemented, provide the translator here
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getUser"), {"id": ctx.author.id})
        except:
            ctx.language = "en"
        else:
            if resultExists(response):
                ctx.language = response[0]["result"][0].get("language", "en")
            else:
                ctx.language = "en"

dev_cog = commands.Cog()
dev_cog.__cog_name__ = "Developer"

@bot.command()
@checks.developer_only()
async def load(_, ctx: commands.Context, module: str):
    """Loads a module."""
    module = f"modules.{module}"
    try:
        bot.load_extension(module)
    except Exception as e:
        em = EMBED_DENIED(title="Module Load Error", description=f"Error loading `{module}`\n```{e}```")
        await ctx.reply(embed=em)
        print('{}: {}'.format(type(e), e))
    else:
        em = EMBED_SUCCESS(title="Module Loaded", description=f"Loaded `{module}`")
        await ctx.reply(embed=em)

@bot.command()
@checks.developer_only()
async def unload(_, ctx: commands.Context, module: str):
    module = f"modules.{module}"
    if module in bot.extensions:
        bot.unload_extension(module)
        em = EMBED_SUCCESS(title="Module Unloaded", description=f"Unloaded `{module}`")
        await ctx.reply(embed=em)
    else:
        em = EMBED_DENIED(title="Module Not Loaded", description=f"Module `{module}` is not loaded")
        await ctx.reply(embed=em)

@bot.command()
@checks.developer_only()
async def reload(_, ctx: commands.Context, module: str=None):
    if module == None:
        em = EMBED_STANDARD(title="Bot Reload", description="Reloading bot")
        await ctx.reply(embed=em)
        os.execv(sys.executable, ['python'] + sys.argv)
    else:
        module = f"modules.{module}"
        try:
            bot.unload_extension(module)
            bot.load_extension(module)
        except Exception as e:
            em = EMBED_DENIED(title="Module Reload Error", description=f"Error reloading `{module}`\n```{e}```")
            await ctx.reply(embed=em)
            print('{}: {}'.format(type(e), e))
        else:
            em = EMBED_SUCCESS(title="Module Reloaded", description=f"Reloaded `{module}`")
            await ctx.reply(embed=em)

load.cog = dev_cog
unload.cog = dev_cog
reload.cog = dev_cog
bot.add_cog(dev_cog)

async def run_bot_and_api():
    await try_db_setup()

    for mod in startup:
        bot.load_extension(mod)
        print(f"Loaded {mod}")
    
    app = Quart(__name__)
    app.config["bot"] = bot
    app = cors(app, allow_origin=[config.ORIGIN_SITE], allow_credentials=True)

    for cog in bot.cogs.values():
        if hasattr(cog, "register_routes"):
            cog.register_routes(app)
    
    @app.route("/uptime", methods=["GET"])
    @route_cors(allow_methods=["GET"], allow_origin=["*"], allow_credentials=False)
    async def Uptime():
        bot_latency = bot.latency * 1000

        return jsonify({
            "bot_latency": bot_latency
        })
    
    app_config = Config()
    app_config.bind = ["localhost:7777"]

    if os.path.exists(config.SSL_CERTIFICATE) and os.path.exists(config.SSL_KEY):
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(config.SSL_CERTIFICATE, config.SSL_KEY)
        app_config.ssl = context
    
    bot_task = bot.start(config.TOKEN)
    api_task = serve(app, app_config)

    await asyncio.gather(bot_task, api_task)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_bot_and_api())
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())