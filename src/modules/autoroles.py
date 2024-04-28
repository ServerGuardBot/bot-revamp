from core.checks_api import dashboard_access, authenticated, has_permissions
from quart import Quart, jsonify, request
from guilded.ext import commands, tasks
from database.autoroles import Autorole
from quart_cors import route_cors
from core.checks import listener
from typing import List

import database as db
import guilded

class Autoroles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def update_autoroles(self, member: guilded.Member, autoroles: List[Autorole]):
        role_ids = member._role_ids
        if len(role_ids) == 0:
            role_ids = await member.fetch_role_ids()

        to_add, to_remove = [], []
        for autorole in autoroles:
            should_have = False
            if len(autorole.has_roles) > 0:
                if autorole.has_all:
                    if all([role in role_ids for role in autorole.has_roles]):
                        should_have = True
                else:
                    if any([role in role_ids for role in autorole.has_roles]):
                        should_have = True
            if len(autorole.not_has_roles) > 0:
                if len(autorole.has_roles) > 0:
                    # Act like a blacklist if there are roles in has_roles
                    if autorole.not_has_all:
                        if any([role in role_ids for role in autorole.not_has_roles]):
                            should_have = False
                    else:
                        if all([role in role_ids for role in autorole.not_has_roles]):
                            should_have = False
                else:
                    # Act like a whitelist if there are no roles in has_roles
                    if autorole.not_has_all:
                        if not all([role in role_ids for role in autorole.not_has_roles]):
                            should_have = True
                    else:
                        if not any([role in role_ids for role in autorole.not_has_roles]):
                            should_have = True
            
            if should_have:
                if autorole.role_id not in role_ids:
                    to_add.append(autorole.role_id)
            else:
                if autorole.role_id in role_ids:
                    to_remove.append(autorole.role_id)
        
        if len(to_add) > 0:
            await member.add_roles(*[guilded.Object(role) for role in to_add])
        if len(to_remove) > 0:
            await member.remove_roles(*[guilded.Object(role) for role in to_remove])
    
    @listener("autoroles")
    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
        member = event.member
        server = event.server
        
        try:
            autoroles = await db.autoroles.get_autoroles(server.id)
        except:
            return
        else:
            to_check = []
            for autorole in autoroles:
                autorole: Autorole
                if autorole.on_join and autorole.delay_time > 0:
                    try:
                        await db.autoroles.schedule_autorole(server.id, member.id, autorole.id)
                    except:
                        pass
                else:
                    to_check.append(autorole)
            if len(to_check) > 0:
                try:
                    await self.update_autoroles(member, to_check)
                except:
                    pass
    
    @listener("autoroles")
    @commands.Cog.listener()
    async def on_bulk_member_roles_update(self, event: guilded.BulkMemberRolesUpdateEvent):
        server = event.server
        try:
            autoroles = await db.autoroles.get_autoroles(server.id)
        except:
            return
        else:
            for member in event.members:
                to_check = []
                for autorole in autoroles:
                    if autorole.delay_time == 0:
                        to_check.append(autorole)
                if len(to_check) > 0:
                    try:
                        await self.update_autoroles(member, to_check)
                    except:
                        pass
    
    def register_routes(self, app: Quart):
        @app.route("/servers/<string:server_id>/autoroles")
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def GetAutoroles(server_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(server_id)
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    autoroles = await db.autoroles.list_autoroles(server_id)
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while fetching autoroles."}), 500
                else:
                    return jsonify({
                        "status": "success",
                        "autoroles": [{
                            "id": role.id,
                            "has_roles": role.has_roles,
                            "not_has_roles": role.not_has_roles,
                            "has_all": role.has_all,
                            "not_has_all": role.not_has_all,
                            "on_join": role.on_join,
                            "delay_time": role.delay_time
                        } for role in autoroles]
                    })
        
        @app.route("/servers/<string:server_id>/autoroles", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def CreateAutorole(server_id: str):
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
                    if data.get("has_roles") is None \
                        or data.get("not_has_roles") is None \
                        or data.get("has_all") is None \
                        or data.get("not_has_all") is None \
                        or data.get("on_join") is None \
                        or data.get("delay_time") is None:
                        return jsonify({"status": "error", "error": "Missing required fields."}), 400
                    try:
                        result = await db.autoroles.create_autorole(
                            server_id,
                            has_roles=data["has_roles"],
                            not_has_roles=data["not_has_roles"],
                            has_all=data["has_all"],
                            not_has_all=data["not_has_all"],
                            on_join=data["on_join"],
                            delay_time=data["delay_time"]
                        )
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while creating autorole."}), 500
                    else:
                        return jsonify({"status": "success", "autorole": {
                            "id": result.id,
                            "has_roles": result.has_roles,
                            "not_has_roles": result.not_has_roles,
                            "has_all": result.has_all,
                            "not_has_all": result.not_has_all,
                            "on_join": result.on_join,
                            "delay_time": result.delay_time
                        }})
        
        @app.route("/servers/<string:server_id>/autoroles/<string:autorole_id>", methods=["PATCH"])
        @route_cors(allow_headers=["content-type"], allow_methods=["PATCH"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def UpdateAutorole(server_id: str, autorole_id: str):
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
                    try:
                        autorole = await db.autoroles.get_autorole(autorole_id)
                    except db.NotFound:
                        return jsonify({"status": "error", "error": "Autorole not found."}), 404
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while fetching autorole."}), 500
                    else:
                        if autorole.guild_id != server_id:
                            return jsonify({"status": "error", "error": "Autorole not found."}), 404
                        try:
                            await autorole.update(
                                has_roles=data.get("has_roles"),
                                not_has_roles=data.get("not_has_roles"),
                                has_all=data.get("has_all"),
                                not_has_all=data.get("not_has_all"),
                                on_join=data.get("on_join"),
                                delay_time=data.get("delay_time")
                            )
                        except:
                            return jsonify({"status": "error", "error": "Something went wrong while updating autorole."}), 500
                        else:
                            return jsonify({"status": "success", "autorole": {
                                "id": autorole.id,
                                "has_roles": autorole.has_roles,
                                "not_has_roles": autorole.not_has_roles,
                                "has_all": autorole.has_all,
                                "not_has_all": autorole.not_has_all,
                                "on_join": autorole.on_join,
                                "delay_time": autorole.delay_time
                            }})
        
        @app.route("/servers/<string:server_id>/autoroles/<string:autorole_id>", methods=["DELETE"])
        @route_cors(allow_headers=["content-type"], allow_methods=["DELETE"], allow_origin=[config.ORIGIN_SITE], allow_credentials=True)
        @authenticated
        @dashboard_access
        @has_permissions(manage_autoroles=True)
        async def DeleteAutorole(server_id: str, autorole_id: str):
            try:
                guild = await db.servers.fetch_or_create_server(server_id)
            except:
                return jsonify({"status": "error", "error": "Something went wrong while fetching server information."}), 500
            else:
                try:
                    autorole = await db.autoroles.get_autorole(autorole_id)
                except db.NotFound:
                    return jsonify({"status": "error", "error": "Autorole not found."}), 404
                except:
                    return jsonify({"status": "error", "error": "Something went wrong while fetching autorole."}), 500
                else:
                    if autorole.guild_id != server_id:
                        return jsonify({"status": "error", "error": "Autorole not found."}), 404
                    try:
                        await autorole.delete()
                    except:
                        return jsonify({"status": "error", "error": "Something went wrong while deleting autorole."}), 500
                    else:
                        return jsonify({"status": "success"})

def setup(bot: commands.Bot):
    bot.add_cog(Autoroles(bot))