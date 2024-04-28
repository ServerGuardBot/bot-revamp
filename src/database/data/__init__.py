from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException
from typing import Any

async def get(key: str):
    cached = valkey.get(f"db:data:{key}")
    if cached:
        return decoder.decode(cached)["value"]
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("getBotData"), {
                "id": key
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(result):
                valkey.set(f"db:data:{key}", encoder.encode({"value": result["results"][0]["value"]}), 86400)
                return result["results"][0]["value"]
            else:
                raise NotFound()

async def set(key: str, value: Any):
    async with DBConnection() as db:
        try:
            await db.query(loadQuery("setBotData"), {
                "id": key,
                "value": value
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            valkey.set(f"db:data:{key}", encoder.encode({"value": value}), 86400)
            return value

async def increment(key: str, value: int):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("incrementBotData"), {
                "id": key,
                "value": value
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set(f"db:data:{key}", encoder.encode({"value": response["results"][0]["value"]}), 86400)
                return response["results"][0]["value"]
            else:
                raise DatabaseError("Failed to increment bot data.")

async def decrement(key: str, value: int):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("decrementBotData"), {
                "id": key,
                "value": value
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set(f"db:data:{key}", encoder.encode({"value": response["results"][0]["value"]}), 86400)
                return response["results"][0]["value"]
            else:
                raise DatabaseError("Failed to decrement bot data.")