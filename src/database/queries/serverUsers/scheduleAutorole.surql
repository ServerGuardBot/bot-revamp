CREATE user_status SET
    type = "autorole",
    guild_id = $guild_id,
    user_id = $user_id,
    autorole_id = $autorole,
    ends = time::now() + type::duration($autorole.delay + "m");