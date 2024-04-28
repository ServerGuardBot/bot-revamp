from .server import Server, AuditLog, ChannelConfig, ChannelConfigType, RoleConfig, RoleConfigType
from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import ServerNotFound, DatabaseError, NotInServer
from core.images import IMAGE_DEFAULT_AVATAR
from surrealdb.ws import SurrealException
from .user import ServerUser
from typing import Union

import guilded

async def fetch_or_create_server(server_id: Union[str, guilded.Server]) -> Server:
    from base import bot
    if isinstance(server_id, guilded.Server):
        guild = server_id
    else:
        guild = bot.get_server(server_id)
    if guild is None:
        raise NotInServer

    try:
        server = await fetch_server(guild)
    except ServerNotFound:
        if guild.member_count == 0:
            # I doubt this is possible, but just in case...
            await guild.fill_members()
            
        server = await create_server(
            guild.id,
            guild.name,
            guild.about,
            guild.avatar.url if guild.avatar else IMAGE_DEFAULT_AVATAR,
            guild.member_count,
        )
    return server

async def fetch_server(server_id: Union[str, guilded.Server]) -> Server:
    if isinstance(server_id, guilded.Server):
        server_id = server_id.id
    cached = valkey.get(f"db:server:{server_id}")
    if cached:
        return await Server.create(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("getGuild"), {
                "id": server_id
            })
        except:
            raise ServerNotFound
        else:
            if resultExists(result):
                return await Server.create(result[0]["result"][0])
            else:
                raise ServerNotFound

async def create_server(
    server_id: str,
    name: str,
    bio: str,
    avatar: str,
    members: int,
) -> Server:
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("createGuild"), {
                "id": server_id,
                "name": name,
                "bio": bio,
                "avatar": avatar,
                "members": members,
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(result):
                valkey.set(f"db:server:{server_id}", encoder.encode(result[0]["result"][0]), 86400)
                return await Server.create(result[0]["result"][0])
            else:
                raise DatabaseError(result[0]["result"])

async def count_servers() -> int:
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("countGuilds"))
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(result):
                return result[0]["result"][0]["count"]
            else:
                raise DatabaseError(result[0]["result"])