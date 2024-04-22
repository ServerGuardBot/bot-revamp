from werkzeug.exceptions import InternalServerError
from quart import Quart, jsonify, request
from core.checks_api import authenticated
from quart_cors import route_cors
from guilded.ext import commands
from datetime import datetime

import database as db
import guilded

class Analytics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def register_routes(self, app: Quart):
        @app.route("/stats", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin="*")
        async def GetStats():
            try:
                guilds = await db.servers.count_servers()
                if guilds:
                    guilds = guilds.score
                else:
                    guilds = 3713
            except Exception as e:
                print(f"Failed to get guild count: {str(e)}")
                raise InternalServerError

            try:
                users = await db.users.count_users()
                if users:
                    users = users.score
                else:
                    users = 73045
            except Exception as e:
                print(f"Failed to get user count: {str(e)}")
                raise InternalServerError
            try:
                verifications = await db.analytics.get_analytics_item("verifications", datetime.now())
                if verifications:
                    verifications = verifications.score
                else:
                    verifications = 2034
            except Exception as e:
                return jsonify({
                    "error": str(e)
                }), 500
                
            return jsonify({
                "servers": guilds,
                "users": users,
                "verifications": verifications
            })

def setup(bot: commands.Bot):
    bot.add_cog(Analytics(bot))