from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException

from .token import *

async def get_token(id: str):
    cached = valkey.get(f"db:user_token:{id}")
    if cached:
        raw = decoder.decode(cached.decode("utf-8"))
        if raw["type"] == "login":
            return LoginToken(raw)
        elif raw["type"] == "verify":
            return VerifyToken(raw)
        else:
            return UserToken(raw)
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getToken"), {
                "id": id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                raw = response[0]["result"][0]
                valkey.set(f"db:user_token:{id}", encoder.encode(raw), 60)
                if raw["type"] == "login":
                    return LoginToken(raw)
                elif raw["type"] == "verify":
                    return VerifyToken(raw)
                else:
                    return UserToken(raw)
            else:
                raise NotFound

async def create_login_token(
    location: str,
    browser: str,
    platform: str,
    lock: str
):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createLoginToken"), {
                "location": location,
                "browser": browser,
                "platform": platform,
                "lock": lock
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            token = LoginToken(response[0]["result"][0])
            valkey.set(f"db:user_token:{token.id}", encoder.encode(token.__raw), 60)
            return token

async def create_verify_token(
    user_id: str,
    guild_id: str
):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createVerifyToken"), {
                "user_id": user_id,
                "guild_id": guild_id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            token = VerifyToken(response[0]["result"][0])
            valkey.set(f"db:user_token:{token.id}", encoder.encode(token.__raw), 60)
            return token

async def blacklist_refresh_token(id: str, expires: int):
    async with DBConnection() as db:
        try:
            await db.query(loadQuery("blacklistRefreshToken"), {
                "id": id,
                "expires": expires
            })
        except SurrealException as e:
            raise DatabaseError(str(e))

async def is_refresh_token_valid(id: str):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getBlacklistedToken"), {
                "id": id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                return False
            else:
                return True

async def cleanup_tokens():
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("cleanupTokens"))
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response) and resultExists(response, 1):
                print("Cleaned up user tokens")
                print("Cleaned up refresh token blacklist")
                return True
            else:
                if not resultExists(response, accept_empty=True):
                    print("Failed to clean up user tokens")
                if not resultExists(response, 1, accept_empty=True):
                    print("Failed to clean up refresh token blacklist")
                return False