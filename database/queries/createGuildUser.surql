CREATE guild_user SET
    guild_id = $guild,
    user_id = $id,
    perms = $perms,
    xp = $xp,
    is_banned = $banned,
    can_access_dash = $access;