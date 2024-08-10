from database import DBConnection, loadQuery, allOk, resultExists, valkey, encoder, decoder, UserPermissions, DatabaseModel
from database.types import to_datetime, to_string
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException
from datetime import datetime
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
        
        self.etag = to_string(data.get("etag"))
        self.last_modified = to_datetime(data["last_updated"])
        self.next_update = to_datetime(data["next_update"])
        
        if isinstance(data["data"], str):
            self.data = decoder.decode(data["data"])
        else:
            self.data = data["data"]
    
    @property
    def updated_at(self):
        return self.last_modified
    
    async def update(
        self,
        url: str=None,
        name: str=None,
        description: str=None,
        etag: str=None,
        last_modified: datetime=None,
        next_update: datetime=None,
        data: dict=None,
        state: FeedState=None
    ):
        _last_modified = None
        _next_update = None
        if last_modified:
            _last_modified = int(last_modified.replace(tzinfo=None).timestamp())
        if next_update:
            _next_update = int(next_update.replace(tzinfo=None).timestamp())
        if isinstance(data, (dict, list)):
            data = encoder.encode(data)
        if etag is None:
            etag = ""
        filtered_payload = {}
        for key in ["url","name","description","etag","data","state"]:
            if locals()[key] != None:
                if key == "state":
                    filtered_payload[key] = state.value
                else:
                    filtered_payload[key] = locals()[key]
        async with DBConnection() as db:
            try:
                result = await db.query(
                    loadQuery("updateFeedData"),
                    {
                        "id": self.id,
                        "payload": filtered_payload,
                        "last_updated": _last_modified,
                        "next_update": _next_update,
                    }
                )
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if allOk(result):
                    old_url = self.url
                    if url != None:
                        self.url = url
                        self.raw["url"] = url
                    if name != None:
                        self.name = name
                        self.raw["name"] = name
                    if description != None:
                        self.description = description
                        self.raw["description"] = description
                    if etag != None:
                        self.etag = etag
                        self.raw["etag"] = etag
                    if last_modified != None:
                        self.last_modified = to_datetime(last_modified)
                        self.raw["last_updated"] = last_modified
                    if next_update != None:
                        self.next_update = to_datetime(next_update)
                        self.raw["next_update"] = next_update
                    if data != None:
                        self.data = data
                        self.raw["data"] = data
                    if state != None:
                        self.state = state
                        self.raw["state"] = state.value
                    
                    if old_url != self.url:
                        valkey.delete(f"db:feed_data:url:{old_url}")
                    valkey.set(f"db:feed_data:url:{self.url}", encoder.encode(self.raw), 86400)
                    valkey.set(f"db:feed_data:id:{self.id}", encoder.encode(self.raw), 86400)
                else:
                    raise DatabaseError(f"Not all results were ok: {result}")