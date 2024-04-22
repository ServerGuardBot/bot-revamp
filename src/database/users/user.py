from database import DatabaseModel, DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException

from .identifier import Identifier

class User(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)

        self.name = data['name']
        self.avatar = data['avatar']
        self.language = data['language']
        
        self.created_at = data['created']
        self.updated_at = data['updated']
    
    async def get_identifier(self):
        import database
        return await database.users.fetch_identifier(self.id)

    async def set_language(self, lang: str):
        async with DBConnection() as db:
            try:
                await db.query(loadQuery("setUserLanguage"), {
                    "id": self.id,
                    "lang": lang
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                self.__raw['language'] = lang
                self.language = lang
                valkey.set(f"db:user{self.id}", encoder.encode(self.__raw), 86400)