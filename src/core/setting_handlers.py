import inspect
import guilded
import pytz
import re

from core import limits, setting_permissions
from database.permissions import UserPermissions
from database.servers import Server

URL_REGEX = r"^(http|https)://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3}(/\S*)?$"

class InvalidSetting(Exception):
    pass

def list_handler(
    whitelist: list=None,
    lowercase: bool=False,
    uppercase: bool=False,
    min_length: int=None,
    max_length: int=None,
    enforce_type: type=None,
):
    def handler(server_id: str, server: Server, value: list, bot: guilded.Client):
        if not isinstance(value, list):
            raise InvalidSetting("Expected list, got something else instead")
        if min_length is not None and len(value) < min_length:
            raise InvalidSetting(f"List must exceed {min_length} amount of items")
        if max_length is not None and len(value) > max_length:
            raise InvalidSetting(f"List exceeds {max_length} amount of items")
        if whitelist is not None:
            for item in value:
                if lowercase:
                    item: str = item.lower()
                    value[value.index(item)] = item
                if uppercase:
                    item: str = item.upper()
                    value[value.index(item)] = item
                if enforce_type is not None and not isinstance(item, enforce_type):
                    raise InvalidSetting(f"{item} is not of type {enforce_type}")
                if item not in whitelist:
                    raise InvalidSetting(f"{item} is not on the whitelist")
        return value
    return handler

def string_handler(
    lowercase: bool=False,
    uppercase: bool=False,
    min_length: int=None,
    max_length: int=None,
):
    def handler(server_id: str, server: Server, value: str, bot: guilded.Client):
        if lowercase:
            value = value.lower()
        if uppercase:
            value = value.upper()
        if min_length is not None and len(value) < min_length:
            raise InvalidSetting(f"Value '{value}' does not exceed minimum length of {min_length}")
        if max_length is not None and len(value) > max_length:
            raise InvalidSetting(f"Value '{value}' exceeds maximum length of {max_length}")
        return value
    return handler

def enum_handler(
    whitelist: list=None,
    lowercase: bool=False,
    uppercase: bool=False,
):
    def handler(server_id: str, server: Server, value: str, bot: guilded.Client):
        if lowercase:
            value = value.lower()
        if uppercase:
            value = value.upper()
        if value not in whitelist:
            raise InvalidSetting(f"{value} is not on the whitelist")
        return value
    return handler

def number_handler(
    min: int=None,
    max: int=None,
):
    def handler(server_id: str, server: Server, value: int, bot: guilded.Client):
        if min is not None and value < min:
            raise InvalidSetting(f"Value '{value}' is below minimum of {min}")
        if max is not None and value > max:
            raise InvalidSetting(f"Value '{value}' exceeds maximum of {max}")
        return value
    return handler

def bool_handler(server_id: str, server: Server, value: bool, bot: guilded.Client):
    if not isinstance(value, bool):
        raise InvalidSetting("Expected bool, got something else instead")
    return value

def channel_handler(allowed_types: list=None):
    if isinstance(allowed_types, str):
        allowed_types = [allowed_types]
    async def handler(server_id: str, server: Server, value: str, bot: guilded.Client):
        if value == "0": return value
        bot_server = bot.get_server(server_id)
        try:
            channel = await bot_server.getch_channel(value)
        except:
            raise InvalidSetting(f"Channel with id {value} does not exist")
        else:
            if allowed_types is not None and channel.type not in allowed_types:
                raise InvalidSetting(f"Channel's type ({channel.type}) is not permitted.")
            return value
        raise InvalidSetting(f"Channel with id {value} does not exist")
    return handler

def channel_list_handler(
    allowed_types: list=None,
    min_length: int=None,
    max_length: int=None,
):
    async def handler(server_id: str, server: Server, value: list, bot: guilded.Client):
        for item in value:
            # We can just reuse the channel_handler here
            # internally
            await channel_handler(allowed_types)(server_id, server, item, bot)
        if min_length is not None and len(value) < min_length:
            raise InvalidSetting(f"List must exceed {min_length} amount of items")
        if max_length is not None and len(value) > max_length:
            raise InvalidSetting(f"List exceeds {max_length} amount of items")
        return value
    return handler

# NOTE: Maybe modify this so a list of
# NOTE: required permissions can be supplied?
async def role_handler(server_id: str, server: Server, value: str, bot: guilded.Client):
    if value == "0": return value
    bot_server = bot.get_server(server_id)
    try:
        await bot_server.getch_role(int(value))
    except Exception as e:
        raise InvalidSetting(f"Role with id {value} does not exist")
    else:
        return value
    raise InvalidSetting(f"Role with id {value} does not exist")

def role_list_handler(
    min_length: int=None,
    max_length: int=None,
):
    async def handler(server_id: str, server: Server, value: list, bot: guilded.Client):
        for item in value:
            await role_handler(server_id, server, item, bot)
        if min_length is not None and len(value) < min_length:
            raise InvalidSetting(f"List must exceed {min_length} amount of items")
        if max_length is not None and len(value) > max_length:
            raise InvalidSetting(f"List exceeds {max_length} amount of items")
        return value
    return handler

