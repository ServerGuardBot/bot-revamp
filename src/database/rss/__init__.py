from database import DBConnection, loadQuery, resultExists, allOk, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException
from datetime import datetime
from typing import List

from .feed_data import FeedData, FeedState
from ..servers import ChannelConfigType
from .preset import FeedPreset
from .feeds import RSSFeed

async def create_feed_data(
    url: str,
    name: str,
    description: str,
    etag: str,
    last_updated: datetime=datetime.now(),
    next_update: datetime=datetime.now(),
    data: dict=None
):
    if last_updated is None:
        last_updated = datetime.now()
    if next_update is None:
        next_update = datetime.now()
    if isinstance(data, (dict, list)):
        data = encoder.encode(data)
    async with DBConnection() as db:
        try:
            result = await db.query(
                loadQuery("createFeedData"),
                {
                    "url": url,
                    "name": name,
                    "description": description,
                    "etag": etag,
                    "last_updated": int(last_updated.timestamp()),
                    "next_update": int(next_update.timestamp()),
                    "data": data
                }
            )
        except SurrealException as e:
            import traceback
            raise DatabaseError(f"{str(e)} - {traceback.format_exc()}")
        else:
            if resultExists(result):
                item = FeedData(result[0]["result"][0])
                valkey.set(f"db:feed_data:id:{item.id}", encoder.encode(item.raw), 86400)
                valkey.set(f"db:feed_data:url:{item.url}", encoder.encode(item.raw), 86400)
                return item
            else:
                raise DatabaseError(f"Failed to create feed data: {result[0]['result']}")

async def list_feed_datas(
    ids: list=[],
    urls: list=[],
):
    if ids is None and urls is None:
        raise ValueError("Must specify either ids or urls.")
    key = str(hash(tuple(ids) + tuple(urls)))
    cached = valkey.get(f"db:feed_datas:{key}")
    if cached:
        return [FeedData(config) for config in decoder.decode(cached.decode("utf-8"))]
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("listFeedDatas"), {
                "ids": ids,
                "urls": urls
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if allOk(response):
                valkey.set(f"db:feed_datas:{key}", encoder.encode(response[0]["result"]), 86400)
                return [FeedData(config) for config in response[0]["result"]]
            else:
                raise DatabaseError("Failed to list feed datas.")

async def fetch_feed_data(
    id: str=None,
    url: str=None
):
    if id is not None and url is not None:
        raise ValueError("Cannot specify both id and url.")
    if id is not None:
        cached = valkey.get(f"db:feed_data:id:{id}")
        if cached:
            return FeedData(decoder.decode(cached.decode("utf-8")))
    else:
        cached = valkey.get(f"db:feed_data:url:{url}")
        if cached:
            return FeedData(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getFeedData"), {
                "id": id,
                "url": url
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                if id is not None:
                    valkey.set(f"db:feed_data:id:{id}", encoder.encode(response[0]["result"][0]), 86400)
                else:
                    valkey.set(f"db:feed_data:url:{url}", encoder.encode(response[0]["result"][0]), 86400)
                return FeedData(response[0]["result"][0])
            else:
                raise NotFound("Feed data not found.")

async def list_rss_feeds(server_id: str) -> List[RSSFeed]:
    cached = valkey.get(f"db:rss_feeds:{server_id}")
    if cached:
        return [RSSFeed(config) for config in decoder.decode(cached.decode("utf-8"))]
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("listChannelConfigs"), {
                "guild": server_id,
                "type": ChannelConfigType.RSS.value
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if allOk(response):
                valkey.set(f"db:rss_feeds:{server_id}", encoder.encode(response[0]["result"]), 700)
                return [RSSFeed(config) for config in response[0]["result"]]
            else:
                raise DatabaseError("Failed to list feeds.")

async def create_rss_feed(
    server_id: str,
    preset: str,
    webhook: str="",
    channel: str="",
    ping_role: str="0",
    extra_fields: dict={},
    filters: List[str]=[]
):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createChannelConfig"), {
                "payload": {
                    "guild_id": server_id,
                    "channel_id": channel,
                    "type": ChannelConfigType.RSS.value,
                    "preset": preset,
                    "webhook": webhook,
                    "ping_role": ping_role,
                    "extra_fields": extra_fields,
                    "filters": filters
                }
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set(f"db:rss_feeds:{server_id}", encoder.encode(response[0]["result"]), 700)
                return RSSFeed(response[0]["result"][0])
            else:
                raise DatabaseError(f"Failed to create feed: {response[0]['result']}")

async def fetch_rss_feed(id: str):
    cached = valkey.get(f"db:rss_feeds:{id}")
    if cached:
        return RSSFeed(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getChannelConfig"), {
                "id": id,
                "type": ChannelConfigType.RSS.value
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set(f"db:rss_feeds:{id}", encoder.encode(response[0]["result"][0]), 700)
                return RSSFeed(response[0]["result"][0])
            else:
                raise NotFound("Feed not found.")

async def get_scheduled_feeds() -> List[FeedData]:
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getScheduledFeeds"))
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                return [FeedData(raw) for raw in response[0]["result"]]
            else:
                print(f"No scheduled feeds found: {response[0]['result']}")
                return []

async def get_updatable_feeds(
    guilds: List[str],
) -> List[RSSFeed]:
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getUpdatableFeeds"), {
                "guilds": guilds
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                return [RSSFeed(raw) for raw in response[0]["result"]]
            else:
                print(f"No updatable feeds found: {response[0]['result']}")
                return []

async def get_feed_presets() -> List[FeedPreset]:
    cached = valkey.get("db:feed_presets")
    if cached:
        return [FeedPreset(config) for config in decoder.decode(cached.decode("utf-8"))]
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("listFeedPresets"))
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                valkey.set("db:feed_presets", encoder.encode(response[0]["result"]), 86400)
                presets = [FeedPreset(raw) for raw in response[0]["result"]]
                for preset in presets:
                    valkey.set(f"db:feed_presets:{preset.id}", encoder.encode(preset.raw), 86400)
                return presets
            else:
                return []

async def fetch_feed_preset(id: str) -> FeedPreset:
    cached = valkey.get(f"db:feed_presets:{id}")
    if cached:
        return FeedPreset(decoder.decode(cached.decode("utf-8")))
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getFeedPreset"), {
                "id": id
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                preset = FeedPreset(response[0]["result"][0])
                valkey.set(f"db:feed_presets:{id}", encoder.encode(preset.raw), 86400)
                return preset
            else:
                raise NotFound("Feed preset not found.")

async def create_feed_preset(
    name: str,
    url: str,
    description: str,
    extra_fields: dict
):
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("createFeedPreset"), {
                "name": name,
                "description": description,
                "url": url,
                "extra_fields": extra_fields
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                cached = valkey.get("db:feed_presets")
                if cached:
                    cached = decoder.decode(cached)
                    cached.append(response[0]["result"][0])
                    valkey.set("db:feed_presets", encoder.encode(cached), 86400)
                preset = FeedPreset(response[0]["result"][0])
                valkey.set(f"db:feed_presets:{preset.id}", encoder.encode(preset.raw), 86400)
                return preset
            else:
                raise DatabaseError("Failed to create feed preset.")