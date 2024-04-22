DELETE guild_user WHERE
    guild_id = $guild,
    user_id = $id;