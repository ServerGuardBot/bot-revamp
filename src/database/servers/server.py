from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions, DatabaseModel
from typing import Optional, TypedDict, List, Dict, Optional, Union
from database.exceptions import DatabaseError, NotInServer
from core.images import IMAGE_DEFAULT_AVATAR
from surrealdb.ws import SurrealException
from datetime import datetime
from .user import ServerUser
from enum import Enum

import guilded

class WelcomerCycle(Enum):
    Daily = "Daily"
    Weekly = "Weekly"
    Monthly = "Monthly"
    Random = "Random"
    PerUser = "PerUser"

class FilterRestrictions(TypedDict):
    allow_users: List[str]
    allow_channels: List[str]
    allow_roles: List[str]
    blacklist_users: List[str]
    blacklist_channels: List[str]
    blacklist_roles: List[str]

class ServerSettings(TypedDict, total=False):
    permissions: Dict[str, List[str]]
    modules: List[str]
    
    prefix: str
    nickname: str
    timezone: str
    language: str
    muted_role: Optional[guilded.Role]
    
    untrusted_block_attachments: List[str]
    
    default_profanities: List[str]
    default_profanities_restrictions: FilterRestrictions
    
    word_blacklist: List[str]
    word_blacklist_restrictions: FilterRestrictions
    
    malicious_urls: bool
    malicious_urls_restrictions: FilterRestrictions
    
    spam_filter: int
    spam_filter_restrictions: FilterRestrictions
    
    filter_mass_mentions: bool
    filter_mass_mentions_restrictions: FilterRestrictions
    
    filter_invites: bool
    filter_invites_restrictions: FilterRestrictions
    
    filter_api_keys: bool
    filter_api_keys_restrictions: FilterRestrictions
    
    filter_toxicity: int
    filter_toxicity_restrictions: FilterRestrictions
    
    filter_hatespeech: int
    filter_hatespeech_restrictions: FilterRestrictions
    
    filter_nsfw: int
    filter_nsfw_restrictions: FilterRestrictions
    
    silence_commands: bool
    log_commands: bool
    logs_traffic: Optional[guilded.ChatChannel]
    logs_message: Optional[guilded.ChatChannel]
    logs_verification: Optional[guilded.ChatChannel]
    logs_action: Optional[guilded.ChatChannel]
    logs_user: Optional[guilded.ChatChannel]
    logs_management: Optional[guilded.ChatChannel]
    logs_nsfw: Optional[guilded.ChatChannel]
    logs_automod: Optional[guilded.ChatChannel]
    
    admin_contact: str
    block_tor: bool
    check_ips: bool
    raid_guard: bool
    verified_role: Optional[guilded.Role]
    unverified_role: Optional[guilded.Role]
    verification_channel: Optional[guilded.ChatChannel]
    
    re_toxicity: int
    re_hatespeech: int
    re_nsfw: int
    re_blacklist: List[str]
    
    remove_old_level_roles: bool
    announce_level_up: bool
    xp_roles: Dict[str, int]
    
    send_welcome: bool
    welcome_message: str
    welcome_channel: Optional[guilded.ChatChannel]
    welcome_image: List[str]
    welcome_image_cycle: WelcomerCycle
    
    send_goodbye: bool
    goodbye_message: str
    goodbye_channel: Optional[guilded.ChatChannel]
    goodbye_image: List[str]
    goodbye_image_cycle: WelcomerCycle
    
    giveaway_ping_role: Optional[guilded.Role]
    giveaway_channel: Optional[guilded.ChatChannel]

class AuditLog:
    def __init__(self, data: dict):
        super().__init__(data)

        self.server_id: str = data["guild_id"]
        
        if len(data["id"].split(":")) > 1:
            self.id: str = data["id"].split(":")[1]
        else:
            self.id: str = data["id"]
        
        self.originator_id: str = data["originator_id"]
        self.event_name: str = data["event_name"]
        self.created_at: datetime = data["created_at"]
        
        self.extra_data: dict = {}
        for key in data:
            if not getattr(self, key, None):
                self.extra_data[key] = data[key]

