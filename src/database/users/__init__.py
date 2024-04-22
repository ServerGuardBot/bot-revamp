from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from core.images import IMAGE_DEFAULT_AVATAR
from surrealdb.ws import SurrealException
from typing import Union

from .user import User
from .identifier import Identifier

import guilded

async def fetch_or_create_user(user: Union[guilded.User, guilded.Member]) -> User:
    try:
        user = await fetch_user(user.id)
    except NotFound:
        user = await create_user(user.id, user.name, user.display_avatar.url)
    return user

async def fetch_user(id: str) -> User:
    cached = valkey.get(f"db:user:{id}")
    if cached:
        return User(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getUser"), {
                "id": id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                raw = response[0]["result"][0]
                valkey.set(f"db:user:{id}", encoder.encode(raw), 86400)
                return User(raw)
            else:
                raise NotFound

async def create_user(id: str, name: str, avatar: str=IMAGE_DEFAULT_AVATAR) -> User:
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createUser"), {
                "id": id,
                "name": name,
                "avatar": avatar
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                raw = response[0]["result"][0]
                valkey.set(f"db:user:{id}", encoder.encode(raw), 86400)
                return User(raw)

async def fetch_identifier(user_id: str):
    cached = valkey.get(f"db:identifier:{user_id}")
    if cached:
        return Identifier(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getIdentifier"), {
                "id": user_id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                raw = response[0]["result"][0]
                valkey.set(f"db:identifier:{user_id}", encoder.encode(raw))
                return Identifier(raw)
            else:
                raise NotFound

async def create_identifier(user_id: str):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createIdentifier"), {
                "id": user_id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                raw = response[0]["result"][0]
                valkey.set(f"db:identifier:{user_id}", encoder.encode(raw))
                return Identifier(raw)

async def find_matching_identifiers(
    ids: list,
    connections: dict,
    hashed_ip: str,
    browser_id: str,
):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getMatchingIdentifiers"), {
                "ids": ids,
                "connections": connections,
                "hashed_ip": hashed_ip,
                "browser_id": browser_id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            for item in raw:
                valkey.set(f"db:identifier:{item['id']}", encoder.encode(item), 86400)
            return [Identifier(raw) for raw in response[0]["result"]]

async def count_users() -> int:
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("countUsers"))
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(result):
                return result[0]["result"][0]["count"]
            else:
                raise DatabaseError(result[0]["result"])