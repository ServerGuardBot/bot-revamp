from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException
from datetime import datetime

from .item import AnalyticsItem

async def get_analytics_item(key: str, date: datetime) -> AnalyticsItem:
    cached = valkey.get(f"db:analytics:{key}:{date.isoformat()}")
    if cached:
        return AnalyticsItem(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getAnalyticsItem"), {
                "key": key,
                "date": int(date.timestamp())
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set(f"db:analytics:{key}:{date.isoformat()}", encoder.encode(response["result"][0]), 30)
                return AnalyticsItem(response["result"][0])
            else:
                raise NotFound