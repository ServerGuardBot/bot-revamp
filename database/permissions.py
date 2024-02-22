class UserPermissions:
    __permissions__ = [
        "manage_verification",
        "manage_xp",
        "manage_moderation",
        "manage_automod",
        "manage_logging",
        "manage_filters",
        "manage_welcomer",
        "manage_autoroles",
        "manage_feeds",
        "manage_giveaways",
        "manage_automations",
        "manage_bot",
        "commands_ban",
        "commands_kick",
        "commands_mute",
        "commands_bypass",
        "commands_warn",
        "commands_evaluate",
        "commands_userinfo",
        "commands_serverinfo",
        "commands_purge",
        "commands_note",
        "bypass_filter",
        "host_giveaways",
        "is_trusted",
    ]

    __perm_map__ = {
        "manage_verification": "ManageVerification",
        "manage_xp": "ManageXP",
        "manage_moderation": "ManageModeration",
        "manage_automod": "ManageAutoMod",
        "manage_logging": "ManageLogging",
        "manage_filters": "ManageFilters",
        "manage_welcomer": "ManageWelcomer",
        "manage_autoroles": "ManageAutoroles",
        "manage_feeds": "ManageFeeds",
        "manage_giveaways": "ManageGiveaways",
        "manage_automations": "ManageAutomations",
        "manage_bot": "ManageBot",
        "commands_ban": "CommandsBan",
        "commands_kick": "CommandsKick",
        "commands_mute": "CommandsMute",
        "commands_bypass": "CommandsBypass",
        "commands_warn": "CommandsWarn",
        "commands_evaluate": "CommandsEvaluate",
        "commands_userinfo": "CommandsUserInfo",
        "commands_serverinfo": "CommandsServerInfo",
        "commands_purge": "CommandsPurge",
        "commands_note": "CommandsNote",
        "bypass_filter": "BypassFilter",
        "host_giveaways": "HostGiveaways",
        "is_trusted": "IsTrusted",
    }

    manage_verification = False
    manage_xp = False
    manage_moderation = False
    manage_automod = False
    manage_logging = False
    manage_filters = False
    manage_welcomer = False
    manage_autoroles = False
    manage_feeds = False
    manage_giveaways = False
    manage_automations = False
    manage_bot = False
    commands_ban = False
    commands_kick = False
    commands_mute = False
    commands_bypass = False
    commands_warn = False
    commands_evaluate = False
    commands_userinfo = False
    commands_serverinfo = False
    commands_purge = False
    commands_note = False
    bypass_filter = False
    host_giveaways = False
    is_trusted = False

    def __init__(self, **permissions):
        if self.manage_bot:
            # If you can manage the bot then you
            # practically have all the perms
            # anyway lol
            for permission in self.__permissions__:
                setattr(self, permission, True)
        else:
            for permission in permissions:
                setattr(self, permission, permissions[permission])

    @property
    def can_access_dash(self):
        # This property exists in case there's other none-manage
        # permissions that can grant dash access.
        for permission in self.__permissions__:
            if permission.startswith("manage") and getattr(self, permission, False):
                return True
        return False
    
    @property
    def list(self):
        perms = []
        for permission in self.__permissions__:
            if getattr(self, permission, False) and self.__perm_map__.get(permission):
                perms.append(self.__perm_map__[permission])
        return perms
    
    @classmethod
    def from_list(cls, permissions: list):
        perms = {}
        for key, value in cls.__perm_map__.items():
            if value in permissions:
                perms[key] = True
        return cls(**perms)
    
    @classmethod
    def from_string(cls, permissions: str):
        perms = {}
        # Permissions strings are a sequence of zeroes and ones
        # corresponding to the permissions defined in __permissions__
        index = 0
        for permission in permissions:
            if permission == "1":
                perms[cls.__permissions__[index]] = True
            elif permission == "0":
                perms[cls.__permissions__[index]] = False
            else:
                raise ValueError(f"Invalid permission string: {permission} in {permissions}")
            index += 1
        
        return cls(**perms)
    
    def __str__(self):
        return "".join(str(int(getattr(self, permission, False))) for permission in self.__permissions__)
    
    def __add__(self, other):
        if not isinstance(other, UserPermissions):
            raise TypeError(f"Cannot add {type(other)} to UserPermissions")
        perms = {}
        for permission in self.__permissions__:
            perms[permission] = getattr(self, permission, False) or getattr(other, permission, False)
        return UserPermissions(**perms)
    
    @classmethod
    def all(cls):
        return cls(**{permission: True for permission in cls.__permissions__})
    
    @classmethod
    def none(cls):
        return cls(**{permission: False for permission in cls.__permissions__})
    
    @classmethod
    def manager(cls):
        perms = {}
        for permission in cls.__permissions__:
            if permission.startswith("manage"):
                perms[permission] = True
        return cls(**perms)
    
    @classmethod
    def admin(cls):
        perms = {}
        for permission in cls.__permissions__:
            if permission.startswith("commands"):
                perms[permission] = True
        return cls(**perms)
    
    @classmethod
    def trusted(cls):
        return cls(**{"is_trusted": True})