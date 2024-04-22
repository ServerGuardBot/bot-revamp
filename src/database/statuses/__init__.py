from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException
from typing import Union, List

from .status import *

async def get_statuses(types: List[str], guild_id:str, user_id:str) -> List[Union[UserStatus, Warning, TempBan, Reminder]]:
    key = f"db:statuses:{guild_id}:{user_id}:{str(hash(tuple(types)))}"
    cached = valkey.get(key)
    if cached:
        raw = decoder.decode(cached.decode("utf-8"))
        res = []
        for raw in raw:
            if raw["type"] == "warn":
                res.append(Warning(raw))
            elif raw["type"] == "tempban":
                res.append(TempBan(raw))
            elif raw["type"] == "reminder":
                res.append(Reminder(raw))
            else:
                res.append(UserStatus(raw))
        return res
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("getStatuses", {
                "types": types,
                "guild_id": guild_id,
                "user_id": user_id
            }))
        except SurrealException as e:
            raise DatabaseError(str(e))

        if resultExists(result):
            valkey.set(key, encoder.encode(result[0]["result"]), 60)
            res = []
            for raw in result[0]["result"]:
                if raw["type"] == "warn":
                    res.append(Warning(raw))
                elif raw["type"] == "tempban":
                    res.append(TempBan(raw))
                elif raw["type"] == "reminder":
                    res.append(Reminder(raw))
                else:
                    res.append(UserStatus(raw))
            return res

async def get_status(id: str) -> Union[UserStatus, Warning, TempBan, Reminder]:
    cached = valkey.get(f"db:statuses:{id}")
    if cached:
        raw = decoder.decode(cached.decode("utf-8"))
        if raw["type"] == "warn":
            return Warning(raw)
        elif raw["type"] == "tempban":
            return TempBan(raw)
        elif raw["type"] == "reminder":
            return Reminder(raw)
        else:
            return UserStatus(raw)
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("getStatus", {
                "id": id
            }))
        except SurrealException as e:
            raise DatabaseError(str(e))

        if resultExists(result):
            raw = result[0]["result"][0]
            valkey.set(f"db:statuses:{id}", encoder.encode(raw), 86400)
            if raw["type"] == "warn":
                return Warning(raw)
            elif raw["type"] == "tempban":
                return TempBan(raw)
            elif raw["type"] == "reminder":
                return Reminder(raw)
            else:
                return UserStatus(raw)
        else:
            raise NotFound

async def expire_statuses(ids: List[str]):
    async with DBConnection() as db:
        try:
            await db.query(loadQuery("expireStatuses"), {
                "ids": ids
            })
        except SurrealException as e:
            raise DatabaseError(str(e))

async def get_expired_statuses(types: List[str]) -> List[Union[UserStatus, Warning, TempBan, Reminder]]:
    async with DBConnection() as db:
        try:
            result = await db.query(loadQuery("getExpiredStatuses", {
                "types": types
            }))
        except SurrealException as e:
            raise DatabaseError(str(e))

        if resultExists(result):
            res = []
            for raw in result[0]["result"]:
                if raw["type"] == "warn":
                    res.append(Warning(raw))
                elif raw["type"] == "tempban":
                    res.append(TempBan(raw))
                elif raw["type"] == "reminder":
                    res.append(Reminder(raw))
                else:
                    res.append(UserStatus(raw))
            return res
        else:
            return []