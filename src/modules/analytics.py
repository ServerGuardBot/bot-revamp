from werkzeug.exceptions import InternalServerError
from quart import Quart, jsonify, request
from core.checks_api import authenticated
from guilded.ext import commands
from datetime import datetime

import database as db
import guilded

class Analytics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def register_routes(self, app: Quart):
        @app.route("/stats", methods=["GET"])
        async def GetStats():
            try:
                guilds = await db.servers.count_servers()
                if guilds:
                    guilds = guilds
                else:
                    guilds = 3713
            except Exception as e:
                print(f"Failed to get guild count: {str(e)}")
                raise InternalServerError(f"Failed to get guild count: {str(e)}")

            try:
                users = await db.users.count_users()
                if users:
                    users = users
                else:
                    users = 73045
            except Exception as e:
                print(f"Failed to get user count: {str(e)}")
                raise InternalServerError(f"Failed to get user count: {str(e)}")
            try:
                try:
                    verifications = await db.data.get("verifications")
                    if verifications:
                        verifications = verifications
                    else:
                        verifications = 2034
                except:
                    verifications = 2034
            except Exception as e:
                print(f"Failed to get verification count: {str(e)}")
                raise InternalServerError(f"Failed to get verification count: {str(e)}")
                
            return jsonify({
                "servers": guilds,
                "users": users,
                "verifications": verifications
            })

def setup(bot: commands.Bot):
    bot.add_cog(Analytics(bot))