from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, statuses
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException

from .autorole import Autorole

async def get_scheduled_autoroles():
    try:
        autoroles = await statuses.get_expired_statuses(["autorole"])
    except DatabaseError as e:
        raise e
    else:
        return autoroles

async def schedule_autorole(server_id: str, user_id: str, autorole: str):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("scheduleAutorole"), {
                "guild_id": server_id,
                "user_id": user_id,
                "autorole": autorole
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                return statuses.Autorole(response[0]["result"])
            else:
                raise DatabaseError("An unknown issue occurred")

async def list_autoroles(server_id: str):
    cached = valkey.get(f"db:autoroles:{server_id}")
    if cached:
        return [Autorole(config) for config in decoder.decode(cached)]
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("listRoleConfigs"), {
                "guild": server_id,
                "type": "autorole"
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set(f"db:autoroles:{server_id}", encoder.encode(response[0]["result"]), 700)
                return [Autorole(config) for config in response[0]["result"]]
            else:
                raise DatabaseError("An unknown issue occurred")

async def get_autorole(id: str):
    cached = valkey.get(f"db:autorole:{id}")
    if cached:
        return Autorole(decoder.decode(cached))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getRoleConfig"), {
                "id": id,
                "type": "autorole"
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                return Autorole(response[0]["result"])
            else:
                raise NotFound("Autorole not found")

async def create_autorole(
    server_id: str,
    has_roles: list,
    has_all: bool,
    not_has_roles: list,
    not_has_all: bool,
    on_join: bool,
    delay_time: int
):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createRoleConfig"), {
                "guild": server_id,
                "type": "autorole",
                "has_roles": has_roles,
                "has_all": has_all,
                "not_has_roles": not_has_roles,
                "not_has_all": not_has_all,
                "on_join": on_join,
                "delay_time": delay_time
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                result = Autorole(response[0]["result"])
                valkey.set(f"db:autorole:{result.id}", encoder.encode(result), 700)
                return result
            else:
                raise DatabaseError("An unknown issue occurred")