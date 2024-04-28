from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions, DatabaseModel
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException
from enum import Enum

class FeedState(Enum):
    ALIVE = "ALIVE"
    DEAD = "DEAD"

class FeedData(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)
        
        self.state = FeedState(data["state"].upper())
        
        self.url = data["url"]
        self.name = data["name"]
        self.description = data["description"]
        
        self.etag = data.get("etag")
        self.last_modified = data["last_updated"]
        self.next_update = data["next_update"]
        
        self.data = data["data"]
    
    def update(
        self,
        url: str=None,
        name: str=None,
        description: str=None,
        etag: str=None,
        last_modified: str=None,
        next_update: str=None,
        data: dict=None,
        state: FeedState=None
    ):
        async with DBConnection() as db:
            try:
                result = await db.query(
                    loadQuery("updateFeedData"),
                    {
                        "id": self.id,
                        "payload": {
                            "url": url,
                            "name": name,
                            "description": description,
                            "etag": etag,
                            "last_updated": last_modified,
                            "next_update": next_update,
                            "data": data,
                            "state": state.value if state else None
                        }
                    }
                )
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    old_url = self.url
                    if url != None:
                        self.url = url
                        self.__raw["url"] = url
                    if name != None:
                        self.name = name
                        self.__raw["name"] = name
                    if description != None:
                        self.description = description
                        self.__raw["description"] = description
                    if etag != None:
                        self.etag = etag
                        self.__raw["etag"] = etag
                    if last_modified != None:
                        self.last_modified = last_modified
                        self.__raw["last_updated"] = last_modified
                    if next_update != None:
                        self.next_update = next_update
                        self.__raw["next_update"] = next_update
                    if data != None:
                        self.data = data
                        self.__raw["data"] = data
                    if state != None:
                        self.state = state
                        self.__raw["state"] = state.value
                    
                    if old_url != self.url:
                        valkey.delete(f"db:feed_data:url:{old_url}")
                    valkey.set(f"db:feed_data:url:{self.url}", encoder.encode(self.__raw), 86400)
                    valkey.set(f"db:feed_data:id:{self.id}", encoder.encode(self.__raw), 86400)
                else:
                    raise DatabaseError("No changes were made")