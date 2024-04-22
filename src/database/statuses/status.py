from database import DBConnection, loadQuery, resultExists, DatabaseModel
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException

class UserStatus(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)

        self.guild_id = data["guild_id"]
        self.user_id = data["user_id"]
        self.type = data["type"]
        
        self.created_at = data["created"]
        self.ends_at = data["ends"]
    
    async def delete(self):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("removeStatus"), {
                    "id": self.id
                })
            except SurrealException as e:
                raise DatabaseError(str(e))

class Reminder(UserStatus):
    def __init__(self, data: dict):
        super().__init__(data)

        self.channel_id = data["channel_id"]
        self.message_id = data["message_id"]
        self.message = data["message"]

class Warning(UserStatus):
    def __init__(self, data: dict):
        super().__init__(data)

        self.issuer: str = data["issuer"]
        self.reason: str = data["reason"]

class TempBan(UserStatus):
    def __init__(self, data: dict):
        super().__init__(data)

        self.reason: str = data["reason"]