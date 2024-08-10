from core import defaults, server_settings, setting_permissions, audit_log_events, limits
from core.checks_api import authenticated, dashboard_access, has_permissions
from core.setting_handlers import InvalidSetting
from database.permissions import UserPermissions
from modules.automod import LDNOOBW_LANGS
from quart import Quart, jsonify, request
from core.cors import apply_cors
from guilded.ext import commands
from guilded.http import Route
from datetime import datetime
from database import valkey

import database as db
import guilded
import inspect
import config

class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.setting_listeners = []
        
        self.register_listener("permissions", self.on_perms_updated)
    
    @commands.Cog.listener()
    async def on_bulk_member_roles_update(self, event: guilded.BulkMemberRolesUpdateEvent):
            try:
                guild = await db.servers.fetch_or_create_server(event.server)
            except Exception as e:
                print("Failed to fetch guild: {} - {}".format(type(e).__name__, e))
            else:
                role_perms: dict = guild.settings.get("permissions", {})
                user_perms = UserPermissions()
                for member in event.after:
                    for role_id in member._role_ids:
                        server_role = role_perms.get(str(role_id))
                        if server_role:
                            user_perms += UserPermissions.from_string(server_role)
                if member.id == event.server.owner_id:
                    user_perms = UserPermissions.all()
                try:
                    user = await guild.fetch_or_create_member(member)
                    await user.set_perms(user_perms)
                except Exception as e:
                    print("Failed to update user permissions: {} - {}".format(type(e).__name__, e))
                
                try:
                    await user.set_roles(list(member._role_ids))
                except Exception as e:
                    print("Failed to update user roles: {} - {}".format(type(e).__name__, e))
    
    def register_listener(self, setting: str, func):
        self.setting_listeners.append((setting, func))
    
    async def dispatch_event(self, server_id: str, setting: str, value, old_value):
        server: guilded.Server = await self.bot.getch_server(server_id)
        for listener in self.setting_listeners:
            if listener[0] == setting:
                await listener[1](server, value, old_value)
    
    async def report_action(self, guild_id: str, user: str, event_name: str, **kwargs):
        payload = {
            "originator_id": user,
            "event_name": event_name,
        }
        for key, value in kwargs.items():
            payload[key] = value
        
        try:
            guild = await db.servers.fetch_or_create_server(self.bot.get_server(guild_id))
            log = await guild.create_audit_log(payload)
        except Exception as e:
            print("Failed to report action: {} - {}".format(type(e).__name__, e))
        else:
            print("Audit log created: {}".format(log.id))
            return log
        return None

    async def on_perms_updated(self, server: guilded.Server, new_perms: dict, old_perms: dict):
        changed_perms = []
        for key, value in new_perms.items():
            if value != old_perms.get(key):
                changed_perms.append(int(key))
        for key, value in old_perms.items():
            if key in changed_perms:
                continue
            if value != new_perms.get(key):
                changed_perms.append(int(key))

        # Highly unlikely, but just in case
        if len(changed_perms) == 0:
            return
        try:
            guild = await db.servers.fetch_or_create_server(server)
            users_with_role = await guild.users_with_roles(changed_perms)
        except Exception as e:
            print("Failed to list users with role: {} - {}".format(type(e).__name__, e))
        else:
            if resultExists(response):
                for user_id in users_with_role:
                    member: guilded.Member = await server.getch_member(user_id)
                    roles = member._role_ids
                    if len(roles) == 0:
                        roles = await member.fetch_role_ids()
                        if len(roles) == 0:
                            # Should be really damn unlikely, but just in case lmao
                            continue
                    user_perms = UserPermissions()
                    for id in roles:
                        perms = new_perms.get(str(id))
                        if perms:
                            user_perms += UserPermissions.from_string(perms)
                    if member.id == server.owner_id:
                        user_perms = UserPermissions.all()
                    try:
                        user = await guild.fetch_or_create_member(member)
                        await user.set_perms(user_perms)
                    except Exception as e:
                        print("Failed to update user permissions: {} - {}".format(type(e).__name__, e))
    
    def register_routes(self, app: Quart):
        @app.route("/modules", methods=["GET"])
        async def Modules():
            return jsonify({
                "modules": defaults.all_modules,
                "defaults": defaults.modules,
            })
        
        @app.route("/servers", methods=["GET"])
        @authenticated
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        async def GetServers():
            userId = request.authenticated_user
            bot_servers = self.bot.servers
            servers = {}
            for server in bot_servers:
                if server.member_count == 0:
                    await server.fill_members()

                try:
                    member = server.get_member(userId)
                except:
                    pass
                else:
                    if member:
                        try:
                            guild = await db.servers.fetch_or_create_server(server)
                            user = await guild.fetch_or_create_member(member)
                        except Exception as e:
                            err = "{}: {}".format(type(e).__name__, e)
                            print(f"Failed to fetch user {member.id} in server {server.id}: {err}")
                        else:
                            if user.can_access_dash:
                                servers[server.id] = {
                                    "name": server.name,
                                    "avatar": server.avatar.url if server.avatar else IMAGE_DEFAULT_AVATAR,
                                    "banner": server.banner.url if server.banner else None,
                                    "members": server.member_count,
                                }
            return jsonify({"status": "ok", "servers": servers})
        
        @app.route("/servers/<string:server_id>")
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        async def ServerOverview(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "message": "Invalid server ID"}), 404
            else:
                if not guild.active:
                    return jsonify({"status": "error", "message": "Invalid server ID"}), 404
                bot_server = self.bot.get_server(server_id)
                
                members = {}
                if len(bot_server.members) == 0:
                    await bot_server.fill_members()
                for member in bot_server.members:
                    if member.id == self.bot.user_id:
                        continue
                    members[member.id] = {
                        "name": member.name,
                        "avatar": member.display_avatar.url,
                    }

                roles = {}
                bot_roles = await (await bot_server.getch_member(self.bot.user_id)).fetch_role_ids()
                server_roles = await bot_server.fetch_roles()
                highest_priority = -999999999
                for role in server_roles:
                    if role.id in bot_roles and role.priority > highest_priority:
                        highest_priority = role.priority
                for role in server_roles:
                    roles[role.id] = {
                        "name": role.name,
                        "color": [str(c) for c in role.colors],
                        "priority": role.priority,
                        "perms": role.permissions.values,
                        "base": role.base,
                        "canManage": role.priority >= highest_priority - 1,
                    }
                
                channels = {}
                
                cached_channels = valkey.get(f"servers:{server_id}:channels")
                if cached_channels:
                    channels = db.decoder.decode(cached_channels.decode("utf-8"))
                else:
                    channel_req = await self.bot.http.request(Route("GET", f"/teams/{server_id}/channels", override_base=Route.USER_BASE))
                    if channel_req:
                        for c in channel_req["channels"]:
                            channels[c["id"]] = {
                                "name": c["name"],
                                "type": c["contentType"],
                                "id": c["id"],
                            }
                    valkey.set(f"servers:{server_id}:channels", db.encoder.encode(channels), 60 * 15)

                data = {
                    "roles": roles,
                    "channels": channels,
                    "members": members,
                }
                
                for item in guild.serialize_settings().items():
                    key, value = item[0], item[1]
                    data[key] = value

                return jsonify({"status": "ok", "server": data})
        
        @app.route("/servers/<string:server_id>/limits")
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        async def GetServerLimits(server_id: str):
            is_premium = False
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except Exception as e:
                print("Failed to get guild: {} - {}".format(type(e).__name__, e))
                return jsonify({"status": "error", "message": "An unknown error occurred"}), 500
            else:
                return jsonify({"status": "ok", "limits": {
                    "welcomerMessageLength": limits.welcomer_message_length,
                    "blacklistLength": guild.is_premium and limits.blacklist_length_premium or limits.blacklist_length,
                    "supportedFilterLangs": LDNOOBW_LANGS,
                    "maxRSSFeeds": guild.is_premium and limits.max_rss_feeds_premium or limits.max_rss_feeds,
                }})
        
        @app.route("/servers/<string:server_id>/permissions")
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @dashboard_access
        async def GetServerPermissions(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
            except:
                return jsonify({"status": "error", "message": "Invalid server ID"}), 404
            else:
                permissions = {}
                _perms: dict = guild.settings.get("permissions", {})
                for role_id in _perms.keys():
                    permissions[role_id] = UserPermissions.from_string(_perms[role_id]).list
                return jsonify({"status": "ok", "permissions": permissions})
            return jsonify({"status": "error", "message": "An unknown error occurred"}), 404
        
        @app.route("/servers/<string:server_id>/settings", methods=["PATCH"])
        @apply_cors(allow_methods=["PATCH"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        async def UpdateServerSettings(server_id: str):
            post_data = await request.get_json()
            if len(post_data) == 0:
                return jsonify({"status": "error", "message": "No data provided"}), 400
            try:
                server = self.bot.get_server(server_id)
                guild = await db.servers.fetch_or_create_server(server)
                user = await guild.fetch_or_create_member(await server.getch_member(request.authenticated_user))
            except:
                return jsonify({"status": "error", "message": "Failed to get server or user"}), 404
            else:
                failures = {}
                should_save = False
                changes = {}
                for key in post_data:
                    field_perms = getattr(setting_permissions, key, None)
                    if field_perms is None:
                        failures[key] = "Setting does not exist or requires another endpoint"
                        continue
                    else:
                        failed = False
                        for _perm in field_perms:
                            if not getattr(user.perms, _perm, False):
                                failures[key] = "You do not have permission to change this setting"
                                failed = True
                                break
                        if failed:
                            continue
                    handler = getattr(server_settings, key, None)
                    if handler is not None:
                        try:
                            # Check if handler is an async function
                            is_async = inspect.iscoroutinefunction(handler)
                            if is_async:
                                res = await handler(server_id, guild, post_data[key], self.bot)
                            else:
                                res = handler(server_id, guild, post_data[key], self.bot)
                            if res != None:
                                changes[key] = res
                                should_save = True
                        except InvalidSetting as e:
                            failures[key] = str(e)
                        except SyntaxError as e:
                            failures[key] = str(e)
                        except Exception as e:
                            print("{}: {}".format(type(e).__name__, e))
                            failures[key] = "An internal error occurred"
                    else:
                        failures[key] = "Setting does not exist"
                if should_save:
                    try:
                        await guild.update_settings(**changes)
                    except Exception as e:
                        import traceback
                        print("Failed to update settings for server {} - {}: {}".format(server_id, type(e).__name__, e))
                        return jsonify({
                            "status": "error",
                            "message": "Failed to update settings",
                            "traceback": traceback.format_exc()
                        }), 500
                    else:
                        for key in changes:
                            await self.report_action(
                                user=request.authenticated_user,
                                guild_id=server_id,
                                event_name="update_setting",
                                setting=key,
                                value=changes[key],
                                prev_value=guild.settings.get(key, defaults.settings.get(key)),
                            )
                            await self.dispatch_event(
                                server_id,
                                key,
                                changes[key],
                                guild.settings.get(key, defaults.settings.get(key)),
                            )
                return jsonify({"status": "ok", "failures": failures})
    
        @app.route("/servers/<string:server_id>/audit/info", methods=["GET"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @has_permissions(view_audit_logs=True)
        async def GetAuditInfo(server_id: str):
            events = {}
            for name in dir(audit_log_events):
                if name.startswith("_"):
                    continue
                event = getattr(audit_log_events, name)
                events[name] = event

            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
                audit_log_users = await guild.get_audit_log_users()
            except Exception as e:
                print("Failed to get audit log users for server {} - {}: {}".format(server_id, type(e).__name__, e))
                return jsonify({"status": "error", "message": "Failed to get audit log users"}), 500
            else:
                return jsonify({"status": "ok", "users": audit_log_users, "events": events})
    
        @app.route("/servers/<string:server_id>/audit", methods=["GET"])
        @apply_cors(allow_credentials=True, allow_origin=[config.ORIGIN_SITE])
        @authenticated
        @has_permissions(view_audit_logs=True)
        async def GetAuditLogs(server_id: str):
            range_start = request.args.get("start", type=int)
            range_end = request.args.get("end", type=int)
            authors = request.args.getlist("author", type=str)
            event_names = request.args.getlist("event", type=str)
            limit = max(20, min(100, request.args.get("limit", 50, type=int)))
            page = request.args.get("page", 1, type=int)
            try:
                guild = await db.servers.fetch_or_create_server(self.bot.get_server(server_id))
                logs, count = await guild.get_audit_logs(
                    start=range_start,
                    end=range_end,
                    authors=authors,
                    event_names=event_names,
                    limit=limit,
                    page=page,
                )
                # TODO: Maybe an option to order by ascending or descending?
            except Exception as e:
                print("Failed to get audit logs for server {} - {}: {}".format(server_id, type(e).__name__, e))
                return jsonify({
                    "status": "error",
                    "message": "Failed to get audit logs"
                }), 400
            else:
                if count == 0:
                    return jsonify(
                        {
                            "status": "ok",
                            "logs": [],
                            "total": 0,
                        }
                    )
                parsedResult = []
                for log in logs:
                    log: db.servers.server.AuditLog
                    raw = dict(log.raw)
                    try:
                        if log.event_name == "update_setting":
                            if raw["setting"] == "permissions":
                                for role_id in raw["value"].keys():
                                    raw["value"][role_id] = UserPermissions.from_string(raw["value"][role_id]).list
                                if raw.get("prev_value"):
                                    for role_id in raw["prev_value"].keys():
                                        raw["prev_value"][role_id] = UserPermissions.from_string(raw["prev_value"][role_id]).list
                    except Exception as e:
                        print("{}: {}".format(type(e).__name__, e))
                    parsedResult.append(raw)
                return jsonify(
                    {
                        "status": "ok",
                        "logs": parsedResult,
                        "total": count,
                    }
                )

def setup(bot: commands.Bot):
    bot.add_cog(Dashboard(bot))