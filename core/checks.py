from database import DBConnection, loadQuery, resultExists
from database.permissions import UserPermissions
from guilded.ext import commands
from functools import wraps
from core import defaults

import config
import guilded

def is_premium_guild():
    async def predicate(ctx: commands.Context):
        if ctx.server:
            async with DBConnection() as db:
                guildData = await db.query(loadQuery("getGuild"), {
                    "id": ctx.server.id,
                })
                if resultExists(guildData):
                    premium: str = guildData[0]["result"][0]["premium"]
                    if premium[0] == "1":
                        # Only check the first character in case
                        # there are more types in the future
                        return True
        return False
    return commands.check(predicate)

def listener(module: str):
    """
    A decorator for cog listeners that makes sure it only executes
    if the module is enabled for the guild.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(cog: commands.Cog, event: guilded.ServerEvent):
            if getattr(event, "server") or getattr(event, "server_id"):
                async with DBConnection() as db:
                    guildData = await db.query(loadQuery("getGuild"), {
                        "id": event.server_id,
                    })
                    if resultExists(guildData):
                        modules = guildData[0]["result"][0].get("modules", defaults.modules)
                        if module in modules:
                            return await func(cog, event)
            return None
        return wrapper
    return decorator

async def is_module_enabled(name: str, event: guilded.ServerEvent):
    """
    A function to check if a module is enabled based on an event
    without preventing the rest of the command/listener from running.
    """
    if getattr(event, "server") or getattr(event, "server_id"):
        async with DBConnection() as db:
            guildData = await db.query(loadQuery("getGuild"), {
                "id": event.server_id,
            })
            if resultExists(guildData):
                modules = guildData[0]["result"][0].get("modules", defaults.modules)
                if name in modules:
                    return True
    return False

def module(name: str):
    async def predicate(ctx: commands.Context):
        if ctx.server:
            async with DBConnection() as db:
                guildData = await db.query(loadQuery("getGuild"), {
                    "id": ctx.server.id,
                })
                if resultExists(guildData):
                    modules = guildData[0]["result"][0].get("modules", defaults.modules)
                    if name in modules:
                        return True
        return False
    return commands.check(predicate)

async def user_has_permissions(user: guilded.Member, **permissions):
    if isinstance(user, guilded.Member):
        async with DBConnection() as db:
            try:
                userData = await db.query(loadQuery("getGuildUser"), {
                    "id": user.id,
                    "guild": user.server.id,
                })
            except:
                return False
            if resultExists(userData):
                perms = UserPermissions.from_string(userData[0]["result"][0]["perms"])
                for permission in permissions:
                    if not getattr(perms, permission):
                        return False
                return True
    return False

async def user_has_any_permissions(user: guilded.Member, **permissions):
    if isinstance(user, guilded.Member):
        async with DBConnection() as db:
            try:
                userData = await db.query(loadQuery("getGuildUser"), {
                    "id": user.id,
                    "guild": user.server.id,
                })
            except:
                return False
            if resultExists(userData):
                perms = UserPermissions.from_string(userData[0]["result"][0]["perms"])
                for permission in permissions:
                    if getattr(perms, permission):
                        return True
                return False
    return False

def has_permissions(**permissions):
    async def predicate(ctx: commands.Context):
        if ctx.server:
            async with DBConnection() as db:
                userData = await db.query(loadQuery("getGuildUser"), {
                    "id": ctx.author.id,
                    "guild": ctx.server.id,
                })
                if resultExists(userData):
                    perms = UserPermissions.from_string(userData[0]["result"][0]["perms"])
                    has = True
                    for permission in permissions:
                        if not getattr(perms, permission):
                            has = False
                    if has:
                        return True
        return False
    return commands.check(predicate)

def developer_only():
    async def predicate(ctx: commands.Context):
        bot = ctx.bot
        support_server = await bot.getch_server(config.SUPPORT_SERVER_ID)
        author = await support_server.getch_member(ctx.author.id)
        if author:
            roles = await author.fetch_role_ids()
            if int(config.DEVELOPER_ROLE_ID) in roles:
                return True
        return False
    return commands.check(predicate)