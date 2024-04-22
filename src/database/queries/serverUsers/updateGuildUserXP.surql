UPDATE guild_user SET
    xp = $xp
WHERE guild_id = $guild AND user_id = $id;