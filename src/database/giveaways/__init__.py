from database import DBConnection, loadQuery, resultExists, allOk, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException
from typing import List

from .giveaway import Giveaway, GiveawayState

async def host(
    guild_id: str,
    hosted_by: str,
    message_id: str,
    channel_id: str,
    prize: str,
    duration: int,
    winners: int
) -> Giveaway:
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery('createGiveaway'), {
                "guild": guild_id,
                "host": hosted_by,
                "message": message_id,
                "channel": channel_id,
                "prize": prize,
                "duration": duration,
                "winners": winners
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                result = Giveaway(response[0]['result'][0])
                valkey.set(f"db:giveaway:{result.id}", encoder.encode(result.raw), 86400)
                return result
            else:
                raise DatabaseError(f"Failed to create giveaway: {response[0]['result'][0]}")

async def list_giveaways(guild_id: str, page: int=1) -> tuple[List[Giveaway], int]:
    cached = valkey.get(f"db:giveaways:{guild_id}:{page}")
    if cached:
        cached = decoder.decode(cached.decode("utf-8"))
        return \
            [Giveaway(giveaway) for giveaway in cached[0]], \
            cached[1]
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery('listGiveaways'), {
                "guild": guild_id,
                "page": page - 1
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if allOk(response):
                valkey.set(f"db:giveaways:{guild_id}:{page}", encoder.encode([
                    response[0]["result"][0],
                    response[1]["result"][0]["count"]
                ]), 60)
                return \
                    [Giveaway(giveaway) for giveaway in response[0]['result'][0]], \
                    response[1]['result'][0]["count"]
            else:
                raise DatabaseError(f"Failed to list giveaways: {response[0]['result'][0]}")

async def fetch_giveaway(guild_id: str, id: str=None, message_id: str=None):
    assert id is None and message_id is None, "You must specify either id or message_id"
    if id is not None:
        cached = valkey.get(f"db:giveaway:{id}")
        if cached:
            return decoder.decode(cached.decode("utf-8"))
    else:
        cached = valkey.get(f"db:giveaway_message:{guild_id}:{message_id}")
        if cached:
            return decoder.decode(cached.decode("utf-8"))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery('fetchGiveaway'), {
                "guild": guild_id,
                "id": id,
                "message": message_id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                result = Giveaway(response[0]['result'][0])
                if id is not None:
                    valkey.set(f"db:giveaway:{id}", encoder.encode(result.raw), 86400)
                else:
                    valkey.set(f"db:giveaway_message:{guild_id}:{message_id}", encoder.encode(result.raw), 86400)
                return result
            else:
                raise NotFound(f"Giveaway not found: {response[0]['result'][0]}")