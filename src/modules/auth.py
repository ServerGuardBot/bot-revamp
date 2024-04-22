from core.checks_api import authenticated, dashboard_access, unauthenticated, user_is_developer
from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from database.permissions import UserPermissions
from core.setting_handlers import InvalidSetting
from core.emotes import EMOTE_VERIFICATION_TICK
from core.images import IMAGE_DEFAULT_AVATAR
from quart import Quart, jsonify, request
from datetime import datetime, timedelta
from quart_cors import route_cors
from guilded.ext import commands
from guilded.http import Route
from database import valkey
from core import defaults

import database as db
import user_agents
import pycountry
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

            async def failed():
                await message.reply(embed=EMBED_DENIED(
                    title="Failure",
                    description=f"{message.author.mention}, Please submit a valid login code here, and remember not to post anything here that others tell you to!"
                ), delete_after=10, private=True)

            try:
                token = await db.auth.get_token(message.content)
            except:
                await failed()
            else:
                if token.type != "login":
                    await failed()
                    return
                if token.user_id:
                    await failed()
                    return

                login_message = await message.reply(embed=EMBED_STANDARD(
                    title="Verify Login",
                    description=f"Hey {message.author.mention}! Are you trying to log in from **{token.get('location', 'Unknown')}** on **{token.get('browser', 'Unknown Browser')} {token.get('platform', 'Unidentified Platform')}?** If so, please click the :white_check_mark: below!"
                ), delete_after=60, private=True)

                payload = {
                    "token": message.content,
                    "user": message.author_id
                }
                valkey.set(f"login:{login_message.id}", db.encoder.encode(payload), 70)

                await login_message.add_reaction(guilded.utils.Object(EMOTE_VERIFICATION_TICK))
    
    @commands.Cog.listener()
    async def on_message_reaction_add(self, event: guilded.MessageReactionAddEvent):
        if event.message.channel_id != config.LOGIN_CHANNEL_ID: return
        if event.message_id in self.user_tokens:
            data = valkey.get(f"login:{event.message_id}")
            if data:
                data = db.decoder.decode(data)
            else:
                return
            if event.user_id != data["user"]: return
            try:
                token = await db.auth.get_token(data["token"])
            except:
                return
            else:
                if token["type"] != "login":
                    return
                try:
                    await token.update(event.user_id)
                except:
                    await event.message.channel.send(embed=EMBED_DENIED(
                        title="Failure",
                        description=f"<@{event.user_id}>, There was an error logging you in. Please try again."
                    ), delete_after=10, private=True)
                else:
                    await event.message.channel.send(embed=EMBED_SUCCESS(
                        title="Success",
                        description=f"<@{event.user_id}>, You should now be logged in on your browser. If you closed the login page before this then you will have to login again."
                    ), delete_after=10, private=True)
    
    def register_routes(self, app: Quart):
        @app.route("/login/<string:lock>/<string:token>", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @unauthenticated
        async def GetLoginState(lock: str, token: str):
                try:
                    token = await db.auth.get_token(token)
                except:
                    return jsonify({"status": "error", "message": "Invalid or expired token"}), 404
                else:
                    if token.type != "login" or token.lock != lock:
                        return jsonify({"status": "error", "message": "Invalid token"}), 400
                    if token.user_id:
                        loginToken = LoginToken("user", token.user_id)
                        refreshToken = LoginToken("refresh", token.user_id)
                        res = jsonify({
                            "status": "ok",
                            "state": 1 # Authorized
                        })
                        res.set_cookie("session", str(loginToken), expires=datetime.now() + LOGIN_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE, samesite="None", httponly=True)
                        res.set_cookie("refresh", str(refreshToken), expires=datetime.now() + REFRESH_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE, samesite="None", httponly=True)
                        
                        try:
                            await token.delete()
                        except:
                            pass
                        
                        return res
                    else:
                        return jsonify({
                            "status": "ok",
                            "state": 0 # Not yet authorized
                        })
        
        @app.route("/login", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @unauthenticated
        async def CreateLoginToken():
            lock = hashlib.sha256(os.urandom(32)).hexdigest()
            country_code = request.headers.get("CF-IPCountry")
            if country_code:
                if country_code == "T1":
                    country_name = "Tor Network"
                else:
                    country_name = pycountry.countries.get(alpha_2=country_code).name
            else:
                country_name = "Unknown"
            ua = user_agents.parse(request.headers.get("User-Agent"))
            try:
                token = await db.auth.create_login_token(country_name, ua.browser, ua.os.family, lock)
            except:
                return jsonify({"status": "error", "message": "Failed to create login token"}), 500
            else:
                return jsonify({
                    "status": "ok",
                    "token": token.id,
                    "lock": lock,
                })
        
        @app.route("/login", methods=["DELETE"])
        @route_cors(allow_headers=["content-type"], allow_methods=["DELETE"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @unauthenticated
        async def CancelLoginToken():
            post_data: dict = await request.get_json()
            if post_data is None:
                return jsonify({"status": "error", "message": "Invalid request"}), 400
            if post_data.get("token") is None:
                return jsonify({"status": "error", "message": "Invalid request"}), 400
            try:
                token = await db.auth.get_token(post_data["token"])
            except:
                return jsonify({"status": "error", "message": "Invalid or expired token"}), 404
            else:
                if token.type != "login" or token.lock != post_data["lock"]:
                    return jsonify({"status": "error", "message": "Invalid token"}), 400

                try:
                    await token.delete()
                except:
                    pass

                return jsonify({"status": "ok"})
        
        @app.route("/logout", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        async def Logout():
            cookies = request.cookies
            sessionCookie = cookies.get("session")
            refreshCookie = cookies.get("refresh")

            if sessionCookie and refreshCookie:
                sessionToken = LoginToken.from_token(sessionCookie)
                refreshToken = LoginToken.from_token(refreshCookie)

                if (not sessionToken or not refreshToken) or (not sessionToken.valid or not refreshToken.valid):
                    return jsonify({"status": "error", "message": "Not authorized"}), 401
                if sessionToken.type != "user" or refreshToken.type != "refresh":
                    return jsonify({"status": "error", "message": "Invalid session or refresh token"}), 400
                try:
                    is_valid = await db.auth.is_refresh_token_valid(refreshCookie)
                except:
                    return jsonify({"status": "error", "message": "Something went wrong"}), 500
                else:
                    if not is_valid:
                        res = jsonify({"status": "error", "message": "Invalid refresh token"})
                        res.set_cookie("session", "", expires=0, domain=config.API_SITE, samesite="None", secure=True, httponly=True)
                        res.set_cookie("refresh", "", expires=0, domain=config.API_SITE, samesite="None", secure=True, httponly=True)
                        return res, 400
                
                try:
                    await db.auth.blacklist_refresh_token(refreshCookie, int((refreshToken.created + REFRESH_TOKEN_EXPIRATION).timestamp()))
                except:
                    return jsonify({"status": "error", "message": "Something went wrong"}), 500
                else:
                    res = jsonify({"status": "ok"})
                    res.set_cookie("session", "", expires=0, domain=config.API_SITE, samesite="None", secure=True, httponly=True)
                    res.set_cookie("refresh", "", expires=0, domain=config.API_SITE, samesite="None", secure=True, httponly=True)
                    return res
            return jsonify({"status": "error", "message": "Not authorized"}), 401
        
        @app.route("/refresh", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        async def Refresh():
            cookies = request.cookies
            refreshCookie = cookies.get("refresh")

            if refreshCookie:
                refreshToken = LoginToken.from_token(refreshCookie)

                if (not refreshToken) or refreshToken.type != "refresh" or not refreshToken.valid:
                    return jsonify({"status": "error", "message": "Invalid refresh token"}), 400
                try:
                    is_valid = await db.auth.is_refresh_token_valid(refreshCookie)
                except:
                    return jsonify({"status": "error", "message": "Something went wrong"}), 500
                else:
                    if not is_valid:
                        res = jsonify({"status": "error", "message": "Invalid refresh token"})
                        res.set_cookie("session", "", expires=0, domain=config.API_SITE, samesite="None", secure=True, httponly=True)
                        res.set_cookie("refresh", "", expires=0, domain=config.API_SITE, samesite="None", secure=True, httponly=True)
                        return res, 400
                
                try:
                    await db.auth.blacklist_refresh_token(refreshCookie, int((refreshToken.created + REFRESH_TOKEN_EXPIRATION).timestamp()))
                except:
                    return jsonify({"status": "error", "message": "Something went wrong"}), 500
                else:
                    res = jsonify({"status": "ok"})
                    new_refresh = LoginToken("refresh", refreshToken.user_id)
                    new_session = LoginToken("user", refreshToken.user_id)
                    res.set_cookie("session", str(new_session), max_age=LOGIN_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE, httponly=True, samesite="None")
                    res.set_cookie("refresh", str(new_refresh), max_age=REFRESH_TOKEN_EXPIRATION, secure=True, domain=config.API_SITE, httponly=True, samesite="None")
                    return res, 200

            return jsonify({"status": "error", "message": "Not authorized"}), 401
        
        @app.route("/session", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        async def GetSession():
            userId = request.authenticated_user
            bot_servers = self.bot.servers
            try:
                user = await db.users.fetch_or_create_user(await self.bot.getch_user(userId))
            except:
                return jsonify({"status": "error", "message": "Could not retrieve user"}), 500
            else:
                servers = []
                for server in bot_servers:
                    if server.member_count == 0:
                        await server.fill_members()

                    guildUser = None
                    try:
                        guildUser = server.get_member(userId)
                    except:
                        pass

                    if not guildUser:
                        continue

                    isPremium = False
                    try:
                        guild = await db.servers.fetch_or_create_server(server)
                    except Exception as e:
                        print("{}: {}".format(type(e).__name__, e))
                        continue
                    else:
                        if guildUser:
                            try:
                                guild_user = await guild.fetch_or_create_member(guildUser)
                            except Exception as e:
                                print("{}: {}".format(type(e).__name__, e))
                            else:
                                if guild_user.can_access_dash:
                                    try:
                                        servers.append({
                                            "id": server.id,
                                            "name": server.name,
                                            "bio": server.description,
                                            "avatar": server.avatar.url if server.avatar else IMAGE_DEFAULT_AVATAR,
                                            "banner": server.banner.url if server.banner else None,
                                            "members": server.member_count,
                                            "perms": guild_user.perms.list,

                                            "isActive": True,
                                            "isPremium": guild.is_premium,
                                        })
                                    except Exception as e:
                                        print("{}: {}".format(type(e).__name__, e))
                try:
                    is_dev = await user_is_developer(self.bot, userId)
                    return jsonify({
                        "status": "ok",
                        "user": {
                            "id": userId,
                            "name": user.name,
                            "avatar": user.avatar,
                            "language": user.language,
                            "isDeveloper": is_dev,
                        },
                        "servers": servers,
                    })
                except Exception as e:
                    print("{}: {}".format(type(e).__name__, e))
                    return jsonify({"status": "error", "message": "Could not retrieve user"}), 500

def setup(bot: commands.Bot):
    bot.add_cog(Auth(bot))