BOT_VERSION = "1.0.0"

from dotenv import load_dotenv
load_dotenv()

from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from quart_rate_limiter.store import RateLimiterStoreABC
from database.permissions import UserPermissions
from core.bot import Bot, HelpCommand, prefix
from prometheus_client import make_asgi_app
from quart_rate_limiter import RateLimiter
from quart import Quart, jsonify, request
from python_loki_logger import LokiLogger
from database.setup import setup_db
from quart_cors import cors, route_cors
from libs.translator import Translator
from hypercorn.asyncio import serve
from hypercorn.config import Config
from libs.loki import LokiHandler
from guilded.ext import commands
from database import valkey
from core import checks

import database as db
import logging
import asyncio
import guilded
import inspect
import config
import glob
import sys
import ssl
import os
import io

cogs = [os.path.basename(f) for f in glob.glob("src/modules/*.py")]
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

## BOT EVENTS ##

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    if config.DATABASE_DB == "dev":
        # Because an in-memory surrealdb instance is used in development
        # clear the cache on bot startup to prevent issues.
        valkey.flushall()

    for server in await bot.fetch_servers():
        print(f"Checking guild {server.name} ({server.id}) for database row")
        if server.member_count == 0:
            await server.fill_members()

        try:
            guild = await db.servers.fetch_or_create_server(server)
        except Exception as e:
            print(f"Failed to fetch or create server {server.id} from database: {e}")
        else:
            me = await server.getch_member(bot.user_id)
            if me.nick != None and me.nick != guild.settings.get("nickname"):
                try:
                    await guild.update_settings(
                        nickname=me.nick
                    )
                except Exception as e:
                    print(f"Failed to update nickname for server {server.id} in database: {e}")

            for member in server.members:
                if member.bot: continue
                try:
                    user = await guild.fetch_or_create_member(member)
                except Exception as e:
                    print(f"Failed to fetch or create member {member.id} in server {server.id} in database: {e}")
                else:
                    print(f"Synced member {member.id} in server {server.id} in database")
                
                try:
                    global_user = await db.users.fetch_or_create_user(member)
                except Exception as e:
                    print(f"Failed to fetch or create user {member.id} in database: {e}")
                else:
                    print(f"Synced user {member.id} in database")

            for ban in await server.bans():
                if ban.user.bot: continue
                if user:
                    try:
                        await user.set_banned(True)
                    except Exception as e:
                        print(f"Failed to sync ban state for user {ban.user.id} in server {server.id} in database: {e}")
                    else:
                        print(f"Synced ban state for user {ban.user.id} in server {server.id} in database")
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

    try:
        guild = await db.servers.fetch_or_create_server(server)
    except Exception as e:
        print(f"Failed to fetch or create server {server.id} from database: {e}")
    else:
        if not guild.active:
            try:
                await guild.set_active(True)
            except Exception as e:
                print(f"Failed to set server {server.id} in database to active: {e}")

    for ban in await server.bans():
        if ban.user.bot: continue
        if user:
            try:
                await user.set_banned(True)
            except Exception as e:
                print(f"Failed to sync ban state for user {ban.user.id} in server {server.id} in database: {e}")

@bot.event
async def on_bot_remove(event: guilded.BotRemoveEvent):
    server = event.server
    try:
        guild = await db.servers.fetch_or_create_server(server)
    except Exception as e:
        print(f"Failed to fetch or create server {server.id} from database: {e}")
    else:
        if guild.active:
            try:
                await guild.set_active(False)
            except Exception as e:
                print(f"Failed to set server {server.id} in database to inactive: {e}")

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
    ctx.translator = await Translator.from_context(ctx)

## LOGGER ##

handler = logging.FileHandler(filename="guilded.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))

logger = logging.getLogger("guilded")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

if config.GRAFANA_ROOT and config.GRAFANA_ROOT != "":
    loki_logger = LokiLogger(
        baseUrl=config.LOKI_ROOT,
        auth=config.LOKI_AUTH
    )
    loki_handler = LokiHandler(loki_logger)
    logger.addHandler(loki_handler)

## RATE LIMITER STORE ##

class ValkeyStore(RateLimiterStoreABC):
    """A valkey-based store of rate limits."""

    def __init__(self) -> None:
        pass

    async def get(self, key: str, default: datetime) -> datetime:
        from database.valkey import valkey
        result = valkey.get(f"rate_limit:{key}")
        if result is None:
            return default
        else:
            return datetime.fromtimestamp(float(result))

    async def set(self, key: str, tat: datetime) -> None:
        from database.valkey import valkey
        valkey.set(f"rate_limit:{key}", tat.timestamp())

    async def before_serving(self) -> None:
        pass

    async def after_serving(self) -> None:
        pass

## REST OF CODE ##

class PrometheusMiddleware:
    def __init__(self, app, prometheus):
        self.app = app
        self.prometheus = prometheus

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/metrics":
            await self.prometheus(scope, receive, send)
        else:
            await self.app(scope, receive, send)

async def run_bot_and_api():
    await setup_db()
    
    for mod in startup:
        bot.load_extension(mod)
        print(f"Loaded {mod}")
    
    app = Quart(__name__)
    app.config["bot"] = bot
    app = cors(app, allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
    
    app.asgi_app = PrometheusMiddleware(app.asgi_app, make_asgi_app())
    
    rate_limiter = RateLimiter(app, store=ValkeyStore())

    for cog in bot.cogs.values():
        if hasattr(cog, "register_routes"):
            cog.register_routes(app)
        if hasattr(cog, "after_load"):
            await cog.after_load()
    
    app_config = Config()
    app_config.bind = ["0.0.0.0:7777"]

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