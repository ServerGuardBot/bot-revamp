from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, DatabaseModel
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException

import base64
import io

class Image(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)
        
        self.source = data["source_url"]
        self.data = data["data"]
        self.expires = data["expires"]
    
    @property
    def bytes(self):
        mem = io.BytesIO(base64.b64decode(self.data))
        mem.seek(0)
        return mem