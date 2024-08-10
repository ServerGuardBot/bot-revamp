from core.checks_api import authenticated, has_permissions, dashboard_access, developer_only
from database.rss import FeedData, RSSFeed, FeedState, FeedPreset
from quart import Quart, jsonify, request
from markdownify import markdownify as md
from datetime import datetime, timedelta
from guilded.ext import commands, tasks
from core.embeds import EMBED_STANDARD
from time import mktime, struct_time
from core.cors import apply_cors
from modules.image import Image
from base import BOT_VERSION
from typing import Union

import database as db
import feedparser
import guilded
import config
import re

USER_AGENT = config.USER_AGENT.format(BOT_VERSION, "RSS")

WEBHOOK_REGEX = r"^https?://media\.guilded\.gg/webhooks/[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}/[a-zA-Z0-9]{86}$"

def sort_entries(t: list):
    return sorted(t, key=lambda x: x.get("published_parsed"))

def sanitize_data(t):
    if isinstance(t, dict):
        result = {}
        for k, v in t.items():
            result[k] = sanitize_data(v)
        return result
    elif isinstance(t, list):
        result = []
        for item in t:
            result.append(sanitize_data(item))
        return result
    else:
        if isinstance(t, tuple):
            return list(t)
        elif isinstance(t, struct_time):
            return list(tuple(t))
        else:
            return t

