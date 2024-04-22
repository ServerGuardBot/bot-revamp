from quart import Quart, jsonify, request, send_file
from werkzeug.exceptions import NotFound
from guilded.ext import commands, tasks
from quart_cors import route_cors
from datetime import timedelta
from base import BOT_VERSION

import database as db
import requests
import guilded
import config
import base64
import io

USER_AGENT = config.USER_AGENT.format(BOT_VERSION, "Image Proxy")

class ImageStoreError(Exception):
    pass

class Image(commands.Cog):
    def __int__(self, bot: commands.Bot):
        self.bot = bot
        
        self.cleanup_images.start()
    
    @tasks.loop(seconds=1)
    async def cleanup_images(self):
        return await db.proxy.cleanup_images()
    
    async def store_bytes(
            self,
            image_bytes: bytes,
            expires: str="1d",
            source_url: str="",
        ):
        return await db.proxy.store_image(source_url, image_bytes, expires)
    
    async def proxy_url(
        self,
        url: str,
        expires: str="1d",
    ):
        existing_image = await db.proxy.get_image(source=url)
        if existing_image:
            return f"{config.API_SITE}/resource/ext/{existing_image.id}"

        download = requests.get(url,
            headers={
                "User-Agent": USER_AGENT,
            }
        )
        if download.ok:
            image = await self.store_bytes(download.content, expires, url)
            return f"{config.API_SITE}/resource/ext/{image.id}"
    
    def register_routes(self, app: Quart):
        @app.route("/resource/ext/<string:id>", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=["*"])
        async def GetExtResource(id: str):
            try:
                image = await db.proxy.get_image(id=id)
            except db.NotFound:
                raise NotFound
            else:
                return await send_file(image.bytes, mimetype="image/png", as_attachment=True, attachment_filename=f"{id}.png")

def setup(bot: commands.Bot):
    bot.add_cog(Image(bot))