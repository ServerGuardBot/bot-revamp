from database import DBConnection, loadQuery, resultExists
from database.permissions import UserPermissions
from quart import request, jsonify
from functools import wraps

import guilded
import config

async def user_is_developer(bot: guilded.Client, user: str):
    support_server = await bot.getch_server(config.SUPPORT_SERVER_ID)
    member = await support_server.getch_member(user)
    if member:
        roles = await member.fetch_role_ids()
        if int(config.DEVELOPER_ROLE_ID) in roles:
            return True
    return False

def authenticated(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        from modules.auth import LoginToken
        session = request.cookies.get('session')

        if not session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        sessionToken = LoginToken.from_token(session)
        if sessionToken.type != 'user':
            return jsonify({'error': 'Unauthorized'}), 401
        
        if not sessionToken.valid:
            return jsonify({'error': 'Unauthorized'}), 401
        
        request.authenticated_user = sessionToken.user_id
        return await f(*args, **kwargs)

    return decorated

def optional_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        from modules.auth import LoginToken
        session = request.cookies.get('session')

        if session:
            sessionToken = LoginToken.from_token(session)
            if sessionToken.type != 'user':
                return jsonify({'error': 'Unauthorized'}), 401

            if not sessionToken.valid:
                return jsonify({'error': 'Unauthorized'}), 401

            request.authenticated_user = sessionToken.user_id

        return await f(*args, **kwargs)

    return decorated(f)

def unauthenticated(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        from modules.auth import LoginToken
        session = request.cookies.get('session')

        if session:
            token = LoginToken.from_token(session)
            if token.valid:
                return jsonify({'error': 'Unauthorized'}), 401
        
        refresh = request.cookies.get('refresh')

        if refresh:
            token = LoginToken.from_token(refresh)
            if token.valid:
                return jsonify({'error': 'Unauthorized'}), 401

        return await f(*args, **kwargs)

    return decorated

def dashboard_access(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        authorized_user = request.authenticated_user
        target_server = kwargs.get('server_id')

        if not authorized_user:
            raise RuntimeError("The authenticated check must be placed before the dashboard_access decorator! (Or you tried using this on a route that does not enforce auth)")
        if not target_server:
            raise RuntimeError("The dashboard_access decorator requires a server_id parameter in the url!")
        
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuildUser"), {
                    "guild": target_server,
                    "id": authorized_user
                })
            except:
                return jsonify({'error': 'Forbidden'}), 403
            if not resultExists(response):
                return jsonify({'error': 'Forbidden'}), 403
            user = response[0]["result"][0]
            if user["can_access_dash"]:
                return await f(*args, **kwargs)
        return jsonify({'error': 'Forbidden'}), 403
    return decorated

def has_permissions(**permissions):
    def wrap_func(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            authorized_user = request.authenticated_user
            target_server = kwargs.get('server_id')

            if not authorized_user:
                raise RuntimeError("The authenticated check must be placed before the has_permissions decorator! (Or you tried using this on a route that does not enforce auth)")
            if not target_server:
                raise RuntimeError("The has_permissions decorator requires a server_id parameter in the url!")
            
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("getGuildUser"), {
                        "guild": target_server,
                        "id": authorized_user
                    })
                except:
                    return jsonify({'error': 'Forbidden'}), 403
                if not resultExists(response):
                    return jsonify({'error': 'Forbidden'}), 403
                user = response[0]["result"][0]
                perms = UserPermissions.from_string(user["perms"])
                for permission in permissions:
                    if not getattr(perms, permission):
                        return jsonify({'error': 'Forbidden'}), 403
            return await f(*args, **kwargs)
        return decorated
    return wrap_func