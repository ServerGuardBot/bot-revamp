from database import DatabaseModel, DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException

class AnalyticsItem(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)
        
        self.key = data["key"]
        self.date = data["date"]
        self.score = data["score"]