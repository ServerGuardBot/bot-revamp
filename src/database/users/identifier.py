from database import DatabaseModel, DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException

class Identifier(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)

        self.connections = data.get("connections")
        self.vpn = data.get("use_vpn")
        self.hashed_ip = data.get("hashed_ip")
        self.browser_id = data.get("browser_id")
    
    async def update(
        self,
        connections: dict=None,
        vpn: bool=None,
        hashed_ip: str=None,
        browser_id: str=None
    ):
        async with DBConnection() as db:
            if connections:
                try:
                    await db.query(loadQuery("setUserConnections"), {
                        "id": self.id,
                        "connections": connections
                    })
                except SurrealException as e:
                    raise DatabaseError(e)
                else:
                    self.connections = connections
                    self.__raw["connections"] = connections
            if vpn != None and hashed_ip != None and browser_id != None:
                try:
                    await db.query(loadQuery("updateIdentifier"), {
                        "id": self.id,
                        "vpn": vpn,
                        "hashed_ip": hashed_ip,
                        "browser_id": browser_id
                    })
                except SurrealException as e:
                    raise DatabaseError(e)
                else:
                    self.vpn = vpn
                    self.hashed_ip = hashed_ip
                    self.browser_id = browser_id
                    self.__raw["uses_vpn"] = vpn
                    self.__raw["hashed_ip"] = hashed_ip
                    self.__raw["browser_id"] = browser_id
            
            if connections or (vpn != None and hashed_ip != None and browser_id != None):
                valkey.set(f"db:identifier:{self.id}", encoder.encode(self.__raw))