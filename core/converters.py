from typing import TypeVar
from guilded.ext import commands

import guilded
import re

_utils_get = guilded.utils.get
_utils_find = guilded.utils.find
T_co = TypeVar('T_co', covariant=True)

_USER_ID_REGEX = re.compile(r'([a-zA-Z0-9]{8,10})$|<@([a-zA-Z0-9]{8,10})>$')

def _get_from_servers(bot, getter, argument):
    result = None
    for server in bot.servers:
        result = getattr(server, getter)(argument)
        if result:
            return result
    return result

class UserMentionConverter(commands.Converter[T_co]):
    @staticmethod
    def _get_id_match(argument: str):
        return _USER_ID_REGEX.match(argument)

class UserConverter(UserMentionConverter[guilded.User]):
    """Converts to a :class:`~guilded.User`.

    The lookup strategy is as follows (in order):

    1. Lookup by ID
    2. Lookup by mention (a REAL one, because the native library one doesn't lmao)
    3. Lookup by name
    """

    def find_user_named(self, bot: commands.Bot, argument: str):
        return _utils_find(lambda m: m.name == argument, bot.users)

    async def convert(self, ctx: commands.Context, argument: str) -> guilded.User:
        bot = ctx.bot
        match = self._get_id_match(argument)
        result = None
        user_id = None
        if match is None:
            # not a mention
            result = self.find_user_named(bot, argument)
        else:
            user_id = match.group(1) or match.group(2)
            result = bot.get_user(user_id) or _utils_get(ctx.message.mentions, id=user_id)

        if result is None:
            if user_id is not None:
                result = await bot.getch_user(user_id)
            else:
                result = self.find_user_named(bot, argument)

            if not result:
                raise commands.UserNotFound(argument)

        return result

class MemberConverter(UserMentionConverter[guilded.Member]):
    """Converts to a :class:`~guilded.Member`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID
    2. Lookup by mention (a REAL one, because the native library one doesn't lmao)
    3. Lookup by name
    """

    def __init__(self, *, default: T_co = None) -> None:
        self.default = default

    def find_member_named(self, server: guilded.Server, argument: str):
        return _utils_find(lambda m: m.name == argument, server.members)

    async def convert(self, ctx: commands.Context, argument: str) -> guilded.Member:
        bot = ctx.bot
        match = self._get_id_match(argument)
        server = ctx.server
        result = None
        user_id = None
        if match is None:
            # not a mention
            result = self.find_member_named(server, argument)
        else:
            user_id = match.group(1) or match.group(2)
            if server:
                result = server.get_member(user_id) or _utils_get(ctx.message.mentions, id=user_id)
            else:
                result = _get_from_servers(bot, 'get_member', user_id)
        
        if result is None:
            if server is None:
                raise commands.MemberNotFound(argument)

            if user_id is not None:
                try:
                    result = await server.getch_member(user_id)
                except:
                    pass

            if not result:
                # At this point, the argument is definitely not an ID
                result = self.find_member_named(server, argument)

            if not result:
                raise commands.MemberNotFound(argument)

        return result

class LangConverter(commands.Converter[str]):
    langs = {
        "en": ["english"],
    }

    async def convert(self, ctx: commands.Context, argument: str) -> str:
        for code in self.langs:
            if argument.lower() in self.langs[code]:
                return code
            if argument.lower() == code:
                return code
        raise commands.BadArgument(f"Language '{argument}' not found")