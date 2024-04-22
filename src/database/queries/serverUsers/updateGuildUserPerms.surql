UPDATE guild_user SET
    perms = $perms,
    can_access_dash = $access
WHERE guild_id = $guild AND user_id = $id;