class RSS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        self.update_feeds.start()
    
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
        if datetime.now() + timedelta(hours=1) > next_update:
            next_update = datetime.now() + timedelta(hours=1)
        return next_update
    
    def get_feed_url(self, feed: RSSFeed, preset: FeedPreset = None):
        if preset:
            return preset.url.format(**feed.extra_fields)
        else:
            return feed.extra_fields.get("url")
    
    async def post_feed(self, source: Union[guilded.ChatChannel, guilded.Webhook], entry: dict, ping_role: str=None):
        image: Image = self.bot.get_cog("Image")
        timestamp = entry.get("published_parsed", entry.get("created_parsed"))
        em = EMBED_STANDARD(
            title=md(entry.get("title", "Unnamed Item")),
            url=entry.get("link", guilded.Embed.Empty),
            description=cutoff(
                md(entry.get("description", "No description")),
                200,
                guilded.utils.link(
                    link=entry.get("link", guilded.Embed.Empty),
                    title="*[Summary too long]*"
                )
            ),
            timestamp=datetime.fromtimestamp(mktime(tuple(timestamp)))
        )

        if entry.get("author_detail"):
            em.set_author(
                name=md(entry.get("author_detail").get("name", "Unnamed Author")),
                url=entry.get("author_detail").get("href", em.Empty),
                icon_url=entry.get("author_detail").get("icon", em.Empty)
            )
        elif entry.get("author"):
            em.set_author(name=entry.get("author", "Unnamed Author"))
        
        if entry.get("publisher_detail"):
            url = entry["publisher_detail"].get("href")
            publisher = md(entry["publisher_detail"].get("name", "Unknown Publisher"))
            em.add_field(
                name="Publisher",
                value=url and guilded.utils.link(link=url, title=publisher) or publisher,
            )
        elif entry.get("publisher"):
            em.add_field(name="Publisher", value=md(entry["publisher"]))
        
        if entry.get("image") and entry["image"].get("href"):
            image_url = await image.proxy_url(entry["image"]["href"], "20m")
            if image_url and config.DATABASE_DB != "dev":
                em.set_image(url=image_url)
            else:
                # Fallback to the source image if the proxy fails
                em.set_image(url=entry["image"]["href"])
        elif entry.get("media_thumbnail") and len(entry["media_thumbnail"]) > 0:
            image_url = await image.proxy_url(entry["media_thumbnail"][0]["url"], "20m")
            if image_url and config.DATABASE_DB != "dev":
                em.set_image(url=image_url)
            else:
                # Fallback to the source image if the proxy fails
                em.set_image(url=entry["media_thumbnail"][0]["url"])
        
        if entry.get("license"):
            em.add_field(name="License", value=guilded.utils.link(
                link=entry["license"],
                title="[Link]"
            ), inline=False)
        
        if entry.get("tags"):
            tags = []
            for tag in entry["tags"]:
                if len(tags) >= 10: break
                if tag.get("label"):
                    tags.append(tag["label"])
            if len(tags) > 0:
                em.add_field(name="Tags", value=", ".join([f"`{md(tag)}`" for tag in tags]), inline=False)
        
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
            print(f"Registering feed: {url}")
            try:
                results = feedparser.parse(url, agent=USER_AGENT)
                if results["status"] != 200:
                    return False
                modified = results.get("modified_parsed")
                if modified:
                    modified = datetime.fromtimestamp(mktime(modified))
                else:
                    modified = datetime.now()
                feed = await db.rss.create_feed_data(
                    url,
                    md(results["feed"].get("title", "Unnamed Feed")),
                    md(results["feed"].get("subtitle", results["feed"].get("info", ""))),
                    results.get("etag", ""),
                    modified,
                    self.calc_next_update(results),
                    sanitize_data(sort_entries(results["entries"]))
                )
            except Exception as e:
                print(f"Failed to register feed: {type(e).__name__} - {e}")
                return False
            else:
                print(f"Registered feed: {url}")
                return True, feed
        except Exception as e:
            print(f"Failed to check if feed exists: {type(e).__name__} - {e}")
            return False
        else:
            print(f"Registered feed: {url}")
            return True, feed
    
    async def scan_feed(self, feed: RSSFeed, data: dict):
        if feed.webhook:
            source = guilded.Webhook.from_url(
                url = feed.webhook,
                session=self.bot.http.session,
                auth_token=self.bot.http.token
            )
        else:
            source = await self.bot.getch_channel(feed.channel_id)
        known = []
        for entry in data:
            if len(feed.filters) > 0:
                indexable = [
                    entry.get("content", ""),
                    entry.get("summary", ""),
                    entry.get("title", ""),
                    ", ".join([tag.get("label", "") for tag in entry.get("tags", [])])
                ]
                contains_filter = False
                for item in indexable:
                    if any([f in item for f in feed.filters]):
                        contains_filter = True
                        break
                if not contains_filter:
                    continue
            if entry["id"] not in feed.known:
                print(f"Will try posting {entry['id']} to feed {str(source)}")
                try:
                    await self.post_feed(source, entry, feed.ping_role)
                except guilded.TooManyRequests:
                    print("Rate limited, willl postpone rest of scanning...")
                    break
                except Exception as e:
                    print(f"Failed to post feed: {type(e).__name__} - {e}")
                else:
                    print(f"Posted {entry['id']} to source {source.id} <{str(type(source))}>")
                    # Only append this if we successfully posted the entry
                    known.append(entry["id"])
            else:
                # Append this to the known list so we don't post it again
                known.append(entry["id"])
        await feed.update(known=known, last_updated=datetime.now())
    
    @tasks.loop(minutes=1)
    async def update_feeds(self):
        print("Updating scheduled feeds...")
        try:
            feed_presets = await db.rss.get_feed_presets()
        except Exception as e:
            print(f"Failed to load feed presets: {type(e).__name__} - {e}")
            return
        else:
            print(f"Found {len(feed_presets)} feed presets...")
        
        presets_to_update = []
        urls_to_update = []
        
        def get_preset_url(preset: str):
            for p in feed_presets:
                if p.name == preset:
                    return p.url
            return "{url}"

        try:
            print("Updating scheduled feed presets...")
            to_update = await db.rss.get_scheduled_feeds()
        except Exception as e:
            print(f"Failed to load scheduled feeds: {type(e).__name__} - {e}")
        else:
            for feed in to_update:
                urls_to_update.append(feed.url)
            
            latest = datetime.now() - timedelta(minutes=5)
            for feed in to_update:
                print(f"Updating feed data {feed.url}...")
                last_modified = datetime.now()
                if feed.data:
                    last_modified = feed.data[-1]["published_parsed"]
                results = feedparser.parse(
                    feed.url,
                    agent=USER_AGENT,
                    etag=feed.etag,
                    modified=last_modified
                )
                if results["status"] == 200:
                    print(f"Successfully parsed feed {feed.url}")
                    try:
                        await feed.update(
                            name=md(results["feed"].get("title", "Unnamed Feed")),
                            description=md(results["feed"].get("subtitle", results["feed"].get("info", ""))),
                            etag=results.get("etag"),
                            last_modified=datetime.fromtimestamp(mktime(results["entries"][-1]["published_parsed"])),
                            next_update=self.calc_next_update(results),
                            data=sanitize_data(sort_entries(results["entries"]))
                        )
                    except Exception as e:
                        print(f"Failed to update feed (200) {feed.url}: {type(e).__name__} - {e}")
                elif results["status"] == 302:
                    # Update the URL in the DB
                    print(f'Feed at "{feed.url}" has been relocated, updating URL...')
                    try:
                        await feed.update(
                            name=md(results["feed"].get("title", "Unnamed Feed")),
                            description=md(results["feed"].get("subtitle", results["feed"].get("info", ""))),
                            etag=results.get("etag"),
                            last_modified=datetime.fromtimestamp(mktime(results["modified_parsed"])) if results.get("modified_parsed") else datetime.now(),
                            next_update=self.calc_next_update(results),
                            data=sanitize_data(results["entries"]),
                            url=results["href"]
                        )
                    except Exception as e:
                        print(f"Failed to update feed (302) {feed.url}: {type(e).__name__} - {e}")
                elif results["status"] == 304:
                    print(f'Feed at "{feed.url}" has not changed, no need to hit DB...')
                elif results["status"] == 410:
                    # Delete the feed's data and mark it as dead in the DB
                    print(f'Feed at "{feed.url}" is dead, marking...')
                    try:
                        await feed.update(
                            state=FeedState.DEAD,
                            data={}
                        )
                    except Exception as e:
                        print(f"Failed to update feed (410) {feed.url}: {type(e).__name__} - {e}")
                if results["status"] != 410:
                    print(f"Feed at {feed.url} is not dead, adding to list...")
                    if feed.last_modified:
                        latest = max(latest, feed.last_modified)
                    if feed.url not in urls_to_update:
                        urls_to_update.append(feed.url)
            try:
                guilds = self.bot.servers
                if len(guilds) == 0:
                    guilds = await self.bot.fetch_servers()
                to_scan = await db.rss.get_updatable_feeds(
                    [guild.id for guild in guilds]
                )
            except Exception as e:
                print(f"Failed to load updatable feeds: {type(e).__name__} - {e}")
            else:
                for item in to_scan:
                    try:
                        preset = None
                        url = ""
                        
                        for feed_preset in feed_presets:
                            if feed_preset.name == item.preset:
                                preset = feed_preset
                                break
                        
                        if preset is None and item.extra_fields.get("url"):
                            url = item.extra_fields["url"]
                        elif preset is not None:
                            url = preset.url.format(**item.extra_fields)
                        else:
                            print(f"No preset or URL found for feed {item.id}, skipping...")
                            # This item is invalid and should be skipped
                            continue
                        
                        print(f"Will try getting feed data for {url}...")
                        feed_data = await db.rss.fetch_feed_data(
                            url=url
                        )
                    except db.NotFound:
                        print(f"Feed data for {url} not found, registering...")
                        success, feed_data = await self.register_feed(url)
                        if not success:
                            continue
                    except:
                        continue
                    print(f"Will try scanning feed {item.channel_id or item.webhook}/{feed_data.id}")
                    try:
                        await self.scan_feed(item, feed_data.data)
                    except Exception as e:
                        print(f"Failed to scan feed {item.channel_id or item.webhook}/{feed_data.id}: {type(e).__name__} - {e}")
    
    def register_routes(self, app: Quart):
        @app.route("/servers/<string:server_id>/rss")
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        @has_permissions(manage_feeds=True)
        async def GetRSSFeeds(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except db.NotFound:
                return jsonify({"status": "error", "error": "Server not found."}), 404
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    feeds = await db.rss.list_rss_feeds(server_id)
                    feed_presets = await db.rss.get_feed_presets()
                    
                    urls = []
                    mapped_urls = {}
                    for feed in feeds:
                        preset: db.rss.FeedPreset = None
                        for feed_preset in feed_presets:
                            if feed_preset.id == feed.preset:
                                preset = preset
                                break
                        if preset is None:
                            if feed.extra_fields.get("url"):
                                urls.append(feed.extra_fields["url"])
                                mapped_urls[feed.id] = feed.extra_fields["url"]
                        else:
                            mapped_urls[feed.id] = preset.url.format(**feed.extra_fields)
                            urls.append(
                                preset.url.format(**feed.extra_fields)
                            )
                    
                    feed_datas = await db.rss.list_feed_datas(
                        urls=urls
                    )
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while fetching RSS feeds."}), 500
                else:
                    def get_feed_data(id: str, provide_dict: bool=True):
                        for data in feed_datas:
                            data: db.rss.FeedData
                            if data.url == mapped_urls.get(id, None):
                                if provide_dict:
                                    return {
                                        "name": data.name,
                                        "description": data.description,
                                        "state": data.state.value
                                    }
                                else:
                                    return data
                    return jsonify({"status": "success", "feeds": [
                        {
                            "id": feed.id,
                            "channel": feed.channel_id,
                            "webhook": feed.webhook,
                            "preset": feed.preset,
                            "extra_fields": feed.extra_fields,
                            "ping_role": feed.ping_role,
                            "data": get_feed_data(feed.id),
                            
                            "name": get_feed_data(feed.id, False).name,
                            "url": get_feed_data(feed.id, False).url
                        } for feed in feeds
                    ], "presets": [
                        {
                            "id": preset.id,
                            "name": preset.name,
                            "url": preset.url,
                            "extra_fields": preset.extra_fields
                        } for preset in feed_presets
                    ]})
        
        @app.route("/servers/<string:server_id>/rss", methods=["POST"])
        @apply_cors(allow_methods=["POST"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        @has_permissions(manage_feeds=True)
        async def CreateRSSFeed(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 400
            else:
                try:
                    data = await request.get_json()
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while parsing request data."}), 400
                else:
                    if data.get("preset") is None \
                        or (data.get("webhook") is None \
                        and data.get("channel") is None):
                        return jsonify({"status": "error", "error": "Missing required fields."}), 400
                    if data.get("filters") is not None:
                        for item in data["filters"]:
                            if not isinstance(item, str):
                                return jsonify({"status": "error", "error": "Invalid filters."}), 400
                    if data.get("webhook") is not None and str.rstrip(data["webhook"]) != "":
                        if not re.match(WEBHOOK_REGEX, data["webhook"]):
                            return jsonify({"status": "error", "error": "Invalid webhook URL."}), 400
                    if data.get("channel") is not None and str.rstrip(data["channel"]) != "":
                        server = self.bot.get_server(server_id)
                        try:
                            channel = await server.getch_channel(data["channel"])
                        except:
                            return jsonify({"status": "error", "error": "Invalid channel"}), 400
                        else:
                            if channel is None:
                                return jsonify({"status": "error", "error": "Invalid channel"}), 400
                    try:
                        if data["preset"] == "custom":
                            preset = db.rss.FeedPreset({
                                "url": "{url}",
                                "name": "Custom Feed",
                                "description": "Input any valid RSS feed ID",
                                "extra_fields": ["url"]
                            })
                        else:
                            preset = await db.rss.fetch_feed_preset(data["preset"])
                    except:
                        return jsonify({"status": "error", "error": "Could not validate preset"})
                    else:
                        if data.get("extra_fields"):
                            for key, value in data["extra_fields"].items():
                                if key not in preset.extra_fields:
                                    return jsonify({"status": "error", "error": "Invalid extra field."}), 400
                                if not isinstance(value, str):
                                    return jsonify({"status": "error", "error": "Invalid extra field."}), 400
                                if len(value) > 512:
                                    return jsonify({"status": "error", "error": "Invalid extra field."}), 400
                            for key in preset.extra_fields:
                                if key not in data["extra_fields"]:
                                    return jsonify({"status": "error", "error": "Missing extra field(s)"}), 400
                        else:
                            if len(preset.extra_fields) > 0:
                                return jsonify({"status": "error", "error": "Missing extra field(s)"}), 400
                        
                        # Validate that the URL will lead to a valid RSS feed
                        try:
                            url = preset.url.format(**data.get("extra_fields", {}))
                            feed_data = feedparser.parse(url)
                            if feed_data["bozo"] == "1":
                                return jsonify({"status": "error", "error": "Malformed feed data."}), 400
                            if feed_data["status"] not in [200, 301, 302]:
                                return jsonify({"status": "error", "error": "Invalid feed."}), 400
                        except:
                            return jsonify({"status": "error", "error": "Invalid feed."}), 400
                        
                        try:
                            result = await db.rss.create_rss_feed(
                                server_id,
                                data.get("preset", ""),
                                data.get("webhook", ""),
                                data.get("channel", ""),
                                data.get("ping_role", "0"),
                                data.get("extra_fields", {}),
                                data.get("filters", []),
                            )
                        except Exception as e:
                            if request.is_developer:
                                import traceback
                                return jsonify({
                                    "status": "error",
                                    "error": "Something went wrong while creating feed.",
                                    "debug": {
                                        "error": "{}: {}".format(str(e.__class__), str(e)),
                                        "trace": traceback.format_exc()
                                    }
                                }), 400
                            return jsonify({"status": "error", "error": "Something went wrong while creating feed."}), 400
                        else:
                            try:
                                registered, feed_info = await self.register_feed(url)
                            except:
                                pass
                            
                            if registered:
                                return jsonify({"status": "success", "feed": {
                                    "id": result.id,
                                    "preset": result.preset,
                                    "channel": result.channel_id,
                                    "webhook": result.webhook,
                                    "extra_fields": result.extra_fields,
                                    "ping_role": result.ping_role,
                                    
                                    "name": feed_info.name,
                                    "url": feed_info.url,
                                }})
                            else:
                                return jsonify({"status": "success", "feed": {
                                    "id": result.id,
                                    "preset": result.preset,
                                    "channel": result.channel_id,
                                    "webhook": result.webhook,
                                    "extra_fields": result.extra_fields,
                                    "ping_role": result.ping_role,
                                }})
        
        @app.route("/servers/<string:server_id>/rss/<string:feed_id>", methods=["PATCH"])
        @apply_cors(allow_methods=["PATCH", "DELETE"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        @has_permissions(manage_feeds=True)
        async def UpdateRSSFeed(server_id: str, feed_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
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
                    except Exception as e:
                        print("{}: {}".format(
                            str(e.__class__),
                            str(e)
                        ))
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
                        
                        _preset = data.get("preset", feed.preset)
                        try:
                            if _preset == "custom":
                                preset = db.rss.FeedPreset({
                                    "url": "{url}",
                                    "name": "Custom Feed",
                                    "description": "Input any valid RSS feed ID",
                                    "extra_fields": ["url"]
                                })
                            else:
                                preset = await db.rss.fetch_feed_preset(_preset)
                        except:
                            return jsonify({"status": "error", "error": "Could not validate preset"})
                        
                        if data.get("extra_fields"):
                            for key, value in data["extra_fields"].items():
                                if key not in preset.extra_fields:
                                    return jsonify({"status": "error", "error": "Invalid extra field."}), 400
                                if not isinstance(value, str):
                                    return jsonify({"status": "error", "error": "Invalid extra field."}), 400
                                if len(value) > 512:
                                    return jsonify({"status": "error", "error": "Invalid extra field."}), 400
                            for key in preset.extra_fields:
                                if key not in data["extra_fields"]:
                                    return jsonify({"status": "error", "error": "Missing extra field(s)"}), 400
                        else:
                            if len(preset.extra_fields) > 0:
                                return jsonify({"status": "error", "error": "Missing extra field(s)"}), 400
                        
                        try:
                            previous_url = preset.url.format(**feed.extra_fields)
                            previous_preset = feed.preset
                            previous_fields = feed.extra_fields
                            await feed.update(
                                **filtered_payload
                            )
                            
                            has_changed = False
                            if feed.preset != previous_preset:
                                has_changed = True
                            for key, value in feed.extra_fields.items():
                                if value != previous_fields.get(key):
                                    has_changed = True
                            for key, value in previous_fields.items():
                                if key not in feed.extra_fields:
                                    has_changed = True
                            
                            if has_changed:
                                if feed.preset != previous_preset:
                                    try:
                                        if feed.preset == "custom":
                                            preset = db.rss.FeedPreset({
                                                "url": "{url}",
                                                "name": "Custom Feed",
                                                "description": "Input any valid RSS feed ID",
                                                "extra_fields": ["url"]
                                            })
                                        else:
                                            preset = await db.rss.fetch_feed_preset(feed.preset)
                                    except:
                                        pass
                                    else:
                                        registered, feed_info = await self.register_feed(preset.url.format(**feed.extra_fields))
                                        
                                        if registered:
                                            return jsonify({
                                                "status": "success",
                                                "feed": {
                                                    "id": feed.id,
                                                    "preset": feed.preset,
                                                    "channel": feed.channel_id,
                                                    "webhook": feed.webhook,
                                                    "extra_fields": feed.extra_fields,
                                                    "ping_role": feed.ping_role,
                                                    
                                                    "name": feed_info.name.format(**feed.extra_fields),
                                                    "url": feed_info.url.format(**feed.extra_fields),
                                                }
                                            })
                                        else:
                                            return jsonify({
                                                "status": "success",
                                                "feed": {
                                                    "id": feed.id,
                                                    "preset": feed.preset,
                                                    "channel": feed.channel_id,
                                                    "webhook": feed.webhook,
                                                    "extra_fields": feed.extra_fields,
                                                    "ping_role": feed.ping_role,
                                                }
                                            })
                                else:
                                    registered, feed_info = await self.register_feed(preset.url.format(**feed.extra_fields))
                                    
                                    if registered:
                                        return jsonify({
                                            "status": "success",
                                            "feed": {
                                                "id": feed.id,
                                                "preset": feed.preset,
                                                "channel": feed.channel_id,
                                                "webhook": feed.webhook,
                                                "extra_fields": feed.extra_fields,
                                                "ping_role": feed.ping_role,
                                                
                                                "name": feed_info.name.format(**feed.extra_fields),
                                                "url": feed_info.url.format(**feed.extra_fields),
                                            }
                                        })
                                    else:
                                        return jsonify({
                                            "status": "success",
                                            "feed": {
                                                "id": feed.id,
                                                "preset": feed.preset,
                                                "channel": feed.channel_id,
                                                "webhook": feed.webhook,
                                                "extra_fields": feed.extra_fields,
                                                "ping_role": feed.ping_role,
                                            }
                                        })
                        except Exception as e:
                            print("{}: {}".format(
                                str(e.__class__),
                                str(e)
                            ))
                            return jsonify({"status": "error", "error": "Something went wrong while updating feed."}), 500
                        else:
                            return jsonify({
                                "status": "success",
                                "feed": {
                                    "id": feed.id,
                                    "preset": feed.preset,
                                    "channel": feed.channel_id,
                                    "webhook": feed.webhook,
                                    "extra_fields": feed.extra_fields,
                                    "ping_role": feed.ping_role,
                                }
                            })
        
        @app.route("/servers/<string:server_id>/rss/<string:feed_id>", methods=["DELETE"])
        @apply_cors(allow_methods=["DELETE"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        @has_permissions(manage_feeds=True)
        async def DeleteRSSFeed(server_id: str, feed_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
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
                    except Exception as e:
                        print("{}: {}".format(
                            str(e.__class__),
                            str(e)
                        ))
                        return jsonify({"status": "error", "error": "Something went wrong while deleting feed."}), 500
                    else:
                        return jsonify({"status": "success"})
        
        @app.route("/rss/preset", methods=["GET"])
        @apply_cors(allow_methods=["GET"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        async def ListRSSPresets():
            try:
                presets = await db.rss.get_feed_presets()
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching RSS presets."}), 500
            else:
                return jsonify({"status": "success", "presets": [
                    {
                        "id": preset.id,
                        "name": preset.name,
                        "url": preset.url,
                        "description": preset.description,
                        "extra_fields": preset.extra_fields
                    } for preset in presets
                ]})
        
        @app.route("/rss/preset", methods=["POST"])
        @apply_cors(allow_methods=["POST"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
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
                        "extra_fields": result.extra_fields
                    }})
        
        @app.route("/rss/preset/<string:preset_id>", methods=["PATCH"])
        @apply_cors(allow_methods=["PATCH"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
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
                            "extra_fields": preset.extra_fields
                        }})
        
        @app.route("/rss/preset/<string:preset_id>", methods=["DELETE"])
        @apply_cors(allow_methods=["DELETE"], allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
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