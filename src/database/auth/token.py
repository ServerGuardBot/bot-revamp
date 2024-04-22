from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions, DatabaseModel
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException

class UserToken(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)
        
        self.type = data["type"]
        self.created_at = data["created"]
    
    async def delete(self):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("deleteToken"), {
                    "id": self.id
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                valkey.delete(f"db:user_token:{self.id}")

class LoginToken(UserToken):
    def __init__(self, data: dict):
        super().__init__(data)

        self.user_id = data.get("user_id")
        
        self.location = data["location"]
        self.browser = data["browser"]
        self.platform = data["platform"]
        self.lock = data["lock"]
    
    async def update(self, user_id: str):
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("updateLoginToken"), {
                    "id": self.id,
                    "user_id": user_id
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.__raw["user_id"] = user_id
                valkey.set(f"db:user_token:{self.id}", encoder.encode(self.__raw), 60)

class VerifyToken(UserToken):
    def __init__(self, data: dict):
        super().__init__(data)

        self.user_id = data["user_id"]
        self.guild_id = data["guild_id"]
    
    @property
    def server_id(self):
        return self.guild_id