async def member_handler(server_id: str, server: Server, value: str, bot: guilded.Client):
    if value == "0": return value
    bot_server = bot.get_server(server_id)
    try:
        await bot_server.getch_member(value)
    except Exception as e:
        raise InvalidSetting(f"Member with id {value} does not exist")
    else:
        return value
    raise InvalidSetting(f"Member with id {value} does not exist")

def member_list_handler(
    min_length: int=None,
    max_length: int=None,
):
    async def handler(server_id: str, server: Server, value: list, bot: guilded.Client):
        for item in value:
            await member_handler(server_id, server, item, bot)
        if min_length is not None and len(value) < min_length:
            raise InvalidSetting(f"List must exceed {min_length} amount of items")
        if max_length is not None and len(value) > max_length:
            raise InvalidSetting(f"List exceeds {max_length} amount of items")
        return value
    return handler

def strict_dict_handler(
    structure: dict,
):
    async def handler(server_id: str, server: Server, value: dict, bot: guilded.Client):
        for key in value.keys():
            if key not in structure.keys():
                raise InvalidSetting(f"Key '{key}' is not permitted")
            if inspect.iscoroutinefunction(structure[key]):
                other_value = await structure[key](server_id, server, value[key], bot)
            else:
                other_value = structure[key](server_id, server, value[key], bot)
            value[key] = other_value
        return value
    return handler

def non_strict_dict_handler(
    value_handler,
):
    async def handler(server_id: str, server: Server, value: dict, bot: guilded.Client):
        for key in value:
            other_value = value_handler(server_id, server, value[key], bot)
            value[key] = other_value
        return value
    return handler

# Custom handlers

automod_restriction_handler = strict_dict_handler(
    {
        "allow_roles": role_list_handler(),
        "allow_channels": channel_list_handler(),
        "allow_users": member_list_handler(),
        "blacklist_roles": role_list_handler(),
        "blacklist_channels": channel_list_handler(),
        "blacklist_users": member_list_handler(),
    }
)

welcomer_cycle = enum_handler(
    ["None", "Daily", "Weekly", "Monthly", "Random", "PerUser"],
)

async def permission_handler(server_id: str, server: Server, value: dict, bot: guilded.Client):
    bot_server = bot.get_server(server_id)
    for role_id in value:
        try:
            await bot_server.getch_role(int(role_id))
        except Exception as e:
            raise InvalidSetting(f"Role with id {role_id} does not exist")
        else:
            try:
                user_perms = UserPermissions.from_list(value[role_id])
            except:
                raise InvalidSetting(f"Invalid permission string for role {role_id}")
            else:
                value[str(role_id)] = str(user_perms)
    return value

def uses_custom_handler(server_id: str, server: Server, value, bot: guilded.Client):
    raise InvalidSetting("This setting is handled through a separate endpoint")

def contact_handler(server_id: str, server: Server, value: str, bot: guilded.Client):
    # Validates that the value is either a valid
    # URL, email, or phone number
    value = value.strip()
    if re.match(URL_REGEX, value):
        return value
    if re.match(r"^\d+$", value):
        return value
    if re.match(r"^\w+@\w+\.\w+$", value):
        return value
    raise InvalidSetting(f"Invalid contact: {value}")

def url_handler(server_id: str, server: Server, value: str, bot: guilded.Client):
    value = value.strip()
    if not re.match(URL_REGEX, value):
        raise InvalidSetting(f"Invalid URL: {value}")
    return value

def timezone_handler(server_id: str, server: Server, value: str, bot: guilded.Client):
    if value not in pytz.all_timezones:
        raise InvalidSetting(f"Invalid timezone: {value}")
    return value

def language_handler(server_id: str, server: Server, value: str, bot: guilded.Client):
    if value not in ["en", "de"]: # TODO: Rework this when proper bot localization is done
        raise InvalidSetting(f"Invalid language: {value}")
    return value

async def xp_role_handler(server_id: str, server: Server, value: dict, bot: guilded.Client):
    bot_server = bot.get_server(server_id)
    for id in value:
        if id == "-1": continue
        try:
            await bot_server.getch_role(int(id))
        except:
            raise InvalidSetting(f"Role with id {id} does not exist")
        if not isinstance(value[id], int):
            raise InvalidSetting(f"All values in role list must be integers.")
    return value

def blacklist_handler(server_id: str, server: Server, value: list, bot: guilded.Client):
    if not isinstance(value, list):
        raise InvalidSetting("Expected list, got something else instead")
    if len(value) == 0:
        return value
    if not all(isinstance(item, str) for item in value):
        raise InvalidSetting(f"All values in blacklist must be strings.")
    if server.is_premium:
        if len(value) > limits.blacklist_length_premium:
            raise InvalidSetting(f"Blacklist length cannot exceed {limits.blacklist_length_premium}")
    else:
        if len(value) > limits.blacklist_length:
            raise InvalidSetting(f"Blacklist length cannot exceed {limits.blacklist_length}")
    return value

def is_premium_server(handler):
    def wrapper(server_id: str, server: Server, value: str, bot: guilded.Client):
        if not server.is_premium:
            raise InvalidSetting("This setting is only available to premium servers")
        return handler(server_id, server, value, bot)
    return wrapper