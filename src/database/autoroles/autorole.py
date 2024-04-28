from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException

from database.servers import RoleConfig, RoleConfigType

class Autorole(RoleConfig):
    def __init__(self, data: dict):
        super().__init__(data)
        
        self.has_roles: list = data["has_roles"]
        self.has_all: bool = data["has_all"]
        self.not_has_roles: list = data["not_has_roles"]
        self.not_has_all: bool = data["not_has_all"]
        
        self.on_join: bool = data["on_join"]
        self.delay_time: int = data.get("delay_time", 0)