class Server(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)

        self.name: str = data["name"]
        self.bio: str = data.get("bio", "")
        self.avatar: str = data.get("avatar", IMAGE_DEFAULT_AVATAR)
        self.members: int = data["members"]
        
        self.subscription_id: Optional[str] = data.get("subscription_id")
        
        self.active = data["active"]
        self.last_active = data["last_active"]
        
        self.first_seen = data["first_seen"]
        
        self.settings: ServerSettings = {}
    
    @classmethod
    async def create(cls, data: dict):
        self = cls(data)
        await self.deserialize_settings(data)
        return self
    
    @property
    def is_premium(self) -> bool:
        return self.__raw["premium"][0] == "1"
    
    def serialize_settings(self, settings: dict) -> dict:
        if settings is None:
            settings = self.settings
        data = {}
        for key in settings:
            if key == "welcome_image_cycle" or key == "goodbye_image_cycle":
                value = settings[key].value
            elif key.endswith("_role"):
                value = settings[key].id
            elif key.endswith("_channel") or key.startswith("logs"):
                value = settings[key].id
            else:
                value = settings[key]
            data[key] = value
        return data
    
    async def deserialize_settings(self, data: dict):
        for key in data:
            if key in ServerSettings.__annotations__.keys():
                if key.startswith("_"): continue
                key: str
                value = data[key]
                if key == "welcome_image_cycle" or key == "goodbye_image_cycle":
                    value = WelcomerCycle(value)
                elif key.endswith("_role"):
                    try:
                        value = await bot_server.getch_role(value)
                    except:
                        value = None
                elif key.endswith("_channel") or key.startswith("logs"):
                    try:
                        value = await bot_server.getch_channel(value)
                    except:
                        value = None
                self.settings[key] = value
    
    async def update_settings(self, **kwargs):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("updateGuildSettings"), {"guild": self.id, "settings": self.serialize_settings(dict(**kwargs))})
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    await self.deserialize_settings(response[0]["result"][0])
                    serialized = self.serialize_settings()
                    for key in serialized:
                        self.__raw[key] = serialized[key]
                    valkey.set(f"db:server:{self.id}", encoder.encode(self.__raw), 86400)
                    return True

    async def set_active(self, active: bool):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("updateGuildActive"), {"guild": self.id, "active": active})
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    self.__raw["active"] = active
                    valkey.set(f"db:server:{self.id}", encoder.encode(self.__raw), 86400)
                    return True
    
    async def create_audit_log(self, payload: dict) -> AuditLog:
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("createAuditLog"), {"guild": self.id, "payload": payload})
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    return AuditLog(response[0]["result"][0])
    
    async def get_audit_log_users(self):
        cached = valkey.get(f"db:audit_log_users:{self.id}")
        if cached:
            return cached
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery("getAuditLogUsers"), {"guild": self.id})
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    raw = result[0]["result"]
                    valkey.set(f"db:audit_log_users:{self.id}", encoder.encode(raw), 86400)
                    return raw
                else:
                    raise DatabaseError(result[0]["result"])
    
    async def get_audit_logs(
        self,
        start: datetime=None,
        end: datetime=None,
        authors: List[str]=None,
        event_names: List[str]=None,
        limit: int=50,
        page: int=0
    ) -> List[AuditLog]:
        filter_key = f"db:audit_logs:{self.id}:{start}:{end}:{authors}:{event_names}:{limit}:{page}"
        cached = valkey.get(filter_key)
        if cached:
            return [
                AuditLog(item) for item in decoder.decode(cached.decode("utf-8"))
            ]
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery("listAuditLogs"), {
                    "guild": self.id,
                    "range_start": start,
                    "range_end": end,
                    "authors": authors and len(authors) > 0 and authors or None,
                    "event_names": event_names and len(event_names) > 0 and event_names or None,
                    "limit": limit,
                    "page": page
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result) and resultExists(result, 1):
                    valkey.set(filter_key, encoder.encode(result[0]["result"]), 86400)
                    return [
                        AuditLog(item) for item in result[0]["result"]
                    ], result[1]["result"][0]["count"]
                else:
                    raise DatabaseError(result[0]["result"])
    
    async def get_banned_members(self):
        cached = valkey.get(f"db:banned_members:{self.id}")
        if cached:
            response = []
            for item in decoder.decode(cached.decode("utf-8")):
                response.append(ServerUser(item))
            return response
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery("getBannedMembers"), {"guild": self.id})
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    raw = result[0]["result"]
                    valkey.set(f"db:banned_members:{self.id}", encoder.encode(raw), 86400)
                    response = []
                    for item in raw:
                        response.append(ServerUser(item))
                    return response
                else:
                    raise DatabaseError(result[0]["result"])
    
    ## USERS ##
    
    async def fetch_or_create_member(self, user: guilded.Member):
        try:
            member = await self.fetch_member(user.id)
        except:
            new_perms: dict = self.settings.get("permissions", {})

            roles = user._role_ids
            if len(roles) == 0:
                roles = await user.fetch_role_ids()
            user_perms = UserPermissions()
            for id in roles:
                perms = new_perms.get(str(id))
                if perms:
                    user_perms += UserPermissions.from_string(perms)
            if user.id == user.server.owner_id:
                user_perms = UserPermissions.all()

            member = await self.create_member(
                user.id,
                str(user_perms),
                await user.award_xp(0),
                False,
                user_perms.can_access_dash
            )

        return member
    
    async def fetch_member(self, user_id: str):
        cached = valkey.get(f"db:server_user:{self.id}:{user_id}")
        if cached:
            return ServerUser(cached.decode("utf-8"))
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery("getGuildUser"), {"guild": self.id, "id": user_id})
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    raw = result[0]["result"][0]
                    valkey.set(f"db:server_user:{self.id}:{user_id}", encoder.encode(raw), 86400)
                    return ServerUser(raw)
                else:
                    raise DatabaseError(result[0]["result"])
    
    async def create_member(
        self,
        user_id: str,
        perms: str,
        xp: int,
        is_banned: bool,
        can_access_dash: bool,
    ):
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery("createGuildUser"), {
                    "guild": self.id,
                    "id": user_id,
                    "perms": perms,
                    "xp": xp,
                    "is_banned": is_banned,
                    "can_access_dash": can_access_dash,
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    raw = result[0]["result"][0]
                    valkey.set(f"db:server_user:{self.id}:{user_id}", encoder.encode(raw), 86400)
                    return ServerUser(raw)
                else:
                    raise DatabaseError(result[0]["result"])
    
    async def users_with_roles(self, roles: List[Union[str, int]]) -> List[str]:
        roles = str(hash(tuple(roles)))
        key = f"db:users_with_roles:{self.id}:{roles}"
        cached = valkey.get(key)
        if cached:
            return cached
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery("listUsersWithRole"), {
                    "guild": self.id,
                    "roles": roles
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    raw = [item["user_id"] for item in result[0]["result"]]
                    valkey.set(key, encoder.encode(raw), 900)
                    return raw
                else:
                    raise DatabaseError(result[0]["result"])

class ChannelConfigType(Enum):
    RSS = "RSS"

class ChannelConfig(DatabaseModel):
    def __init__(self, data: dict):
        self.guild_id: str = data["guild_id"]
        self.channel_id: str = data["channel_id"]
        self.type: ChannelConfigType = ChannelConfigType(data["type"])
        self.created_at: datetime = data["created"]
        
        self.extra_data: dict = {}
        for key, value in data.items():
            if not key in ["guild_id", "channel_id", "type", "created"]:
                self.extra_data[key] = value
    
    async def update(
        self,
        **kwargs
    ):
        if "guild_id" in kwargs:
            kwargs.pop("guild_id")
        if "channel_id" in kwargs:
            kwargs.pop("channel_id")
        if "type" in kwargs:
            kwargs.pop("type")
        if "created" in kwargs:
            kwargs.pop("created")

        async with DBConnection() as db:
            filtered_args = {}
            for key, value in kwargs.items():
                if value is None: continue
                filtered_args[key] = value
            try:
                response = await db.query(loadQuery("updateChannelConfig"), {
                    "id": self.id,
                    "payload": filtered_args
                })
            except Exception as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    for key, value in kwargs.items():
                        self.extra_data[key] = value
                        self.__raw[key] = value
                else:
                    raise DatabaseError(response[0]["result"])
    
    async def delete(self):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("deleteChannelConfig"), {"id": self.id})
            except Exception as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    pass
                else:
                    raise DatabaseError(response[0]["result"])

class RoleConfigType(Enum):
    AUTOROLE = "AUTOROLE"

class RoleConfig(DatabaseModel):
    def __init__(self, data: dict):
        self.guild_id: str = data["guild_id"]
        self.role_id: str = data["role_id"]
        self.type: RoleConfigType = RoleConfigType(data["type"])
        self.created_at: datetime = data["created"]

        self.extra_data: dict = {}
        for key, value in data.items():
            if not key in ["guild_id", "role_id", "type", "created"]:
                self.extra_data[key] = value
    
    async def update(
        self,
        **kwargs
    ):
        if "guild_id" in kwargs:
            kwargs.pop("guild_id")
        if "role_id" in kwargs:
            kwargs.pop("role_id")
        if "type" in kwargs:
            kwargs.pop("type")
        if "created" in kwargs:
            kwargs.pop("created")

        async with DBConnection() as db:
            filtered_args = {}
            for key, value in kwargs.items():
                if value is None: continue
                filtered_args[key] = value
            try:
                response = await db.query(loadQuery("updateRoleConfig"), {
                    "id": self.id,
                    "payload": filtered_args
                })
            except Exception as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    for key, value in kwargs.items():
                        self.extra_data[key] = value
                        self.__raw[key] = value
                else:
                    raise DatabaseError(response[0]["result"])
    
    async def delete(self):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("deleteRoleConfig"), {"id": self.id})
            except Exception as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    pass
                else:
                    raise DatabaseError(response[0]["result"])