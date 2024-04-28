from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions, DatabaseModel
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException

class FeedPreset(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)

        self.url = data['url']
        self.name = data['name']
        self.description = data['description']
        self.extra_fields = data['extra_fields']
    
    async def update(
        self,
        url: str=None,
        name: str=None,
        description: str=None,
        extra_fields: dict=None
    ):
        async with DBConnection() as db:
            try:
                result = await db.query(
                    loadQuery("updateFeedPreset"),
                    {
                        "url": url,
                        "name": name,
                        "description": description,
                        "extra_fields": extra_fields,
                        "id": self.id
                    }
                )
            except SurrealException as e:
                raise DatabaseError(e.message)
            else:
                if url != None:
                    self.url = url
                    self.__raw['url'] = url
                if name != None:
                    self.name = name
                    self.__raw['name'] = name
                if description != None:
                    self.description = description
                    self.__raw['description'] = description
                if extra_fields != None:
                    self.extra_fields = extra_fields
                    self.__raw['extra_fields'] = extra_fields
                cached = valkey.get(f"db:feed_presets")
                if cached:
                    cached = decoder.decode(cached)
                    for item in cached:
                        if item["id"] == self.id:
                            cached.remove(item)
                            cached.append(self.__raw)
                            break
                    valkey.set("db:feed_presets", encoder.encode(cached), 86400)
                return self
    
    async def delete():
        async with DBConnection() as db:
            try:
                result = await db.query(
                    loadQuery("deleteFeedPreset"),
                    {
                        "id": self.id
                    }
                )
            except SurrealException as e:
                raise DatabaseError(e.message)
            else:
                cached = valkey.get(f"db:feed_presets")
                if cached:
                    cached = decoder.decode(cached)
                    for item in cached:
                        if item["id"] == self.id:
                            cached.remove(item)
                            break
                    valkey.set("db:feed_presets", encoder.encode(cached), 86400)