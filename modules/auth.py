from core.checks_api import authenticated, dashboard_access, unauthenticated
from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from database import DBConnection, loadQuery, resultExists
from core.emotes import EMOTE_VERIFICATION_TICK
from core.images import IMAGE_DEFAULT_AVATAR
from quart import Quart, jsonify, request
from datetime import datetime, timedelta
from quart_cors import route_cors
from guilded.ext import commands
from guilded.http import Route

import hashlib
import guilded
import base64
import config
import os

REFRESH_TOKEN_EXPIRATION = timedelta(days=7)
LOGIN_TOKEN_EXPIRATION = timedelta(hours=1)

def b64_no_padding(str: str):
    return str.rstrip("=")

def b64_padding(str: str):
    return str + "=" * (4 - (len(str) % 4)) if len(str) % 4 != 0 else str

class LoginToken:
    def __init__(self, type: str, user_id: str, created: datetime=None):
        self.type = type
        self.user_id = user_id
        if created:
            self.created = created
        else:
            self.created = datetime.now()
        
        if self.type == "user":
            self.valid = datetime.now() < self.created + LOGIN_TOKEN_EXPIRATION
        elif self.type == "refresh":
            self.valid = datetime.now() < self.created + REFRESH_TOKEN_EXPIRATION
    
    def __str__(self):
        try:
            type = b64_no_padding(base64.urlsafe_b64encode(bytes(self.type, 'utf-8')).decode("utf-8"))
            user_id = b64_no_padding(base64.urlsafe_b64encode(bytes(self.user_id, 'utf-8')).decode("utf-8"))
            created = b64_no_padding(base64.urlsafe_b64encode(bytes(str(self.created), 'utf-8')).decode("utf-8"))
            sig = hashlib.sha256(bytes(f'{type}.{user_id}.{created}', 'utf-8')).hexdigest()
            return f"{type}.{user_id}.{created}.{sig}"
        except Exception as e:
            print(e)
            return ""
    
    @classmethod
    def from_token(cls, token: str):
        type, user_id, created, sig = token.split(".")
        if hashlib.sha256(bytes(f'{type}.{user_id}.{created}', 'utf-8')).hexdigest() != sig:
            return None
        return cls(base64.urlsafe_b64decode(b64_padding(type)).decode("utf-8"), base64.urlsafe_b64decode(b64_padding(user_id)).decode("utf-8"))

