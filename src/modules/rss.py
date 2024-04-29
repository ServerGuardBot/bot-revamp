from core.checks_api import authenticated, has_permissions, dashboard_access, developer_only
from database.rss import FeedData, RSSFeed, FeedState, FeedPreset
from quart import Quart, jsonify, request
from markdownify import markdownify as md
from datetime import datetime, timedelta
from guilded.ext import commands, tasks
from core.embeds import EMBED_STANDARD
from quart_cors import route_cors
from modules.image import Image
from base import BOT_VERSION
from typing import Union
from time import mktime

import database as db
import feedparser
import guilded
import config
import re

USER_AGENT = config.USER_AGENT.format(BOT_VERSION, "RSS")

WEBHOOK_REGEX = r"(?:https?:\/\/)?media\.(guilded\.com\/webhooks\/)([a-zA-Z0-9_-]+)\/([a-zA-Z0-9_-]+)"

class RSS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def calc_next_update(self, feed: dict):
        next_update = datetime.now()
        if feed.get("ttl"):
            next_update += timedelta(minutes=feed["ttl"])
        else:
            next_update += timedelta(minutes=60)

        try:
            if feed["feed"].get("skiphours") and isinstance(feed["feed"]["skiphours"], list):
                skip_hours = feed["feed"]["skiphours"]
                for hour in skip_hours:
                    if hour == next_update.hour:
                        next_update += timedelta(hours=1)
            
            if feed["feed"].get("skipdays") and isinstance(feed["feed"]["skiphours"], list):
                skip_days = feed["feed"]["skipdays"]
                for day in skip_days:
                    if day == next_update.weekday():
                        next_update += timedelta(days=1)
        except:
            pass
    
    def get_feed_url(self, feed: RSSFeed, preset: FeedPreset = None):
        if preset:
            return preset.url.format(feed.extra_data)
        else:
            return feed.extra_data.get("url")
    
    async def post_feed(self, source: Union[guilded.ChatChannel, guilded.Webhook], entry: dict, ping_role: str=None):
        image: Image = self.bot.get_cog("Image")
        timestamp = entry.get("published_parsed", entry.get("created_parsed"))
        em = EMBED_STANDARD(
            title=md(entry.get("title", "Unnamed Item")),
            url=entry.get("link", "https://example.com"),
            description=cutoff(
                md(entry.get("description", "No description")),
                200,
                guilded.utils.link(entry.get("link", "https://example.com"), "*[Summary too long]*")
            ),
            timestamp=datetime.fromtimestamp(mktime(timestamp))
        )

        if entry.get("author_detail"):
            em.set_author(
                name=entry.get("author_detail").get("name", "Unnamed Author"),
                url=entry.get("author_detail").get("href", "https://example.com"),
                icon_url=entry.get("author_detail").get("icon", "")
            )
        elif entry.get("author"):
            em.set_author(name=entry.get("author", "Unnamed Author"))
        
        if entry.get("publisher_detail"):
            em.add_field(
                name="Publisher",
                value=guilded.utils.link(entry["publisher_detail"].get("href", "https://example.com"), entry["publisher_detail"].get("name", "Unknown Publisher")),
            )
        
        if entry.get("image") and entry["image"].get("href"):
            image_url = await image.proxy_url(entry["image"]["href"], "20m")
            if image_url:
                em.set_image(url=image_url)
            else:
                # Fallback to the source image if the proxy fails
                em.set_image(url=entry["image"]["href"])
        elif entry.get("media_thumbnail") and len(entry["media_thumbnail"]) > 0:
            image_url = await image.proxy_url(entry["media_thumbnail"][0]["url"], "20m")
            if image_url:
                em.set_image(url=image_url)
            else:
                # Fallback to the source image if the proxy fails
                em.set_image(url=entry["media_thumbnail"][0]["url"])
        
        if entry.get("license"):
            em.add_field(name="License", value=guilded.utils.link(entry["license"], "[Link]"), inline=False)
        
        if entry.get("tags"):
            tags = []
            for tag in entry["tags"]:
                if len(tags) >= 10: break
                if tag.get("label"):
                    tags.append(tag["label"])
            if len(tags) > 0:
                em.add_field(name="Tags", value=", ".join([f"`{tag}`" for tag in tags]), inline=False)
        
        if ping_role:
            await source.send(
                embed=em,
                content=f"<@{ping_role}>"
            )
        else:
            await source.send(embed=em)
    
    async def register_feed(self, url: str):
        try:
            feed = await db.rss.fetch_feed_data(url)
        except db.NotFound:
            results = feedparser.parse(url, agent=USER_AGENT)
            if results.status != 200:
                return False
            modified = results.get("modified_parsed")
            if modified:
                modified = datetime.fromtimestamp(mktime(modified))
            feed = await db.rss.create_feed_data(
                url,
                md(results["feed"].get("title", "Unnamed Feed")),
                md(results["feed"].get("subtitle", results["feed"].get("info", ""))),
                results.get("etag"),
                modified,
                self.calc_next_update(results)
            )
        except:
            return False
        else:
            return True, feed
    
    async def scan_feed(self, feed: RSSFeed, data: dict):
        source = await self.bot.getch_channel(feed.channel_id)
        if feed.webhook:
            source = await guilded.Webhook.from_url(
                feed.webhook,
                session=self.bot.http.session,
                auth_token=self.bot.http.token
            )
        known = []
        for entry in data["entries"]:
            if entry["id"] not in feed.known:
                try:
                    await self.post_feed(source, entry, feed.ping_role)
                except:
                    pass
                else:
                    # Only append this if we successfully posted the entry
                    known.append(entry["id"])
            else:
                # Append this to the known list so we don't post it again
                known.append(entry["id"])
        await feed.update(known=known)
    
    @tasks.loop(seconds=60)
    async def update_feeds(self):
        try:
            feed_presets = await db.rss.get_feed_presets()
        except:
            print("Failed to load feed presets")
            return
        
        presets_to_update = []

        try:
            to_update = await db.rss.get_scheduled_feeds()
        except:
            pass
        else:
            latest = datetime.now() - timedelta(minutes=5)
            for feed in to_update:
                feed: FeedData
                results = feedparser.parse(
                    feed.url,
                    agent=USER_AGENT,
                    etag=feed.etag,
                    modified=feed.updated_at
                )
                if results.status == 200:
                    try:
                        await feed.update(
                            name=md(results["feed"].get("title", "Unnamed Feed")),
                            description=md(results["feed"].get("subtitle", results["feed"].get("info", ""))),
                            etag=results.get("etag"),
                            last_modified=datetime.fromtimestamp(mktime(results["modified_parsed"])) if results.get("modified_parsed") else datetime.now(),
                            next_update=self.calc_next_update(results),
                            data=results
                        )
                    except:
                        pass
                elif results.status == 304:
                    # Update the URL in the DB
                    print(f'Feed at "{feed.url}" has been relocated, updating URL...')
                    try:
                        await feed.update(
                            name=md(results["feed"].get("title", "Unnamed Feed")),
                            description=md(results["feed"].get("subtitle", results["feed"].get("info", ""))),
                            etag=results.get("etag"),
                            last_modified=datetime.fromtimestamp(mktime(results["modified_parsed"])) if results.get("modified_parsed") else datetime.now(),
                            next_update=self.calc_next_update(results),
                            data=results,
                            url=results["href"]
                        )
                    except:
                        pass
                elif results.status == 410:
                    # Delete the feed's data and mark it as dead in the DB
                    print(f'Feed at "{feed.url}" is dead, marking...')
                    try:
                        await feed.update(
                            state=FeedState.DEAD,
                            data={}
                        )
                    except:
                        pass
                if results.status != 410:
                    if feed.last_modified:
                        latest = max(latest, feed.last_modified)
                    for preset in feed_presets:
                        if len(preset.extra_fields.keys()) > 0:
                            continue
                        if preset.id == feed.preset:
                            presets_to_update.append(preset)
            try:
                to_scan = await db.rss.get_updatable_feeds(
                    [item.url for item in to_update],
                    presets_to_update,
                    latest
                )
            except:
                for item in to_scan:
                    try:
                        feed_data = await db.rss.fetch_feed_data(
                            url=item.url
                        )
                    except:
                        pass
                    else:
                        await self.scan_feed(item, feed_data.data)
    
    def register_routes(self, app: Quart):
        @app.route("/servers/<string:server_id>/rss")
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def GetRSSFeeds(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(server_id)
            except db.NotFound:
                return jsonify({"status": "error", "error": "Server not found."}), 404
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    feeds = await db.rss.list_rss_feeds(server_id)
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while fetching RSS feeds."}), 500
                else:
                    return jsonify({"status": "success", "feeds": [
                        {
                            "channel": feed.channel_id,
                            "webhook": feed.webhook,
                            "preset": feed.preset,
                            "extra_fields": feed.extra_data
                        } for feed in feeds
                    ]})
        
        @app.route("/servers/<string:server_id>/rss", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def CreateRSSFeed(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(server_id)
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    data = await request.get_json()
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while parsing request data."}), 500
                else:
                    if data.get("preset") is None \
                        or (data.get("webhook") is None \
                        and data.get("channel") is None):
                        return jsonify({"status": "error", "error": "Missing required fields."}), 400
                    if data.get("webhook") is not None:
                        if not re.match(WEBHOOK_REGEX, data["webhook"]):
                            return jsonify({"status": "error", "error": "Invalid webhook URL."}), 400
                    try:
                        result = await db.rss.create_rss_feed(
                            server_id,
                            data.get("preset", ""),
                            data.get("webhook", ""),
                            data.get("channel", ""),
                            data.get("ping_role", "0"),
                            data.get("extra_fields", {}),
                        )
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while creating autorole."}), 500
                    else:
                        return jsonify({"status": "success", "feed": {
                            "id": result.id,
                            "preset": result.preset,
                            "channel": result.channel_id,
                            "webhook": result.webhook,
                            "extra_fields": result.extra_data,
                            "ping_role": result.ping_role
                        }})
        
        @app.route("/servers/<string:server_id>/rss", methods=["PATCH"])
        @route_cors(allow_headers=["content-type"], allow_methods=["PATCH"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def UpdateRSSFeed(server_id: str, id: str):
            try:
                guild = await db.servers.fetch_or_create_server(server_id)
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    data = await request.get_json()
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while parsing request data."}), 500
                else:
                    if data.get("webhook") is not None:
                        if not re.match(WEBHOOK_REGEX, data["webhook"]):
                            return jsonify({"status": "error", "error": "Invalid webhook URL."}), 400
                    try:
                        feed = await db.rss.fetch_rss_feed(
                            feed_id
                        )
                    except db.NotFound:
                        return jsonify({"status": "error", "error": "Feed not found."}), 404
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while fetching feed."}), 500
                    else:
                        if feed.guild_id != server_id:
                            return jsonify({"status": "error", "error": "Feed not found."}), 404
                        filtered_payload = {}
                        for key, value in data.items():
                            if not key in ["channel", "webhook", "ping_role", "extra_fields", "preset"]: continue
                            if value is not None:
                                filtered_payload[key] = value
                        if len(filtered_payload) == 0:
                            return jsonify({"status": "error", "error": "No fields to update."}), 400
                        try:
                            await feed.update(
                                **filtered_payload
                            )
                        except:
                            return jsonify({"status": "error", "error": "Something went wrong while updating feed."}), 500
        
        @app.route("/servers/<string:server_id>/rss", methods=["DELETE"])
        @route_cors(allow_headers=["content-type"], allow_methods=["DELETE"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def DeleteRSSFeed(server_id: str, id: str):
            try:
                guild = await db.servers.fetch_or_create_server(server_id)
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    feed = await db.rss.fetch_rss_feed(
                        feed_id
                    )
                except db.NotFound:
                    return jsonify({"status": "error", "error": "Feed not found."}), 404
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while fetching feed."}), 500
                else:
                    if feed.guild_id != server_id:
                        return jsonify({"status": "error", "error": "Feed not found."}), 404
                    try:
                        await feed.delete()
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while deleting feed."}), 500
                    else:
                        return jsonify({"status": "success"})
        
        @app.route("/rss/preset", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @developer_only
        async def CreateRSSPreset():
            try:
                data = await request.get_json()
            except:
                return jsonify({"status": "error", "error": "Something went wrong while parsing request data."}), 500
            else:
                if data.get("name") is None \
                    or data.get("url") is None \
                    or data.get("description") is None:
                    return jsonify({"status": "error", "error": "Missing required fields."}), 400
                try:
                    result = await db.rss.create_feed_preset(
                        data["name"],
                        data["url"],
                        data["description"],
                        data.get("extra_fields", {})
                    )
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while creating RSS preset."}), 500
                else:
                    return jsonify({"status": "success", "preset": {
                        "id": result.id,
                        "name": result.name,
                        "url": result.url,
                        "description": result.description,
                        "extra_fields": result.extra_data
                    }})
        
        @app.route("/rss/preset/<string:preset_id>", methods=["PATCH"])
        @route_cors(allow_headers=["content-type"], allow_methods=["PATCH"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @developer_only
        async def UpdateRSSPreset(preset_id: str):
            try:
                preset = await db.rss.fetch_feed_preset(
                    preset_id
                )
            except db.NotFound:
                return jsonify({"status": "error", "error": "Preset not found."}), 404
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching preset."}), 500
            else:
                try:
                    data = await request.get_json()
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while parsing request data."}), 500
                else:
                    filtered_payload = {}
                    for key, value in data.items():
                        if not key in ["name", "url", "description", "extra_fields"]: continue
                        if value is not None:
                            filtered_payload[key] = value
                    if len(filtered_payload) == 0:
                        return jsonify({"status": "error", "error": "No fields to update."}), 400
                    try:
                        await preset.update(
                            **filtered_payload
                        )
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while updating preset."}), 500
                    else:
                        return jsonify({"status": "success", "preset": {
                            "id": preset.id,
                            "name": preset.name,
                            "url": preset.url,
                            "description": preset.description,
                            "extra_fields": preset.extra_data
                        }})
        
        @app.route("/rss/preset/<string:preset_id>", methods=["DELETE"])
        @route_cors(allow_headers=["content-type"], allow_methods=["DELETE"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @developer_only
        async def DeleteRSSPreset(preset_id: str):
            try:
                preset = await db.rss.fetch_feed_preset(
                    preset_id
                )
            except db.NotFound:
                return jsonify({"status": "error", "error": "Preset not found."}), 404
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching preset."}), 500
            else:
                try:
                    await preset.delete()
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while deleting preset."}), 500
                else:
                    return jsonify({"status": "success"})

def setup(bot: commands.Bot):
    bot.add_cog(RSS(bot))

def cutoff(message: str, length: int, replacement: str):
    if len(message) > length:
        return replacement
    return message