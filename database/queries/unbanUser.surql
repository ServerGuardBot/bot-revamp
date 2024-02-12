DELETE user_status WHERE
    type = "tempban" AND
    guild_id = $guild_id AND
    user_id = $user_id;