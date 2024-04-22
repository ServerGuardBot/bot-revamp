from quart import Quart, jsonify, request
from markdownify import markdownify as md
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

USER_AGENT = config.USER_AGENT.format(BOT_VERSION, "RSS")

class RSS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def post_feed(self, source: Union[guilded.ChatChannel, guilded.Webhook], entry: dict):
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
            timestamp=mktime(timestamp)
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
        
        if isinstance(source, guilded.ChatChannel):
            await source.send(embed=em)
        else:
            source: guilded.Webhook
            await source.send(embed=em)
    
    async def register_feed(self, url: str):
        try:
            feed = None # TODO: Replace with db function once implemented
        except db.NotFound:
            # TODO: One implemented, fetch the feed and then create it
            return False
        except:
            return False
        else:
            return True, feed
    
    @tasks.loop(seconds=60)
    async def update_feeds(self):
        try:
            to_update = [] # TODO: Replace with db function once implemented
        except:
            pass
        else:
            for feed in to_update:
                results = feedparser.parse(
                    feed.url,
                    agent=USER_AGENT,
                    etag=feed.etag,
                    modified=feed.updated_at
                )
                if results.status == 200:
                    try:
                        pass # TODO: Replace with db function once implemented
                    except:
                        pass
                elif results.status == 304:
                    # Update the URL in the DB
                    try:
                        pass # TODO: Replace with db function once implemented
                    except:
                        pass
                elif results.status == 410:
                    # Delete the feed's data and mark it as dead in the DB
                    try:
                        pass # TODO: Replace with db function once implemented
                    except:
                        pass

def setup(bot: commands.Bot):
    bot.add_cog(RSS(bot))

def cutoff(message: str, length: int, replacement: str):
    if len(message) > length:
        return replacement
    return message