class Auth(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.user_tokens = {}
    
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        message = event.message
        if message.channel_id == config.LOGIN_CHANNEL_ID:
            if message.author.bot: return
            await message.delete()
            async with DBConnection() as db:
                response = await db.query(loadQuery("getToken"), {"id": message.content})
                async def failed():
                    await message.reply(embed=EMBED_DENIED(
                        title="Failure",
                        description=f"{message.author.mention}, Please submit a valid login code here, and remember not to post anything here that others tell you to!"
                    ), delete_after=10, private=True)
                if resultExists(response):
                    token = response[0]["result"][0]
                    if token["type"] != "login":
                        await failed()
                        return
                    if token.get("user_id"):
                        await failed()
                        return
                    login_message = await message.reply(embed=EMBED_STANDARD(
                        title="Verify Login",
                        description=f"Hey {message.author.mention}! Are you trying to log in from **{token.get('location', 'Unknown')}** on **{token.get('browser', 'Unknown Browser')} {token.get('platform', 'Unidentified Platform')}?** If so, please click the :white_check_mark: below!"
                    ), delete_after=60, private=True)
                    self.user_tokens[login_message.id] = {
                        "token": message.content,
                        "user": message.author_id
                    }
                    await login_message.add_reaction(guilded.utils.Object(EMOTE_VERIFICATION_TICK))
                else:
                    await failed()
    
    @commands.Cog.listener()
    async def on_message_reaction_add(self, event: guilded.MessageReactionAddEvent):
        if event.message.channel_id != config.LOGIN_CHANNEL_ID: return
        if event.message_id in self.user_tokens:
            data = self.user_tokens[event.message_id]
            if event.user_id != data["user"]: return
            async with DBConnection() as db:
                response = await db.query(loadQuery("getToken"), {"id": data["token"]})
                if resultExists(response):
                    token = response[0]["result"][0]
                    if token["type"] != "login":
                        return
                    response2 = await db.query(loadQuery("updateLoginToken"), {
                        "id": data["token"],
                        "user": data["user"],
                    })
                    print(response2)
                    if response2[0]["status"] == "OK":
                        await event.message.channel.send(embed=EMBED_SUCCESS(
                            title="Success",
                            description=f"<@{event.user_id}>, You should now be logged in on your browser. If you closed the login page before this then you will have to login again."
                        ), delete_after=10, private=True)
    
    def register_routes(self, app: Quart):
        @app.route("/login/<string:lock>/<string:token>", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=config.ORIGIN_SITE)
        @unauthenticated
        async def GetLoginState(lock: str, token: str):
            async with DBConnection() as db:
                response = await db.query(loadQuery("getToken"), {
                    "id": token
                })
                if resultExists(response):
                    data: dict = response[0]["result"][0]
                    if data["type"] != "login" or data["lock"] != lock:
                        return jsonify({"status": "error", "message": "Invalid token"}, status=400)
                    if data.get("user"):
                        loginToken = LoginToken("user", data["user"])
                        refreshToken = LoginToken("refresh", data["user"])
                        res = jsonify({
                            "status": "ok",
                            "state": 1 # Authorized
                        })
                        res.set_cookie("session", str(loginToken), expires=datetime.now() + LOGIN_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE)
                        res.set_cookie("refresh", str(refreshToken), expires=datetime.now() + REFRESH_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE)
                        await db.query(loadQuery("deleteToken"), {
                            "id": token
                        })
                        return res
                    else:
                        return jsonify({
                            "status": "ok",
                            "state": 0 # Not yet authorized
                        })
                else:
                    return jsonify({"status": "error", "message": "Invalid or expired token"}, status=404)
        
        @app.route("/login", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=config.ORIGIN_SITE)
        @unauthenticated
        async def CreateLoginToken():
            async with DBConnection() as db:
                lock = hashlib.sha256(os.urandom(32)).hexdigest()
                response = await db.query(loadQuery("createLoginToken"), {
                    "type": "login",
                    "lock": lock,
                    "location": "test",
                    "browser": "test",
                    "platform": "test"
                })
                if response[0]["status"] == "OK":
                    return jsonify({
                        "status": "ok",
                        "token": response[0]["result"][0]["id"].split(":")[1],
                        "lock": lock,
                    })
                else:
                    return jsonify({"status": "error"}, status=500)
        
        @app.route("/login", methods=["DELETE"])
        @route_cors(allow_headers=["content-type"], allow_methods=["DELETE"], allow_origin=config.ORIGIN_SITE)
        @unauthenticated
        async def CancelLoginToken():
            post_data: dict = await request.get_json()
            if post_data is None:
                return jsonify({"status": "error", "message": "Invalid request"}), 400
            if post_data.get("token") is None:
                return jsonify({"status": "error", "message": "Invalid request"}), 400
            async with DBConnection() as db:
                response = await db.query(loadQuery("getToken"), {
                    "id": post_data["token"]
                })
                if resultExists(response):
                    data = response[0]["result"][0]
                    if data["type"] != "login" or data["lock"] != post_data["lock"]:
                        return jsonify({"status": "error", "message": "Invalid token"}), 400
                    await db.query(loadQuery("deleteToken"), {
                        "id": post_data["token"]
                    })
                    return jsonify({"status": "ok"})
                else:
                    return jsonify({"status": "error", "message": "Invalid or expired token"}), 404
        
        @app.route("/logout", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=config.ORIGIN_SITE)
        async def Logout():
            cookies = request.cookies
            sessionCookie = cookies.get("session")
            refreshCookie = cookies.get("refresh")

            if sessionCookie and refreshCookie:
                sessionToken = LoginToken.from_token(sessionCookie)
                refreshToken = LoginToken.from_token(refreshCookie)

                if not sessionToken or not refreshToken:
                    return jsonify({"status": "error", "message": "Not authorized"}, status=401)
                if sessionToken.type != "user" or refreshToken.type != "refresh":
                    return jsonify({"status": "error", "message": "Invalid session or refresh token"}, status=400)
                async with DBConnection() as db:
                    blResponse = await db.query(loadQuery("getBlacklistedToken"), {
                        "id": refreshCookie,
                    })
                    if resultExists(blResponse):
                        return jsonify({"status": "error", "message": "Invalid refresh token"}, status=400)
                    response = await db.query(loadQuery("blacklistRefreshToken"), {
                        "id": refreshCookie,
                        "expires": (refreshToken.created + REFRESH_TOKEN_EXPIRATION).timestamp()
                    })

                    if response[0]["status"] == "OK":
                        res = jsonify({"status": "ok"})
                        res.set_cookie("session", "", expires=0)
                        res.set_cookie("refresh", "", expires=0)
                    else:
                        return jsonify({"status": "error", "message": "Failed to blacklist refresh token"}, status=500)
            return jsonify({"status": "error", "message": "Not authorized"}, status=401)
        
        @app.route("/refresh", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=config.ORIGIN_SITE)
        async def Refresh():
            cookies = request.cookies
            refreshCookie = cookies.get("refresh")

            if refreshCookie:
                refreshToken = LoginToken.from_token(refreshCookie)

                if (not refreshToken) or refreshToken.type != "refresh":
                    return jsonify({"status": "error", "message": "Invalid refresh token"}, status=400)
                async with DBConnection() as db:
                    blResponse = await db.query(loadQuery("getBlacklistedToken"), {
                        "id": refreshCookie,
                    })
                    if resultExists(blResponse):
                        return jsonify({"status": "error", "message": "Invalid refresh token"}, status=400)
                    response = await db.query(loadQuery("blacklistRefreshToken"), {
                        "id": refreshCookie,
                        "expires": (refreshToken.created + REFRESH_TOKEN_EXPIRATION).timestamp()
                    })

                    if response[0]["status"] == "OK":
                        res = jsonify({"status": "ok"})
                        new_refresh = LoginToken("refresh", refreshToken.user_id)
                        new_session = LoginToken("user", refreshToken.user_id)
                        res.set_cookie("session", str(new_session), max_age=LOGIN_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE)
                        res.set_cookie("refresh", str(new_refresh), max_age=REFRESH_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE)
                        return res, 200
                    else:
                        return jsonify({"status": "error", "message": "Failed to blacklist refresh token"}, status=500)
            return jsonify({"status": "error", "message": "Not authorized"}, status=401)
        
        @app.route("/servers", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=config.ORIGIN_SITE)
        @authenticated
        async def GetServers():
            userId = request.authenticated_user
            bot_servers = self.bot.servers
            servers = {}
            async with DBConnection() as db:
                for server in bot_servers:
                    user = None
                    try:
                        user = server.get_member(userId)
                    except:
                        pass
                    if user:
                        response = await db.query(loadQuery("getGuildUser"), {
                            "guild": server.id,
                            "id": userId
                        })
                        if resultExists(response):
                            data = response[0]["result"][0]
                            if data["access"]:
                                servers[server.id] = {
                                    "name": server.name,
                                    "avatar": server.avatar.url if server.avatar else IMAGE_DEFAULT_AVATAR,
                                    "banner": server.banner.url if server.banner else None,
                                    "members": server.member_count,
                                }
            return jsonify({"status": "ok", "servers": servers})
        
        @app.route("/servers/<string:server_id>")
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=config.ORIGIN_SITE)
        @authenticated
        @dashboard_access
        async def ServerOverview(server_id: str):
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("getGuild"), {
                        "id": server_id
                    })
                except:
                    return jsonify({"status": "error", "message": "Invalid server ID"}), 404
                if resultExists(response):
                    server = response[0]["result"][0]
                    bot_server = self.bot.get_server(server_id)
                    prefix = server.get("prefix", config.DEFAULT_PREFIX)

                    roles = {}
                    server_roles = await bot_server.fetch_roles()
                    highest_priority = 0
                    for role in server_roles:
                        if role.bot_user_id == self.bot.user.id:
                            highest_priority = role.priority
                            break
                    for role in server_roles:
                        if role.priority >= highest_priority:
                            continue
                        roles[role.id] = {
                            "name": role.name,
                            "color": [str(c) for c in role.colors],
                            "priority": role.priority,
                            "perms": role.permissions.values,
                            "base": role.base,
                        }
                    
                    channels = {}
                    channel_req = await self.bot.http.request(Route("GET", f"/teams/{server_id}/channels", override_base=Route.USER_BASE))
                    if channel_req:
                        for c in channel_req["channels"]:
                            channels[c["id"]] = {
                                "name": c["name"],
                                "type": c["contentType"],
                                "id": c["id"],
                            }

                    data = {
                        "prefix": prefix,
                        "roles": roles,
                        "channels": channels,
                    }

                    return jsonify({"status": "ok", "server": data})

def setup(bot: commands.Bot):
    bot.add_cog(Auth(bot))