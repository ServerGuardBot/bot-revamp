from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions, DatabaseModel
from typing import Optional, TypedDict, List, Dict, Optional, Union
from database.exceptions import DatabaseError
from core.images import IMAGE_DEFAULT_AVATAR
from surrealdb.ws import SurrealException
from datetime import datetime
from enum import Enum

import guilded

class ServerUser(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)

        self.server_id: str = data["guild_id"]
        self.user_id: str = data["user_id"]
        
        self.perms: UserPermissions = UserPermissions.from_string(data["perms"])
        self.xp: int = data["xp"]
        self.is_banned: bool = data["is_banned"]
        self.bypass_verification: bool = data["bypass_verification"]
        self.roles: List[str] = data["roles"]
        self.note: str = data.get("note", "")
        
        self.join_date: datetime = data["join_date"]
        
    @property
    def can_access_dash(self):
        return self.perms.can_access_dash

    async def warnings(self):
        import database
        return await database.statuses.get_statuses(
            ["warn"],
            self.server_id,
            self.user_id
        )
    
    async def reminders(self):
        import database
        return await database.statuses.get_statuses(
            ["reminder"],
            self.server_id,
            self.user_id
        )
    
    async def create_reminder(
        self,
        message: str,
        message_id: str,
        channel_id: str,
        ends: str
    ):
        from database.statuses import Reminder
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("addReminder"), {
                    "guild_id": self.server_id,
                    "user_id": self.user_id,
                    "message": message,
                    "message_id": message_id,
                    "channel_id": channel_id,
                    "ends": ends
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    raw = response[0]["result"][0]
                    valkey.set(f"db:reminder:{self.server_id}:{self.user_id}:{raw['id']}", encoder.encode(raw))
                    return Reminder(raw)
                else:
                    raise DatabaseError("Failed to create reminder")
    
    async def set_roles(self, roles: List[Union[str, int]]):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("updateGuildUserRoles"), {
                    "guild": self.server_id,
                    "user_id": self.user_id,
                    "roles": roles
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.roles = roles
                self.__raw["roles"] = roles
                valkey.set(f"db:server_user:{self.server_id}:{self.user_id}", encoder.encode(self.__raw), 86400)
    
    async def set_perms(self, perms: UserPermissions):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("updateGuildUserPerms"), {
                    "guild": self.server_id,
                    "user_id": self.user_id,
                    "perms": str(perms),
                    "acces": perms.can_access_dash
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.perms = perms
                self.__raw["perms"] = str(perms)
                valkey.set(f"db:server_user:{self.server_id}:{self.user_id}", encoder.encode(self.__raw), 86400)
    
    async def set_banned(self, banned: bool):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("updateGuildUserBanned"), {
                    "guild": self.server_id,
                    "user_id": self.user_id,
                    "banned": banned
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.is_banned = banned
                self.__raw["is_banned"] = banned
                valkey.set(f"db:server_user:{self.server_id}:{self.user_id}", encoder.encode(self.__raw), 86400)
    
    async def set_note(self, note: str):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("updateGuildUserNote"), {
                    "guild": self.server_id,
                    "user_id": self.user_id,
                    "note": note
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.note = note
                self.__raw["note"] = note
                valkey.set(f"db:server_user:{self.server_id}:{self.user_id}", encoder.encode(self.__raw), 86400)
    
    async def set_xp(self, xp: int):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("updateGuildUserXP"), {
                    "guild": self.server_id,
                    "id": self.user_id,
                    "xp": xp
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.xp = xp
                self.__raw["xp"] = xp
                valkey.set(f"db:server_user:{self.server_id}:{self.user_id}", encoder.encode(self.__raw), 86400)
    
    async def delete(self):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("deleteGuildUser"), {
                    "guild": self.server_id,
                    "user_id": self.user_id
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                valkey.delete(f"db:server_user:{self.server_id}:{self.user_id}")
    
    async def unban(self):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("unbanUser"), {
                    "guild_id": self.server_id,
                    "user_id": self.user_id
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
    
    async def warn(
        self,
        issuer: str,
        reason: str,
        ends: str=None
    ):
        async with DBConnection() as db:
            try:
                if ends:
                    await db.query(loadQuery("tempWarnUser"), {
                        "guild_id": self.server_id,
                        "user_id": self.user_id,
                        "issuer": issuer,
                        "reason": reason,
                        "ends": ends
                    })
                else:
                    await db.query(loadQuery("warnUser"), {
                        "guild_id": self.server_id,
                        "user_id": self.user_id,
                        "issuer": issuer,
                        "reason": reason
                    })
            except SurrealException as e:
                raise DatabaseError(str(e))
    
    async def temp_ban(
        self,
        issuer: str,
        reason: str,
        ends: str
    ):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("tempBanUser"), {
                    "guild_id": self.server_id,
                    "user_id": self.user_id,
                    "reason": reason,
                    "ends": ends
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
    
    async def clear_statuses(
        self,
        types: Union[List[str], str]
    ):
        if isinstance(types, str):
            types = [types]
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("clearStatuses"), {
                    "guild_id": self.server_id,
                    "user_id": self.user_id,
                    "types": types
                })
            except SurrealException as e:
                raise DatabaseError(str(e))