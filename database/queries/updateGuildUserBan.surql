UPDATE guild_user SET
    is_banned = $banned
WHERE guild_id = $guild AND user_id = $id;